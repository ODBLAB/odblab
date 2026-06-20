import subprocess
import numpy as np
from pathlib import Path
from typing import NamedTuple
from numpy.ma import MaskedArray
from numpy import ndarray as Array
from importlib import resources

class Database(NamedTuple):
    """
    A data container for extracted finite element analysis mesh and results.
    This container holds the finite element mesh, node/element sets, and temporal field output data.
    """

    nodes: Array
    """
    Array of (x, y, z) nodal coordinates.
    Shape: `(n, 3)`, where `n` is the total number of nodes.
    """

    elements: MaskedArray
    """
    Masked array of element connectivities. Padded with -1 for elements with fewer than the maximum number of nodes.
    Shape: `(m, n)`, where `m` is the total number of elements and `n` is the maximum number of element nodes.
    """

    types: Array
    """
    Array of element type identifiers.
    Shape: `(n,)`, where `n` is the total number of elements.
    """

    nodeSets: dict[str, Array]
    """Maps node set names to their corresponding 1D array of node indices."""

    elementSets: dict[str, Array]
    """Maps element set names to their corresponding 1D array of element indices."""

    times: Array
    """
    Array of available frame times/frequencies.
    Shape: `(n,)`, where `n` is the number of frames.
    """

    nodeData: Array
    """
    Array of node field outputs.
    Shape: `(m, n, k)`, where `m` is the number of node variables, `n` is the number of nodes, and `k` is the number of
    frames.
    """

    centroidData: Array
    """
    Array of element/centroid field outputs.
    Shape: `(m, n, k)`, where `m` is the number of element/centroid variables, `n` is the number of elements/centroids,
    and `k` is the number of frames.
    """

    nodeHeaders: Array
    """Names of the extracted node variables corresponding to the first dimension of `nodeData`."""

    centroidHeaders: Array
    """Names of the extracted element/centroid variables corresponding to the first dimension of `centroidData`."""

def _loadNpz(npzPath: str | Path) -> Database:
    """Loads the requested *.npz file."""
    with np.load(npzPath) as data:
        nodes: Array = data["__nodes__"]
        types: Array = data["__types__"].astype("U")
        elements: MaskedArray = np.ma.array(data=data["__elements__"], mask=data["__elements__"] < 0, fill_value=-1)
        nodeSets: dict[str, Array] = {
            key.removeprefix("__node_set__.")[1:-1]: data[key]
            for key in data.files if key.startswith("__node_set__")
        }
        elementSets: dict[str, Array] = {
            key.removeprefix("__element_set__.")[1:-1]: data[key]
            for key in data.files if key.startswith("__element_set__")
        }
        times: Array = data["__times__"]
        nodeData: Array = data["__node_data__"]
        centroidData: Array = data["__centroid_data__"]
        nodeHeaders: Array = data["__node_headers__"].astype("U")
        centroidHeaders: Array = data["__centroid_headers__"].astype("U")
        return Database(
            nodes, elements, types, nodeSets, elementSets,
            times, nodeData, centroidData, nodeHeaders, centroidHeaders
        )

def _loadOdb(odbPath: str | Path) -> Database:
    """Loads the requested *.odb file."""
    if not isinstance(odbPath, Path): odbPath = Path(odbPath)
    odbzPath: Path = odbPath.with_suffix(".odbz")
    if odbPath.exists() and odbzPath.exists() and odbzPath.stat().st_mtime > odbPath.stat().st_mtime:
        print("Using cached ODBZ database.")
    else:
        print("ODBZ database not found or outdated. Converting ODB to ODBZ...")
        script: str = str(resources.files("odblab.scripts") / "odb2npz.py")
        if subprocess.run(("abaqus", "python", script, "--odb", str(odbPath)), shell=True, check=True).returncode:
            raise RuntimeError("abaqus command not found; abaqus must be installed on the system")
        with open("odb2npz.log", "r") as log:
            if log.readline().strip() != "EXIT_SUCCESS":
                raise RuntimeError("error in 'odb2npz.py'\n  " + log.readline().strip())
    return _loadNpz(odbzPath)

def load(filePath: str | Path) -> Database:
    """Loads the requested finite element analysis database file."""
    if not isinstance(filePath, Path): filePath = Path(filePath)
    filePath = filePath.resolve()
    if not filePath.exists(): raise FileNotFoundError(filePath)
    match filePath.suffix.lower():
        case ".odbz": return _loadNpz(filePath)
        case ".odb": return _loadOdb(filePath)
        case _: raise ValueError(f"unexpected file extension '{filePath.suffix}': {filePath}")
