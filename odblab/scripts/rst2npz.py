#-----------------------------------------------------------------------------------------------------------------------
# A Python script to extract data from an Ansys results database (*.rst).
# The extracted data is stored in the corresponding *.rstz file.
# Ansys must be installed on the system.
#-----------------------------------------------------------------------------------------------------------------------
# Copyright (c) 2026, Carlos Souto and Diego Salamanca
# Contact: csouto@fe.up.pt; diazsdiego@uniovi.es
# License: <LICENSE>
#-----------------------------------------------------------------------------------------------------------------------

# type: ignore

import os
import numpy as np
import ansys.dpf.core as dpf
from argparse import ArgumentParser

def main(rstPath):
    """The main block."""
    print("Extracting data from: " + rstPath)
    model = dpf.Model(rstPath)

    # ------------------------------------------------------------------------------------------------------------------
    #  MESH EXTRACTION
    # ------------------------------------------------------------------------------------------------------------------
    print("Extracting finite element mesh...")
    mesh = model.metadata.meshed_region

    # nodes
    nodes = np.asarray(mesh.nodes.coordinates_field.data, dtype=np.float32)

    # connectivity array offsets and element sizes
    offsets = np.asarray(mesh.elements.connectivities_field.entity_data_offsets, dtype=np.int32)
    offsets = np.append(offsets, np.int32(mesh.elements.connectivities_field.data.size))
    elementSizes = np.diff(offsets)
    maxElementSize = np.max(elementSizes)

    # elements
    i = np.repeat(np.arange(len(mesh.elements), dtype=np.int32), elementSizes)
    j = np.arange(offsets[-1], dtype=np.int32) - np.repeat(offsets[:-1], elementSizes)
    elements = np.full((len(mesh.elements), maxElementSize), -1, dtype=np.int32)
    elements[i, j] = mesh.elements.connectivities_field.data

    # types
    rawTypes = np.asarray(mesh.elements.element_types_field.data, dtype=np.int32)
    uniqueRawTypes = np.unique(rawTypes)
    typeMap = {t: dpf.element_types(int(t)).name for t in uniqueRawTypes}
    types = np.array([typeMap[t] for t in rawTypes], dtype="U")

    # sets
    sets = {}
    nodeMap = np.full((np.max(mesh.nodes.scoping.ids) + 1,), -1, dtype=np.int32)
    elementMap = np.full((np.max(mesh.elements.scoping.ids) + 1,), -1, dtype=np.int32)
    nodeMap[mesh.nodes.scoping.ids] = np.arange(len(mesh.nodes))
    elementMap[mesh.elements.scoping.ids] = np.arange(len(mesh.elements))
    for name in model.metadata.available_named_selections:
        scoping = model.metadata.named_selection(name)
        match scoping.location:
            case dpf.locations.nodal:
                indices = nodeMap[scoping.ids[scoping.ids < nodeMap.size]]
                sets[f"__node_set__.\"{name}\""] = np.unique(indices[indices > -1]).astype(np.int32, copy=False)
            case dpf.locations.elemental:
                indices = elementMap[scoping.ids[scoping.ids < elementMap.size]]
                sets[f"__element_set__.\"{name}\""] = np.unique(indices[indices > -1]).astype(np.int32, copy=False)
            case _:
                raise NotImplementedError()

    # ------------------------------------------------------------------------------------------------------------------
    #  RESULTS EXTRACTION
    # ------------------------------------------------------------------------------------------------------------------
    print("Extracting field outputs...")

    # pre-allocate storage
    times = np.asarray(model.metadata.time_freq_support.time_frequencies.data, dtype=np.float32)
    nodeHeaders, centroidHeaders = [], []
    nodeFieldOffsets, centroidFieldOffsets = [0], [0]
    for metadata in model.metadata.result_info.available_results:
        name = metadata.operator_name
        match metadata.dimensionality:
            case dpf.natures.scalar: headers = [name]
            case dpf.natures.vector: headers = [f"{name}.{name}{x}" for x in ("1", "2", "3")]
            case dpf.natures.symmatrix: headers = [f"{name}.{name}{xy}" for xy in ("11", "22", "33", "12", "23", "13")]
            case _: headers = [f"{name}.{name}{i + 1}" for i in range(metadata.n_components)]
        match metadata.native_location:
            case dpf.locations.nodal:
                nodeHeaders.extend(headers)
                nodeFieldOffsets.append(nodeFieldOffsets[-1] + metadata.n_components)
                centroidFieldOffsets.append(centroidFieldOffsets[-1])
            case dpf.locations.elemental:
                centroidHeaders.extend(headers)
                nodeFieldOffsets.append(nodeFieldOffsets[-1])
                centroidFieldOffsets.append(centroidFieldOffsets[-1] + metadata.n_components)
            case dpf.locations.elemental_nodal:
                nodeHeaders.extend(headers)
                centroidHeaders.extend(headers)
                nodeFieldOffsets.append(nodeFieldOffsets[-1] + metadata.n_components)
                centroidFieldOffsets.append(centroidFieldOffsets[-1] + metadata.n_components)
            case _:
                raise NotImplementedError()
    nodeData = np.full((nodeFieldOffsets[-1], len(mesh.nodes), len(times)), np.nan, dtype=np.float32)
    centroidData = np.full((centroidFieldOffsets[-1], len(mesh.elements), len(times)), np.nan, dtype=np.float32)

    # extraction loop
    for i, metadata in enumerate(model.metadata.result_info.available_results):
        result = getattr(model.results, metadata.name)
        fields = result.on_all_time_freqs.eval()
        match metadata.native_location:
            case dpf.locations.nodal:
                slice0 = slice(nodeFieldOffsets[i], nodeFieldOffsets[i] + metadata.n_components)
                for timeIndex, field in enumerate(fields):
                    boundsMask = field.scoping.ids < nodeMap.size
                    indices = nodeMap[field.scoping.ids[boundsMask]]
                    validMask = indices > -1
                    nodeData[slice0, indices[validMask], timeIndex] = field.data[boundsMask][validMask].T
            case dpf.locations.elemental:
                slice0 = slice(centroidFieldOffsets[i], centroidFieldOffsets[i] + metadata.n_components)
                for timeIndex, field in enumerate(fields):
                    boundsMask = field.scoping.ids < elementMap.size
                    indices = elementMap[field.scoping.ids[boundsMask]]
                    validMask = indices > -1
                    centroidData[slice0, indices[validMask], timeIndex] = field.data[boundsMask][validMask].T
            case dpf.locations.elemental_nodal:
                nodeSlice0 = slice(nodeFieldOffsets[i], nodeFieldOffsets[i] + metadata.n_components)
                centroidSlice0 = slice(centroidFieldOffsets[i], centroidFieldOffsets[i] + metadata.n_components)
                for timeIndex, field in enumerate(dpf.operators.averaging.to_nodal_fc(fields).eval()):
                    boundsMask = field.scoping.ids < nodeMap.size
                    indices = nodeMap[field.scoping.ids[boundsMask]]
                    validMask = indices > -1
                    nodeData[nodeSlice0, indices[validMask], timeIndex] = field.data[boundsMask][validMask].T
                for timeIndex, field in enumerate(dpf.operators.averaging.to_elemental_fc(fields).eval()):
                    boundsMask = field.scoping.ids < elementMap.size
                    indices = elementMap[field.scoping.ids[boundsMask]]
                    validMask = indices > -1
                    centroidData[centroidSlice0, indices[validMask], timeIndex] = field.data[boundsMask][validMask].T
            case _:
                raise NotImplementedError()

    # ------------------------------------------------------------------------------------------------------------------
    #  SAVE TO DISK
    # ------------------------------------------------------------------------------------------------------------------
    print("Saving data to disk...")
    rstzPath = os.path.splitext(rstPath)[0] + ".rstz"
    with open(rstzPath, "wb") as rstz:
        np.savez(rstzPath, **sets, **{
            "__nodes__": nodes,
            "__types__": types,
            "__elements__": elements,
            "__times__": times,
            "__node_data__": nodeData,
            "__centroid_data__": centroidData,
            "__node_headers__": nodeHeaders,
            "__centroid_headers__": centroidHeaders,
        })
    print("Done extracting. Data stored in: " + rstzPath)

if __name__ == "__main__":
    argParser = ArgumentParser()
    argParser.add_argument("--rst", dest="rst", type=os.path.abspath, required=True, help="The RST file path.")
    args = argParser.parse_args()
    main(args.rst)
