#-----------------------------------------------------------------------------------------------------------------------
# A multiprocessing Python script to extract data from an Abaqus output database (*.odb).
# The extracted data is stored in the corresponding *.odbz file.
# Abaqus must be installed on the system.
#-----------------------------------------------------------------------------------------------------------------------
# Copyright (c) 2026, Carlos Souto and Diego Salamanca
# Contact: csouto@fe.up.pt; diazsdiego@uniovi.es
# License: https://spdx.org/licenses/GPL-3.0-only.html
#-----------------------------------------------------------------------------------------------------------------------

# type: ignore

import os
import pickle
import shutil
import tempfile
import traceback
import odbAccess
import numpy as np
from argparse import ArgumentParser
from multiprocessing import Process, Pool, cpu_count
from abaqusConstants import NODAL, ELEMENT_NODAL, CENTROID, INTEGRATION_POINT

#-----------------------------------------------------------------------------------------------------------------------

def autoUpgradeOdb(odbPath):
    """Automatically upgrades the ODB if required."""
    if odbAccess.isUpgradeRequiredForOdb(odbPath):
        print("The ODB is from a previous release of Abaqus. Automatically upgrading the ODB...")
        odbRoot, odbExt = os.path.splitext(odbPath)
        upgradedOdbPath = odbRoot + "-upgraded" + odbExt
        oldOdbPath = odbRoot + "-old" + odbExt
        odbAccess.upgradeOdb(existingOdbPath=odbPath, upgradedOdbPath=upgradedOdbPath)
        os.rename(odbPath, oldOdbPath)
        os.rename(upgradedOdbPath, odbPath)
        print("The ODB was upgraded successfully.")

#-----------------------------------------------------------------------------------------------------------------------

def buildIndexLookups(odbPath, tempDir):
    """Builds the label-to-index lookup maps."""

    # helper: build node or element label-to-index lookup map for the given entity (root assembly or part instance)
    def buildMap(entity, attribute, counter):
        items = getattr(entity, attribute)
        map = {item.label: index for index, item in enumerate(items, start=counter)}
        counter += len(map)
        return map, counter

    # open database
    odb = None
    try:
        odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)

        # build index lookup maps for each entity
        nodeCount, elementCount = 0, 0
        nodeLookup, elementLookup = {}, {}
        for entity in [odb.rootAssembly] + list(odb.rootAssembly.instances.values()):
            entityName = entity.name if entity != odb.rootAssembly else "__root__"
            nodeLookup[entityName], nodeCount = buildMap(entity, "nodes", nodeCount)
            elementLookup[entityName], elementCount = buildMap(entity, "elements", elementCount)

        # save index lookup maps
        with open(os.path.join(tempDir, "__mesh_metadata__.pkl"), "wb") as file:
            pickle.dump(file=file, obj={
                "__node_count__": nodeCount, "__element_count__": elementCount,
                "__node_lookup__": nodeLookup, "__element_lookup__": elementLookup,
            })

    # close database
    finally:
        if odb is not None:
            odb.close()

#-----------------------------------------------------------------------------------------------------------------------

def extractMesh(odbPath, tempDir):
    """Unifies and extracts the finite element mesh."""

    # load mesh metadata
    with open(os.path.join(tempDir, "__mesh_metadata__.pkl"), "rb") as file: meshMetadata = pickle.load(file)
    nodeCount, elementCount = meshMetadata["__node_count__"], meshMetadata["__element_count__"]
    nodeLookup, elementLookup = meshMetadata["__node_lookup__"], meshMetadata["__element_lookup__"]

    # open database
    odb = None
    try:
        odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)
        entities = [odb.rootAssembly] + list(odb.rootAssembly.instances.values())

        # pass 1: find max element size and max type length
        maxTypeLength = 0
        maxElementSize = 0
        for entity in entities:
            for element in entity.elements:
                typeLength = len(element.type)
                elementSize = len(element.connectivity)
                if typeLength > maxTypeLength: maxTypeLength = typeLength
                if elementSize > maxElementSize: maxElementSize = elementSize

        # initialize storage
        sets = {}
        nodes = np.zeros(shape=(nodeCount, 3), dtype=np.float32)
        types = np.zeros(shape=(elementCount,), dtype="U%d" % maxTypeLength)
        elements = np.full(shape=(elementCount, maxElementSize), fill_value=-1, dtype=np.int32)

        # entity extraction loop
        for entity in entities:
            entityName = entity.name if entity != odb.rootAssembly else "__root__"
            entityNodeLookup = nodeLookup[entityName]
            entityElementLookup = elementLookup[entityName]

            # extract nodes
            for node in entity.nodes:
                nodeIndex = entityNodeLookup[node.label]
                nodes[nodeIndex, :] = node.coordinates

            # extract elements
            for element in entity.elements:
                elementIndex = entityElementLookup[element.label]
                nodeIndices = [entityNodeLookup[nodeLabel] for nodeLabel in element.connectivity]
                elements[elementIndex, :len(nodeIndices)] = nodeIndices
                types[elementIndex] = element.type

            # extract node/element sets
            for prefix, itemSets, itemsAttribute, itemLookup in (
                ("__node_set__", entity.nodeSets, "nodes", nodeLookup),
                ("__element_set__", entity.elementSets, "elements", elementLookup),
            ):
                for setName, itemSet in itemSets.items():
                    if setName.startswith(" "): continue # skip internal sets
                    if entity == odb.rootAssembly:
                        setKey = "%s.\"%s\"" % (prefix, setName)
                        items = [item for sequence in getattr(itemSet, itemsAttribute) for item in sequence]
                    else:
                        setKey = "%s.\"%s.%s\"" % (prefix, entityName, setName)
                        items = getattr(itemSet, itemsAttribute)
                    itemIndices = [itemLookup[item.instanceName or "__root__"][item.label] for item in items]
                    sets[setKey] = np.unique(np.array(itemIndices, dtype=np.int32)) # np.unique also sorts

        # save mesh
        np.save(os.path.join(tempDir, "__nodes__.npy"), nodes)
        np.save(os.path.join(tempDir, "__types__.npy"), types)
        np.save(os.path.join(tempDir, "__elements__.npy"), elements)
        np.savez(os.path.join(tempDir, "__sets__.npz"), **sets)

    # close database
    finally:
        if odb is not None:
            odb.close()

#-----------------------------------------------------------------------------------------------------------------------

def getHeaders(fieldOutput, componentLabels=None):
    """Helper function that returns the variable names (headers) from the specified field output."""
    componentLabels = componentLabels or fieldOutput.componentLabels
    if fieldOutput.name.startswith(("COPEN", "CPRESS", "CSHEAR", "CSLIP", "CSTATUS")): # special case
        return [".".join(fieldOutput.name.split())]
    elif componentLabels:
        return [fieldOutput.name + "." + label for label in componentLabels]
    else:
        return [fieldOutput.name]

#-----------------------------------------------------------------------------------------------------------------------

def extractResultsMetadata(odbPath, tempDir):
    """Extracts the field output metadata."""

    # open database
    odb = None
    try:
        odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)

        # get unique frames and build header to index mappings
        uniqueFrames = {}
        nodeHeaderCount, nodeHeaderMap = 0, {}
        centroidHeaderCount, centroidHeaderMap = 0, {}
        for stepName, step in odb.steps.items():
            for frameIndex, frame in enumerate(step.frames):
                time = step.totalTime + frame.frameValue
                if time not in uniqueFrames:
                    uniqueFrames[time] = (stepName, frameIndex)
                for fieldOutput in frame.fieldOutputs.values():
                    for header in getHeaders(fieldOutput):
                        if fieldOutput.locations[0].position in (NODAL, INTEGRATION_POINT):
                            if header not in nodeHeaderMap:
                                nodeHeaderMap[header] = nodeHeaderCount
                                nodeHeaderCount += 1
                        if fieldOutput.locations[0].position in (CENTROID, INTEGRATION_POINT):
                            if header not in centroidHeaderMap:
                                centroidHeaderMap[header] = centroidHeaderCount
                                centroidHeaderCount += 1

        # save data
        np.save(os.path.join(tempDir, "__times__.npy"), np.array(sorted(uniqueFrames.keys()), dtype=np.float32))
        np.save(os.path.join(tempDir, "__node_headers__.npy"), np.array(list(nodeHeaderMap.keys()), dtype="U"))
        np.save(os.path.join(tempDir, "__centroid_headers__.npy"), np.array(list(centroidHeaderMap.keys()), dtype="U"))
        with open(os.path.join(tempDir, "__field_metadata__.pkl"), "wb") as file:
            pickle.dump(file=file, obj={
                "__node_header_map__": nodeHeaderMap,
                "__centroid_header_map__": centroidHeaderMap,
                "__unique_frames__": [uniqueFrames[time] for time in sorted(uniqueFrames.keys())]
            })

    # close database
    finally:
        if odb is not None:
            odb.close()

#-----------------------------------------------------------------------------------------------------------------------

def extractResults(odbPath, tempDir, timeIndex):
    """Extracts the field outputs."""

    # load metadata and disk arrays
    with open(os.path.join(tempDir, "__mesh_metadata__.pkl"), "rb") as file: meshMetadata = pickle.load(file)
    with open(os.path.join(tempDir, "__field_metadata__.pkl"), "rb") as file: fieldMetadata = pickle.load(file)
    diskArrays = {
        "__node_data__": np.load(os.path.join(tempDir, "__node_data__.npy"), "r+"),
        "__centroid_data__": np.load(os.path.join(tempDir, "__centroid_data__.npy"), "r+"),
    }

    # open database
    odb = None
    try:
        odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)

        # loop field outputs
        stepName, frameIndex = fieldMetadata["__unique_frames__"][timeIndex]
        for fieldOutput in odb.steps[stepName].frames[frameIndex].fieldOutputs.values():
            fieldHeaders = getHeaders(fieldOutput)

            # determine original and extrapolated positions
            originalPosition = fieldOutput.locations[0].position
            if originalPosition == NODAL: extrapolatedPositions = (NODAL,)
            elif originalPosition == CENTROID: extrapolatedPositions = (CENTROID,)
            elif originalPosition == INTEGRATION_POINT: extrapolatedPositions = (CENTROID, ELEMENT_NODAL)
            else: continue

            # for each extrapolated position
            for extrapolatedPosition in extrapolatedPositions:
                if extrapolatedPosition == CENTROID:
                    labelsAttribute = "elementLabels"
                    itemCount = meshMetadata["__element_count__"]
                    itemLookup = meshMetadata["__element_lookup__"]
                    headerMap = fieldMetadata["__centroid_header_map__"]
                    diskArray = diskArrays["__centroid_data__"]
                else:
                    labelsAttribute = "nodeLabels"
                    itemCount = meshMetadata["__node_count__"]
                    itemLookup = meshMetadata["__node_lookup__"]
                    headerMap = fieldMetadata["__node_header_map__"]
                    diskArray = diskArrays["__node_data__"]

                # determine if nodal smoothing is required
                isSmoothingRequired = extrapolatedPosition == ELEMENT_NODAL

                # extrapolation
                if originalPosition == extrapolatedPosition: extrapolatedFieldOutput = fieldOutput
                else: extrapolatedFieldOutput = fieldOutput.getSubset(position=extrapolatedPosition)

                # pre-allocate arrays
                if isSmoothingRequired:
                    matrix = np.zeros(shape=(itemCount, len(fieldHeaders)), dtype=np.float32)
                    counts = np.zeros(shape=(itemCount, 1), dtype=np.int32)
                else:
                    matrix = np.full(shape=(itemCount, len(fieldHeaders)), fill_value=np.nan, dtype=np.float32)

                # extract data by block
                for block in extrapolatedFieldOutput.bulkDataBlocks:
                    blockHeaders = getHeaders(fieldOutput, block.componentLabels)
                    entityName = block.instance.name if block.instance else "__root__"
                    itemIndexMap = itemLookup[entityName]
                    i = [itemIndexMap[label] for label in getattr(block, labelsAttribute)]
                    j_rhs = [index for index, header in enumerate(blockHeaders) if header in fieldHeaders]
                    j_lhs = [fieldHeaders.index(header) for header in blockHeaders if header in fieldHeaders]
                    if not isSmoothingRequired:
                        matrix[np.ix_(i, j_lhs)] = block.data[:, j_rhs]
                    else:
                        np.add.at(matrix, np.ix_(i, j_lhs), block.data[:, j_rhs])
                        np.add.at(counts, (i, 0), 1)

                # nodal smoothing/averaging
                if isSmoothingRequired:
                    mappedMask = counts[:, 0] > 0
                    matrix[mappedMask] /= counts[mappedMask]
                    matrix[~mappedMask] = np.nan

                # save results
                for k, header in enumerate(fieldHeaders):
                    diskArray[headerMap[header], :, timeIndex] = matrix[:, k]

        # done
        for diskArray in diskArrays.values():
            diskArray.flush()

    # close database
    finally:
        if odb is not None:
            odb.close()

#-----------------------------------------------------------------------------------------------------------------------

def main(odbPath, tempDir, cpus):
    """The main block."""
    autoUpgradeOdb(odbPath)
    print("Extracting data from: " + odbPath)

    # extract metadata
    cpuCount = min(2, cpus)
    print("Extracting metadata using %d CPU(s)..." % cpuCount)
    tasks = [
        (buildIndexLookups, (odbPath, tempDir)),
        (extractResultsMetadata, (odbPath, tempDir)),
    ]
    pool = Pool(processes=cpuCount)
    pool.map(worker, tasks)
    pool.close()
    pool.join()

    # initialize disk storage for result extraction
    print("Initializing field output storage...")
    with open(os.path.join(tempDir, "__mesh_metadata__.pkl"), "rb") as file: meshMetadata = pickle.load(file)
    with open(os.path.join(tempDir, "__field_metadata__.pkl"), "rb") as file: fieldMetadata = pickle.load(file)
    nodeCount = meshMetadata["__node_count__"]
    elementCount = meshMetadata["__element_count__"]
    frameCount = len(fieldMetadata["__unique_frames__"])
    nodeHeaderCount = len(fieldMetadata["__node_header_map__"])
    centroidHeaderCount = len(fieldMetadata["__centroid_header_map__"])
    for file, headerCount, itemCount in (
        ("__node_data__.npy", nodeHeaderCount, nodeCount),
        ("__centroid_data__.npy", centroidHeaderCount, elementCount),
    ):
        diskArray = np.lib.format.open_memmap(
            filename=os.path.join(tempDir, file), mode="w+", dtype=np.float32,
            shape=(headerCount, itemCount, frameCount)
        )
        diskArray.fill(np.nan)
        diskArray.flush()

    # extract data
    cpuCount = min(cpu_count(), cpus)
    print("Extracting data using %d CPU(s)..." % cpuCount)
    tasks = [(extractResults, (odbPath, tempDir, timeIndex)) for timeIndex in range(frameCount)]
    tasks += [(extractMesh, (odbPath, tempDir))]
    pool = Pool(processes=cpuCount)
    pool.map(worker, tasks)
    pool.close()
    pool.join()

    # compile temporary files into the final database
    print("Compiling final ODBZ database...")
    odbzPath = os.path.splitext(odbPath)[0] + ".odbz"
    with open(odbzPath, "wb") as odbz:
        data = {
            fileName: np.load(os.path.join(tempDir, fileName + ".npy"), "r")
            for fileName in (
                "__nodes__", "__elements__", "__types__", "__times__",
                "__node_headers__", "__node_data__", "__centroid_headers__", "__centroid_data__"
            )
        }
        data.update(np.load(os.path.join(tempDir, "__sets__.npz"), "r"))
        np.savez(odbz, **data)

    # done
    print("Done extracting. Data stored in: " + odbzPath)

#-----------------------------------------------------------------------------------------------------------------------

def worker(task): return task[0](*task[1])

if __name__ == "__main__":
    tempDir = tempfile.mkdtemp()
    with open("odb2odbz.log", "w") as log:
        try:
            argParser = ArgumentParser()
            argParser.add_argument("--odb", dest="odb", type=os.path.abspath, required=True, help="The ODB file path.")
            argParser.add_argument("--cpus", dest="cpus", type=int, default=32, help="Upper process count limit.")
            args = argParser.parse_args()
            main(args.odb, tempDir, max(1, args.cpus))
            log.write("EXIT_SUCCESS\n")
        except Exception as e:
            log.write("EXIT_FAILURE\n")
            log.write("%s: %s\n\n" % (type(e).__name__, e))
            log.write(traceback.format_exc())
        finally:
            shutil.rmtree(tempDir, ignore_errors=True)
