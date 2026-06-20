#-----------------------------------------------------------------------------------------------------------------------
# A multiprocessing Python script to extract data from an Abaqus output database (*.odb).
# The extracted data is stored in the corresponding *.npz file.
# Abaqus must be installed on the system.
#-----------------------------------------------------------------------------------------------------------------------
# Copyright (c) 2026, Carlos Souto and Diego Salamanca
# Contact: csouto@fe.up.pt; diazsdiego@uniovi.es
# License: <LICENSE>
#-----------------------------------------------------------------------------------------------------------------------

# type: ignore

import os
import odbAccess
import numpy as np
import multiprocessing
from argparse import ArgumentParser
from collections import OrderedDict
from itertools import accumulate, chain
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

def extractMesh(odbPath):
    """Unifies and extracts the finite element mesh."""
    odb = None
    try:

        # open database and perform counts
        odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)
        entities = [odb.rootAssembly] + list(odb.rootAssembly.instances.values())
        nodeOffsets = [0]
        elementOffsets = [0]
        for entity in entities:
            nodeOffsets.append(len(entity.nodes) + nodeOffsets[-1])
            elementOffsets.append(len(entity.elements) + elementOffsets[-1])
        nodeCount = nodeOffsets[-1]
        elementCount = elementOffsets[-1]

        # initialize storage
        mesh = dict()
        nodes = mesh.setdefault("__nodes__", np.empty(shape=(nodeCount, 3), dtype=np.float32))
        elements = mesh.setdefault("__elements__", np.full(shape=(elementCount, 20), fill_value=-1, dtype=np.int32))
        types = mesh.setdefault("__types__", np.empty(shape=(elementCount,), dtype="S16"))

        # lookup mappings: (entity name, node/element label) -> node/element index
        nodeMap = dict()
        elementMap = dict()

        # entity loop
        for entityIndex, entity in enumerate(entities):
            entityName = entity.name if entity != odb.rootAssembly else "__root__"
            nodeOffset = nodeOffsets[entityIndex]
            elementOffset = elementOffsets[entityIndex]

            # extract nodes
            for index, node in enumerate(entity.nodes):
                nodeMap[(entityName, node.label)] = nodeOffset + index
                nodes[nodeOffset + index, :] = node.coordinates

            # extract elements
            for index, element in enumerate(entity.elements):
                elementMap[(entityName, element.label)] = elementOffset + index
                connectivity = [nodeMap[(entityName, label)] for label in element.connectivity]
                elements[elementOffset + index, :len(connectivity)] = connectivity
                types[elementOffset + index] = element.type

        # entity loop (after mappings)
        for entityIndex, entity in enumerate(entities):
            entityName = entity.name if entity != odb.rootAssembly else "__root__"

            # extract node sets
            if entity == odb.rootAssembly:
                for setName, nodeSet in entity.nodeSets.items():
                    mesh["__node_set__.\"%s\"" % setName] = np.array(object=sorted(set(
                        nodeMap[(instance.name, node.label)]
                        for instance, nodes in zip(nodeSet.instances, nodeSet.nodes)
                        for node in nodes
                    )), dtype=np.int32)
            else:
                for setName, nodeSet in entity.nodeSets.items():
                    mesh["__node_set__.\"%s.%s\"" % (entityName, setName)] = np.array(object=sorted(set(
                        nodeMap[(entityName, node.label)]
                        for node in nodeSet.nodes
                    )), dtype=np.int32)

            # extract element sets
            if entity == odb.rootAssembly:
                for setName, elementSet in entity.elementSets.items():
                    mesh["__element_set__.\"%s\"" % setName] = np.array(object=sorted(set(
                        elementMap[(instance.name, element.label)]
                        for instance, elements in zip(elementSet.instances, elementSet.elements)
                        for element in elements
                    )), dtype=np.int32)
            else:
                for setName, elementSet in entity.elementSets.items():
                    mesh["__element_set__.\"%s.%s\"" % (entityName, setName)] = np.array(object=sorted(set(
                        elementMap[(entityName, element.label)]
                        for element in elementSet.elements
                    )), dtype=np.int32)

        # done
        return mesh, nodeMap, elementMap

    finally:
        if odb is not None:
            odb.close()

def extractResults(fieldOutputs, originalPosition, extrapolatedPosition, labelMap):
    """Extracts the field outputs."""

    # loop field outputs
    headers = list()
    results = list()
    for fieldOutput in fieldOutputs:
        if fieldOutput.locations[0].position != originalPosition: continue

        # detect if smoothing is required
        smooth = originalPosition == INTEGRATION_POINT and extrapolatedPosition == ELEMENT_NODAL

        # compute invariants before extrapolation
        invariants = [fieldOutput.getScalarField(invariant=inv) for inv in fieldOutput.validInvariants]
        fields = [fieldOutput] + invariants

        # interpolate/extrapolate
        if originalPosition != extrapolatedPosition:
            fields = [field.getSubset(position=extrapolatedPosition) for field in fields]

        # generate column headers
        variables = [
            fieldOutput.name + "." + label
            for label in list(fieldOutput.componentLabels) + [inv.name for inv in fieldOutput.validInvariants]
        ] or [fieldOutput.name]

        # pre-allocate arrays
        matrix = np.zeros(shape=(len(labelMap), len(variables)), dtype=np.float32)
        if smooth: counts = np.zeros(shape=(matrix.shape[0], 1), dtype=np.int32)

        # extract data
        columnIndex = 0
        for field in fields:
            columnCount = len(field.componentLabels) if field.componentLabels else 1
            for block in field.bulkDataBlocks:
                entityName = block.instance.name if block.instance else "__root__"
                labels = block.elementLabels if extrapolatedPosition == CENTROID else block.nodeLabels
                rowIndices = [labelMap[(entityName, label)] for label in labels]
                if not smooth:
                    matrix[rowIndices, columnIndex : columnIndex + columnCount] = block.data
                else:
                    np.add.at(matrix[:, columnIndex : columnIndex + columnCount], rowIndices, block.data)
                    if columnIndex == 0: np.add.at(counts[:, 0], rowIndices, 1)
            columnIndex += columnCount

        # nodal smoothing/averaging
        if smooth:
            counts[counts == 0] = 1
            matrix /= counts

        # store results
        results.append(matrix)
        headers.extend(variables)

    # done
    if not results: return None
    else: return np.concatenate(results, axis=1), np.array(headers, dtype="S24")

def extractFrameWorker(args): return extractFrame(*args)
def extractFrame(odbPath, stepName, frameIndex, nodeMap, elementMap):
    """Extracts the full step frame."""
    odb = None
    try:

        # open database
        odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)
        step = odb.steps[stepName]
        frame = step.frames[frameIndex]
        fieldOutputs = frame.fieldOutputs.values()
        data = dict()
        data["__time__"] = step.totalTime + frame.frameValue

        # extract centroid data
        centroidData = extractResults(fieldOutputs, INTEGRATION_POINT, CENTROID, elementMap)
        if centroidData:
            data["__centroid_data__"] = centroidData[0]
            data["__centroid_headers__"] = centroidData[1]

        # extract node data
        nodeData = extractResults(fieldOutputs, NODAL, NODAL, nodeMap)
        elementNodeData = extractResults(fieldOutputs, INTEGRATION_POINT, ELEMENT_NODAL, nodeMap)
        if nodeData or elementNodeData:
            if nodeData and elementNodeData:
                nodeData = np.concatenate((nodeData[0], elementNodeData[0]), axis=1), \
                    np.concatenate((nodeData[1], elementNodeData[1]), axis=0)
            else:
                nodeData = nodeData or elementNodeData
            data["__node_data__"] = nodeData[0]
            data["__node_headers__"] = nodeData[1]

        # done
        return data

    finally:
        if odb is not None:
            odb.close()

def mergeResults(results, nodeMap, elementMap):
    """Merges the frame-based results into a single array."""

    # build value to index mappings
    timeMap = OrderedDict()
    nodeHeaderMap = OrderedDict()
    centroidHeaderMap = OrderedDict()
    for resultBlock in results:
        time = resultBlock["__time__"]
        if time not in timeMap: timeMap[time] = len(timeMap)
        for nodeHeader in resultBlock.get("__node_headers__", list()):
            if nodeHeader not in nodeHeaderMap: nodeHeaderMap[nodeHeader] = len(nodeHeaderMap)
        for centroidHeader in resultBlock.get("__centroid_headers__", list()):
            if centroidHeader not in centroidHeaderMap: centroidHeaderMap[centroidHeader] = len(centroidHeaderMap)

    # merge data
    mergedNodeData = np.zeros(shape=(len(nodeHeaderMap), len(nodeMap), len(timeMap)), dtype=np.float32)
    mergedCentroidData = np.zeros(shape=(len(centroidHeaderMap), len(elementMap), len(timeMap)), dtype=np.float32)
    for resultBlock in results:
        timeIndex = timeMap[resultBlock["__time__"]]
        if "__node_data__" in resultBlock:
            headerIndices = [nodeHeaderMap[header] for header in resultBlock["__node_headers__"]]
            mergedNodeData[headerIndices, :, timeIndex] = resultBlock["__node_data__"].T
        if "__centroid_data__" in resultBlock:
            headerIndices = [centroidHeaderMap[header] for header in resultBlock["__centroid_headers__"]]
            mergedCentroidData[headerIndices, :, timeIndex] = resultBlock["__centroid_data__"].T

    # done
    return {
        "__times__": np.array(object=list(timeMap.keys()), dtype=np.float32),
        "__node_headers__": np.array(object=list(nodeHeaderMap.keys()), dtype="S24"),
        "__centroid_headers__": np.array(object=list(centroidHeaderMap.keys()), dtype="S24"),
        "__node_data__": mergedNodeData,
        "__centroid_data__": mergedCentroidData,
    }

def main(odbPath):
    """The main block."""
    autoUpgradeOdb(odbPath)
    print("Extracting data from: " + odbPath)

    # extract mesh
    print("Extracting finite element mesh...")
    data, nodeMap, elementMap = extractMesh(odbPath)

    # prepare parallel workload
    cpuCount = multiprocessing.cpu_count()
    odb = odbAccess.openOdb(path=odbPath, readOnly=True, readInternalSets=False)
    tasks = [
        (odbPath, stepName, frameIndex, nodeMap, elementMap)
        for stepName, step in odb.steps.items()
        for frameIndex in range(len(step.frames))
    ]
    odb.close()

    # extract field outputs in parallel
    print("Extracting field outputs using %d CPU(s)..." % cpuCount)
    pool = multiprocessing.Pool(processes=cpuCount)
    results = pool.map(extractFrameWorker, tasks)
    pool.close()
    pool.join()

    # merge and write to disk
    print("Saving data to disk...")
    data.update(mergeResults(results, nodeMap, elementMap))
    odbzPath = os.path.splitext(odbPath)[0] + ".odbz"
    with open(odbzPath, "wb") as odbz: np.savez(odbz, allow_pickle=False, **data)

    # done
    print("Done extracting. Data stored in: " + odbzPath)

if __name__ == "__main__":
    with open("odb2npz.log", "w") as log:
        try:
            argParser = ArgumentParser()
            argParser.add_argument("--odb", dest="odb", type=os.path.abspath, required=True, help="The ODB file path.")
            args = argParser.parse_args()
            main(args.odb)
            log.write("EXIT_SUCCESS\n")
        except Exception as e:
            log.write("EXIT_FAILURE\n")
            log.write("%s: %s\n" % (type(e).__name__, e))
