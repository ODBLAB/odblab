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
                sets[f"__node_set__.\"{name}\""] = np.unique(nodeMap[scoping.ids]).astype(np.int32, copy=False)
            case dpf.locations.elemental:
                sets[f"__element_set__.\"{name}\""] = np.unique(elementMap[scoping.ids]).astype(np.int32, copy=False)
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
            case "scalar": headers = [name]
            case "vector": headers = [f"{name}.{name}{x}" for x in ("1", "2", "3")]
            case "symmatrix": headers = [f"{name}.{name}{xy}" for xy in ("11", "22", "33", "12", "23", "13")]
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
                    nodeData[slice0, nodeMap[field.scoping.ids], timeIndex] = field.data.T
            case dpf.locations.elemental:
                slice0 = slice(centroidFieldOffsets[i], centroidFieldOffsets[i] + metadata.n_components)
                for timeIndex, field in enumerate(fields):
                    centroidData[slice0, elementMap[field.scoping.ids], timeIndex] = field.data.T
            case dpf.locations.elemental_nodal:
                nodeSlice0 = slice(nodeFieldOffsets[i], nodeFieldOffsets[i] + metadata.n_components)
                centroidSlice0 = slice(centroidFieldOffsets[i], centroidFieldOffsets[i] + metadata.n_components)
                for timeIndex, field in enumerate(dpf.operators.averaging.to_nodal_fc(fields).eval()):
                    nodeData[nodeSlice0, nodeMap[field.scoping.ids], timeIndex] = field.data.T
                for timeIndex, field in enumerate(dpf.operators.averaging.to_elemental_fc(fields).eval()):
                    centroidData[centroidSlice0, elementMap[field.scoping.ids], timeIndex] = field.data.T
            case _:
                raise NotImplementedError()

    # ------------------------------------------------------------------------------------------------------------------
    #  SAVE TO DISK
    # ------------------------------------------------------------------------------------------------------------------
    print("Saving data to disk...")
    rstzPath = os.path.splitext(rstPath)[0] + ".rstz"
    with open(rstzPath, "wb") as rstz:
        np.savez(
            file=rstz,
            __nodes__=np.asarray(nodes, dtype=np.float32),
            __types__=np.asarray(types, dtype="U"),
            __elements__=np.asarray(elements, dtype=np.int32),
            __times__=np.asarray(times, dtype=np.float32),
            __node_headers__=np.asarray(nodeHeaders, dtype="U"),
            __centroid_headers__=np.asarray(centroidHeaders, dtype="U"),
            __node_data__=np.asarray(nodeData, dtype=np.float32),
            __centroid_data__=np.asarray(centroidData, dtype=np.float32),
            **sets
        )
    print("Done extracting. Data stored in: " + rstzPath)

if __name__ == "__main__":
    argParser = ArgumentParser()
    argParser.add_argument("--rst", dest="rst", type=os.path.abspath, required=True, help="The RST file path.")
    args = argParser.parse_args()
    main(args.rst)
