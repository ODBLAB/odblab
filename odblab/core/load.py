import sys
import subprocess
import numpy as np
from pathlib import Path
from numpy.ma import MaskedArray
from numpy import ndarray as Array
from importlib import resources
from odblab.core import Database, autoComputeMagnitude, autoComputeInvariants

def _loadNpz(npzPath: str | Path, autoComputeAllInvariants: bool = False) -> Database:
    """Loads the requested *.npz file."""
    if not isinstance(npzPath, Path): npzPath = Path(npzPath)
    npzPath = npzPath.resolve()
    with np.load(npzPath) as data:
        nodes: Array = data["__nodes__"]
        types: Array = data["__types__"]
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
        nodeHeaders: Array = data["__node_headers__"]
        centroidHeaders: Array = data["__centroid_headers__"]
        database: Database = Database(
            nodes, elements, types, nodeSets, elementSets,
            times, nodeHeaders, centroidHeaders, nodeData, centroidData,
            str(npzPath)
        )
        if autoComputeAllInvariants:
            print("Computing invariants...")
            autoComputeMagnitude(database)
            autoComputeInvariants(database)
            database.save()
            print("Database updated with invariants.")
        return database

def _loadOdb(odbPath: str | Path, cpus: int | None = None) -> Database:
    """Loads the requested *.odb file."""
    if not isinstance(odbPath, Path): odbPath = Path(odbPath)
    odbPath = odbPath.resolve()
    odbzPath: Path = odbPath.with_suffix(".odbz")
    autoComputeAllInvariants: bool = True
    if odbPath.exists() and odbzPath.exists() and odbzPath.stat().st_mtime > odbPath.stat().st_mtime:
        print("Using cached ODBZ database.")
        autoComputeAllInvariants = False
    else:
        print("ODBZ database not found or outdated. Converting ODB to ODBZ...")
        script: str = str(resources.files("odblab.scripts") / "odb2npz.py")
        args: list[str] = ["abaqus", "python", script, "--odb", str(odbPath)]
        if cpus is not None: args += ["--cpus", str(cpus)]
        if subprocess.run(args, shell=True, check=True).returncode:
            raise RuntimeError("abaqus command not found; abaqus must be installed on the system")
        with open("odb2npz.log", "r") as log:
            if log.readline().strip() != "EXIT_SUCCESS":
                raise RuntimeError("error in 'odb2npz.py'\n  " + log.readline().strip())
    return _loadNpz(odbzPath, autoComputeAllInvariants)

def _loadRst(rstPath: str | Path) -> Database:
    """Loads the requested *.rst file."""
    if not isinstance(rstPath, Path): rstPath = Path(rstPath)
    rstPath = rstPath.resolve()
    rstzPath: Path = rstPath.with_suffix(".rstz")
    autoComputeAllInvariants: bool = True
    if rstPath.exists() and rstzPath.exists() and rstzPath.stat().st_mtime > rstPath.stat().st_mtime:
        print("Using cached RSTZ database.")
        autoComputeAllInvariants = False
    else:
        print("RSTZ database not found or outdated. Converting RST to RSTZ...")
        script: str = str(resources.files("odblab.scripts") / "rst2npz.py")
        subprocess.run((sys.executable, script, "--rst", str(rstPath)), shell=True, check=True)
    return _loadNpz(rstzPath, autoComputeAllInvariants)

def load(filePath: str | Path, cpus: int | None = None) -> Database:
    """Loads the requested finite element analysis database file."""
    if not isinstance(filePath, Path): filePath = Path(filePath)
    filePath = filePath.resolve()
    if not filePath.exists(): raise FileNotFoundError(filePath)
    match filePath.suffix.lower():
        case ".odbz" | ".rstz": return _loadNpz(filePath)
        case ".odb": return _loadOdb(filePath, cpus)
        case ".rst": return _loadRst(filePath)
        case _: raise ValueError(f"unexpected file extension '{filePath.suffix}': {filePath}")
