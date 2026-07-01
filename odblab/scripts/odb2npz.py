#-----------------------------------------------------------------------------------------------------------------------
# A multiprocessing Python script to extract data from an Abaqus output database (*.odb).
# The extracted data is stored in the corresponding *.odbz file.
# Abaqus must be installed on the system.
#-----------------------------------------------------------------------------------------------------------------------
# Copyright (c) 2026, Carlos Souto and Diego Salamanca
# Contact: csouto@fe.up.pt; diazsdiego@uniovi.es
# License: <LICENSE>
#-----------------------------------------------------------------------------------------------------------------------

# type: ignore

import os
import pickle
import shutil
import tempfile
import odbAccess
import numpy as np
from argparse import ArgumentParser
from collections import OrderedDict
from multiprocessing import Process, Pool, cpu_count
from abaqusConstants import NODAL, ELEMENT_NODAL, CENTROID, INTEGRATION_POINT

def autoUpgradeOdb(odbPath):
    """Auto-upgrades the ODB if required."""
    if odbAccess.isUpgradeRequiredForOdb(upgradeRequiredOdbPath=odbPath):
        print("The ODB is from a previous release of Abaqus. Automatically upgrading the ODB...")
        existingOdbPath = odbPath
        upgradedOdbPath = os.path.splitext(odbPath)[0] + "-upgraded" + os.path.splitext(odbPath)[1]
        oldOdbPath = os.path.splitext(odbPath)[0] + "-old" + os.path.splitext(odbPath)[1]
        odbAccess.upgradeOdb(existingOdbPath=existingOdbPath, upgradedOdbPath=upgradedOdbPath)
        os.rename(existingOdbPath, oldOdbPath)
        os.rename(upgradedOdbPath, existingOdbPath)
        print("The ODB was upgraded successfully.")

def extractMesh(odbPath, tempDir):
    """Unifies and extracts the finite element mesh."""
    odb = None
    try:

        # open database and perform counts
        odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)
        entities = [odb.rootAssembly] + list(odb.rootAssembly.instances.values())
        nodeOffsets, elementOffsets = [0], [0]
        for entity in entities:
            nodeOffsets.append(len(entity.nodes) + nodeOffsets[-1])
            elementOffsets.append(len(entity.elements) + elementOffsets[-1])
        nodeCount, elementCount = nodeOffsets[-1], elementOffsets[-1]

        # initialize storage
        nodes = np.empty(shape=(nodeCount, 3), dtype=np.float32)
        types = np.empty(shape=(elementCount,), dtype="U")
        elements = np.empty(shape=(elementCount, 0), dtype=np.int32)

        # lookup mappings: (entity name, node/element label) -> node/element index
        nodeMap = dict()
        elementMap = dict()

        # entity loop
        for entityIndex, entity in enumerate(entities):
            entityName = entity.name if entity != odb.rootAssembly else "__root__"
            nodeOffset, elementOffset = nodeOffsets[entityIndex], elementOffsets[entityIndex]

            # extract nodes
            for index, node in enumerate(entity.nodes):
                nodeMap[(entityName, node.label)] = nodeOffset + index
                nodes[nodeOffset + index, :] = node.coordinates

            # extract elements
            for index, element in enumerate(entity.elements):
                elementMap[(entityName, element.label)] = elementOffset + index
                connectivity = [nodeMap[(entityName, label)] for label in element.connectivity]
                elementSize, typeLength = len(connectivity), len(element.type)
                if elementSize > elements.shape[1]:
                    elements = np.pad(
                        elements, ((0, 0), (0, elementSize - elements.shape[1])),
                        "constant", constant_values=-1
                    )
                if typeLength > types.dtype.itemsize//np.dtype("U1").itemsize:
                    types = types.astype("U%d" % typeLength)
                elements[elementOffset + index, :elementSize] = connectivity
                types[elementOffset + index] = element.type

        # entity loop (after mappings)
        sets = dict()
        for entityIndex, entity in enumerate(entities):
            entityName = entity.name if entity != odb.rootAssembly else "__root__"

            # extract node/element sets
            for suffix, setAttribute, itemsAttribute, indexMap in (
                ("__node_set__", "nodeSets", "nodes", nodeMap),
                ("__element_set__", "elementSets", "elements", elementMap),
            ):
                if entity == odb.rootAssembly:
                    for setName, entitySet in getattr(entity, setAttribute).items():
                        if setName in (" ALL ELEMENTS", " ALL NODES"): continue
                        sets["%s.\"%s\"" % (suffix, setName)] = np.array(object=sorted(set(
                            indexMap[(instance.name, item.label)]
                            for instance, items in zip(entitySet.instances, getattr(entitySet, itemsAttribute))
                            for item in items
                        )), dtype=np.int32)
                else:
                    for setName, entitySet in getattr(entity, setAttribute).items():
                        if setName in (" ALL ELEMENTS", " ALL NODES"): continue
                        sets["%s.\"%s.%s\"" % (suffix, entityName, setName)] = np.array(object=sorted(set(
                            indexMap[(entityName, item.label)]
                            for item in getattr(entitySet, itemsAttribute)
                        )), dtype=np.int32)

        # save mesh
        np.save(os.path.join(tempDir, "__nodes__.npy"), nodes)
        np.save(os.path.join(tempDir, "__types__.npy"), types)
        np.save(os.path.join(tempDir, "__elements__.npy"), elements)
        np.savez(os.path.join(tempDir, "__sets__.npz"), **sets)

        # save maps
        with open(os.path.join(tempDir, "__mesh_metadata__.pkl"), "wb") as file:
            pickle.dump({"__node_map__": nodeMap, "__element_map__": elementMap}, file)

    finally:
        if odb is not None:
            odb.close()

def extractResultsMetadata(odbPath, tempDir):
    """Extracts the field output metadata."""
    odb = None
    try:
        odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)
        nodeHeaders, centroidHeaders, frameInfo = OrderedDict(), OrderedDict(), OrderedDict()
        for stepName, step in odb.steps.items():
            for frameIndex, frame in enumerate(step.frames):
                time = step.totalTime + frame.frameValue
                if time not in frameInfo:
                    frameInfo[time] = (stepName, frameIndex, time)
                for fieldOutput in frame.fieldOutputs.values():
                    headers = [fieldOutput.name + "." + label for label in fieldOutput.componentLabels]
                    headers = headers or [fieldOutput.name]
                    if fieldOutput.locations[0].position in (NODAL, INTEGRATION_POINT):
                        nodeHeaders.update((header, None) for header in headers)
                    if fieldOutput.locations[0].position in (CENTROID, INTEGRATION_POINT):
                        centroidHeaders.update((header, None) for header in headers)
        nodeHeaders = np.array(list(nodeHeaders.keys()), dtype="U")
        centroidHeaders = np.array(list(centroidHeaders.keys()), dtype="U")
        times = np.sort(np.array([time for _, _, time in frameInfo.values()], dtype=np.float32))
        np.save(os.path.join(tempDir, "__times__.npy"), times)
        np.save(os.path.join(tempDir, "__node_headers__.npy"), nodeHeaders)
        np.save(os.path.join(tempDir, "__centroid_headers__.npy"), centroidHeaders)
        with open(os.path.join(tempDir, "__field_metadata__.pkl"), "wb") as file:
            pickle.dump(file=file, obj={
                "__node_header_map__": {name: index for index, name in enumerate(nodeHeaders)},
                "__centroid_header_map__": {name: index for index, name in enumerate(centroidHeaders)},
                "__frame_info__": sorted(frameInfo.values(), key=lambda x: x[-1])
            })
    finally:
        if odb is not None:
            odb.close()

def extractResultsWorker(args): return extractResults(*args)
def extractResults(odbPath, tempDir, timeIndex, originalPosition, extrapolatedPosition):
    """Extracts the field outputs."""
    odb = None
    try:

        # open database and load data from disk
        odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)
        with open(os.path.join(tempDir, "__mesh_metadata__.pkl"), "rb") as file: meshMetadata = pickle.load(file)
        with open(os.path.join(tempDir, "__field_metadata__.pkl"), "rb") as file: fieldMetadata = pickle.load(file)
        stepName, frameIndex, _ = fieldMetadata["__frame_info__"][timeIndex]
        if extrapolatedPosition == CENTROID:
            indexMap = meshMetadata["__element_map__"]
            headerMap = fieldMetadata["__centroid_header_map__"]
            diskArray = np.load(os.path.join(tempDir, "__centroid_data__.npy"), "r+")
            labelsAttribute = "elementLabels"
        else:
            indexMap = meshMetadata["__node_map__"]
            headerMap = fieldMetadata["__node_header_map__"]
            diskArray = np.load(os.path.join(tempDir, "__node_data__.npy"), "r+")
            labelsAttribute = "nodeLabels"

        # loop field outputs
        for field in odb.steps[stepName].frames[frameIndex].fieldOutputs.values():
            if field.locations[0].position != originalPosition: continue
            if originalPosition != extrapolatedPosition: field = field.getSubset(position=extrapolatedPosition)
            isSmoothingRequired = extrapolatedPosition == ELEMENT_NODAL
            headers = [field.name + "." + label for label in field.componentLabels] or [field.name]

            # pre-allocate arrays
            if isSmoothingRequired:
                matrix = np.zeros(shape=(len(indexMap), len(headers)), dtype=np.float32)
                counts = np.zeros(shape=(matrix.shape[0], 1), dtype=np.int32)
            else:
                matrix = np.full(shape=(len(indexMap), len(headers)), fill_value=np.nan, dtype=np.float32)

            # extract data
            for block in field.bulkDataBlocks:
                entityName = block.instance.name if block.instance else "__root__"
                i = [indexMap[(entityName, label)] for label in getattr(block, labelsAttribute)]
                if not isSmoothingRequired:
                    matrix[i, :] = block.data
                else:
                    np.add.at(matrix, (i, slice(None)), block.data)
                    np.add.at(counts, (i, 0), 1)

            # nodal smoothing/averaging
            if isSmoothingRequired:
                unmappedMask = counts[:, 0] == 0
                counts[unmappedMask] = 1
                matrix /= counts
                matrix[unmappedMask, :] = np.nan

            # save results
            for k, header in enumerate(headers):
                diskArray[headerMap[header], :, timeIndex] = matrix[:, k]

        # done
        diskArray.flush()

    finally:
        if odb is not None:
            odb.close()

def main(odbPath, tempDir, cpus):
    """The main block."""
    autoUpgradeOdb(odbPath)
    print("Extracting data from: " + odbPath)

    # mesh and field metadata extraction
    print("Extracting finite element mesh and field output metadata using %d CPU(s)..." % min(2, cpus))
    if cpus == 1:
        extractMesh(odbPath, tempDir)
        extractResultsMetadata(odbPath, tempDir)
    else:
        extractMeshProcess = Process(target=extractMesh, args=(odbPath, tempDir))
        extractResultsMetadataProcess = Process(target=extractResultsMetadata, args=(odbPath, tempDir))
        extractMeshProcess.start()
        extractResultsMetadataProcess.start()
        extractMeshProcess.join()
        extractResultsMetadataProcess.join()

    # initialize disk storage for result extraction
    print("Initializing field output storage...")
    with open(os.path.join(tempDir, "__mesh_metadata__.pkl"), "rb") as file: meshMetadata = pickle.load(file)
    with open(os.path.join(tempDir, "__field_metadata__.pkl"), "rb") as file: fieldMetadata = pickle.load(file)
    nodeCount = len(meshMetadata["__node_map__"])
    elementCount = len(meshMetadata["__element_map__"])
    nodeHeaderCount = len(fieldMetadata["__node_header_map__"])
    centroidHeaderCount = len(fieldMetadata["__centroid_header_map__"])
    frameCount = len(fieldMetadata["__frame_info__"])
    for file, headerCount, entityCount in (
        ("__node_data__.npy", nodeHeaderCount, nodeCount),
        ("__centroid_data__.npy", centroidHeaderCount, elementCount),
    ):
        diskArray = np.lib.format.open_memmap(
            filename=os.path.join(tempDir, file), mode="w+", dtype=np.float32,
            shape=(headerCount, entityCount, frameCount)
        )
        diskArray.fill(np.nan)
        diskArray.flush()

    # extract field outputs in parallel
    cpuCount = min(cpu_count(), cpus)
    print("Extracting field outputs using %d CPU(s)..." % cpuCount)
    tasks = list()
    for timeIndex in range(frameCount):
        tasks.append((odbPath, tempDir, timeIndex, NODAL, NODAL))
        tasks.append((odbPath, tempDir, timeIndex, CENTROID, CENTROID))
        tasks.append((odbPath, tempDir, timeIndex, INTEGRATION_POINT, CENTROID))
        tasks.append((odbPath, tempDir, timeIndex, INTEGRATION_POINT, ELEMENT_NODAL))
    pool = Pool(processes=cpuCount)
    pool.map(extractResultsWorker, tasks)
    pool.close()
    pool.join()

    # compile temporary files into the final database
    print("Compiling final ODBZ database...")
    odbzPath = os.path.splitext(odbPath)[0] + ".odbz"
    with open(odbzPath, "wb") as odbz:
        data = {
            "__nodes__": np.load(os.path.join(tempDir, "__nodes__.npy"), "r"),
            "__types__": np.load(os.path.join(tempDir, "__types__.npy"), "r"),
            "__elements__": np.load(os.path.join(tempDir, "__elements__.npy"), "r"),
            "__times__": np.load(os.path.join(tempDir, "__times__.npy"), "r"),
            "__node_data__": np.load(os.path.join(tempDir, "__node_data__.npy"), "r"),
            "__centroid_data__": np.load(os.path.join(tempDir, "__centroid_data__.npy"), "r"),
            "__node_headers__": np.load(os.path.join(tempDir, "__node_headers__.npy"), "r"),
            "__centroid_headers__": np.load(os.path.join(tempDir, "__centroid_headers__.npy"), "r"),
        }
        data.update(np.load(os.path.join(tempDir, "__sets__.npz"), "r"))
        np.savez(odbz, **data)

    # done
    print("Done extracting. Data stored in: " + odbzPath)

if __name__ == "__main__":
    tempDir = tempfile.mkdtemp()
    with open("odb2npz.log", "w") as log:
        try:
            argParser = ArgumentParser()
            argParser.add_argument("--odb", dest="odb", type=os.path.abspath, required=True, help="The ODB file path.")
            argParser.add_argument("--cpus", dest="cpus", type=int, default=32, help="Upper process count limit.")
            args = argParser.parse_args()
            main(args.odb, tempDir, max(1, args.cpus))
            log.write("EXIT_SUCCESS\n")
        except Exception as e:
            log.write("EXIT_FAILURE\n")
            log.write("%s: %s\n" % (type(e).__name__, e))
        finally:
            shutil.rmtree(tempDir, ignore_errors=True)
