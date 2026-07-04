import re
import numpy as np
from re import Pattern
from numpy import ndarray as Array
from odblab.core import Database

def _findVectors(database: Database) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Scan database headers to identify and group vector components."""
    nodeVectors: dict[str, dict[str, str]] = {}
    centroidVectors: dict[str, dict[str, str]] = {}
    pattern: Pattern[str] = re.compile(r"^(.*?)\.[a-zA-Z]*([123])$")
    for vectors, headers in (nodeVectors, database.nodeHeaders), (centroidVectors, database.centroidHeaders):
        for header in headers:
            if match := pattern.match(header := str(header)):
                vectors.setdefault(match.group(1), {})[match.group(2)] = header
    return nodeVectors, centroidVectors

def _findTensors(database: Database) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Scan database headers to identify and group tensor components."""
    nodeTensors: dict[str, dict[str, str]] = {}
    centroidTensors: dict[str, dict[str, str]] = {}
    pattern: Pattern[str] = re.compile(r"^(.*?)\.[a-zA-Z]*([0-9]{2})$")
    for tensors, headers in (nodeTensors, database.nodeHeaders), (centroidTensors, database.centroidHeaders):
        for header in headers:
            if match := pattern.match(header := str(header)):
                tensors.setdefault(match.group(1), {})[match.group(2)] = header
    return nodeTensors, centroidTensors

def computeMagnitude(u1: Array, u2: Array, u3: Array | None) -> Array:
    """Compute the element-wise magnitude of a 2D or 3D vector field."""
    if u3 is None: return np.sqrt(u1*u1 + u2*u2)
    else: return np.sqrt(u1*u1 + u2*u2 + u3*u3)

def computePrincipal(*, s11: Array, s22: Array, s33: Array | None, s12: Array, s13: Array | None, s23: Array | None) \
    -> tuple[Array, Array, Array, Array]:
    """Compute the element-wise max., mid., and min. principal tensor values."""
    tensor: Array = np.zeros(shape=(*s11.shape, 3, 3), dtype=s11.dtype)
    tensor[..., 0, 0] = s11
    tensor[..., 1, 1] = s22
    tensor[..., 0, 1] = tensor[..., 1, 0] = s12
    if s33 is not None: tensor[..., 2, 2] = s33
    if s13 is not None: tensor[..., 0, 2] = tensor[..., 2, 0] = s13
    if s23 is not None: tensor[..., 1, 2] = tensor[..., 2, 1] = s23
    validMask: Array = np.isfinite(tensor).all(axis=(-2, -1))
    eigenvalues: Array = np.full(shape=(*s11.shape, 3), fill_value=np.nan, dtype=s11.dtype)
    eigenvalues[validMask] = np.linalg.eigvalsh(tensor[validMask])
    max: Array = eigenvalues[..., 2]
    mid: Array = eigenvalues[..., 1]
    min: Array = eigenvalues[..., 0]
    major: Array = np.where(np.abs(max) > np.abs(min), max, min)
    return max, mid, min, major

def computeEquivalentStress(s1: Array, s2: Array, s3: Array) -> tuple[Array, Array, Array]:
    """Compute the equivalent von Mises, Tresca, and pressure stress based on the provided principal stresses."""
    mises: Array = np.sqrt(0.5*((s1 - s2)**2 + (s2 - s3)**2 + (s3 - s1)**2))
    tresca: Array = s1 - s3
    pressure: Array = -(s1 + s2 + s3)/3
    return mises, tresca, pressure

def autoComputeMagnitude(database: Database) -> None:
    """
    Auto-discover node and centroid vector fields and compute their element-wise magnitude.
    Results are appended to the database, e.g., "U.MAGNITUDE".
    """
    for position, currentHeaders, vectors in zip(
        ("nodes", "centroids"),
        (database.nodeHeaders, database.centroidHeaders),
        _findVectors(database)
    ):
        magnitudes: dict[str, Array] = {}
        for label, components in vectors.items():
            if f"{label}.MAGNITUDE" in currentHeaders: continue
            if "1" not in components or "2" not in components: continue
            u1, u2 = database.get((components["1"], components["2"]), position)
            u3, = database.get((components["3"],), position) if "3" in components else (None,)
            magnitudes[f"{label}.MAGNITUDE"] = computeMagnitude(u1, u2, u3)
        database.add(magnitudes, position)

def autoComputeInvariants(database: Database) -> None:
    """
    Auto-discover node and centroid tensor fields and compute their element-wise invariants.
    Results are appended to the database, e.g., "LE.MAX_PRINCIPAL", "S.MISES".
    """
    for position, currentHeaders, tensors in zip(
        ("nodes", "centroids"),
        (database.nodeHeaders, database.centroidHeaders),
        _findTensors(database)
    ):
        invariants: dict[str, Array] = {}
        for label, components in tensors.items():
            if any(f"{label}.{invariant}" in currentHeaders for invariant in (
                "MAX_PRINCIPAL", "MID_PRINCIPAL", "MIN_PRINCIPAL", "MAJOR_PRINCIPAL",
                "MISES", "TRESCA", "PRESSURE"
            )): continue
            if any(ij not in components for ij in ("11", "22", "12")): continue
            s11, s22, s12 = database.get((components["11"], components["22"], components["12"]), position)
            s33, = database.get((components["33"],), position) if "33" in components else (None,)
            s13, = database.get((components["13"],), position) if "13" in components else (None,)
            s23, = database.get((components["23"],), position) if "23" in components else (None,)
            if label != "S":
                s12 = s12/2
                if s13 is not None: s13 = s13/2
                if s23 is not None: s23 = s23/2
            s1, s2, s3, major = computePrincipal(s11=s11, s22=s22, s33=s33, s12=s12, s13=s13, s23=s23)
            invariants[f"{label}.MAX_PRINCIPAL"] = s1
            invariants[f"{label}.MID_PRINCIPAL"] = s2
            invariants[f"{label}.MIN_PRINCIPAL"] = s3
            invariants[f"{label}.MAJOR_PRINCIPAL"] = major
            if label == "S":
                mises, tresca, pressure = computeEquivalentStress(s1, s2, s3)
                invariants[f"{label}.MISES"] = mises
                invariants[f"{label}.TRESCA"] = tresca
                invariants[f"{label}.PRESSURE"] = pressure
        database.add(invariants, position)
