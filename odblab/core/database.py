import os
import numpy as np
from numpy import ndarray as Array
from numpy.ma import MaskedArray
from dataclasses import dataclass
from collections.abc import Mapping, Collection, Callable
from typing import Literal, overload

@dataclass(frozen=True)
class Database:
    """
    A data container for extracted finite element analysis mesh and results.
    This container holds the finite element mesh, node/element sets, and temporal field output data.

    Notes
    -----
    Do not instantiate this class directly. Use `odblab.load` instead.
    """
    nodes: Array
    elements: MaskedArray
    types: Array
    nodeSets: dict[str, Array]
    elementSets: dict[str, Array]
    times: Array
    nodeHeaders: Array
    centroidHeaders: Array
    nodeData: Array
    centroidData: Array
    path: str

    def __post_init__(self) -> None:
        """Post dataclass object initialization."""
        for array in (
            self.nodes, self.elements, self.types, self.times, self.nodeHeaders, self.centroidHeaders, self.nodeData,
            self.centroidData, *self.nodeSets.values(), *self.elementSets.values()
        ):
            array.setflags(write=False)

    def __repr__(self, indexBase: int = 0) -> str:
        """Readable database summary."""
        indent: str = " "*2
        join: Callable[[Collection[str]], str] = lambda items: \
            "\n".join(f"{indent*2}\"{item}\"" for item in items) if len(items) else f"{indent*2}None"
        typeSummary: str = "; ".join(f"{t}: {c}" for t, c in zip(*np.unique(self.types, return_counts=True)))
        timeSummary: str = "\n".join(f"{indent}{i}: {t}" for i, t in enumerate(self.times, start=indexBase))
        return f"""\
{os.path.splitext(self.path)[1][1:].upper()} Database - {self.path}
Mesh:
{indent}Number of nodes: {self.nodes.shape[0]}
{indent}Number of elements: {self.elements.shape[0]} ({typeSummary})
Sets:
{indent}Available node sets ({len(self.nodeSets)}):\n{join(self.nodeSets.keys())}
{indent}Available element sets ({len(self.elementSets)}):\n{join(self.elementSets.keys())}
Time steps ({self.times.size}) [{indexBase}-based indexing]:\n{timeSummary}
Fields:
{indent}Node fields ({self.nodeHeaders.size}):\n{join(self.nodeHeaders)}
{indent}Centroid fields ({self.centroidHeaders.size}):\n{join(self.centroidHeaders)}"""

    @overload
    def get(
        self,
        fields: str,
        position: Literal["nodes", "centroids"],
        subset: str | None = None,
        timeMask: Array | None = None
    ) -> Array:
        ...

    @overload
    def get(
        self,
        fields: list[str] | tuple[str, ...],
        position: Literal["nodes", "centroids"],
        subset: str | None = None,
        timeMask: Array | None = None
    ) -> tuple[Array, ...]:
        ...

    def get(
        self,
        fields: str | list[str] | tuple[str, ...],
        position: Literal["nodes", "centroids"],
        subset: str | None = None,
        timeMask: Array | None = None
    ) -> Array | tuple[Array, ...]:
        """
        Retrieve field output data for the specified position, region, and time.

        Parameters
        ----------
        fields : string or sequence of strings
            The names/headers of the requested fields, e.g., `['U.U1', 'U.U2', 'U.U3']`, `['S.MISES', 'S.TRESCA']`.
        position : {'nodes', 'centroids'}
            The spatial location of the requested data.
        subset : string, optional
            Optional node (if `position='nodes'`) or element (if `position='centroids'`) set name defining the region
            for which the data is to be extracted. If not specified, extracts data for all nodes or centroids.
        timeMask : array, optional
            Optional mask used to filter the requested time steps (e.g., `timeMask=database.times >= 3.14`). If not
            specified, extracts data for all frames.

        Returns
        -------
        out : array or tuple of arrays
            Arrays containing the requested field output data. The returned arrays are matrices of size `m`-by-`n`,
            where `m` is the number of nodes (if `position='nodes'`) or elements (if `position='centroids'`) and `n` is
            the number of requested time frames if `timeMask` is specified; otherwise, it is the number of available
            time frames. If `fields` is specified as a single string, return a single array instead of a tuple of
            arrays.
        """

        # get requested position
        targetData: Array; targetSets: dict[str, Array]; targetHeaders: Array
        match position:
            case "nodes":
                targetData = self.nodeData
                targetSets = self.nodeSets
                targetHeaders = self.nodeHeaders
            case "centroids":
                targetData = self.centroidData
                targetSets = self.elementSets
                targetHeaders = self.centroidHeaders
            case _:
                raise ValueError(f"invalid position '{position}'; position must be 'nodes' or 'centroids'")

        # get j-indexing
        j: slice | Array = slice(None)
        if subset is not None:
            if subset not in targetSets.keys():
                raise ValueError(
                    f"set '{subset}' not available for position '{position}'; available sets: " +
                    ", ".join(f"'{key}'" for key in targetSets.keys())
                )
            j = targetSets[subset]

        # get k-indexing
        if isinstance(timeMask, Array) and not np.isdtype(timeMask.dtype, "bool"):
            raise ValueError(f"time mask array must have a boolean data type, not '{timeMask.dtype}'")
        k: slice | Array = slice(None) if timeMask is None else timeMask

        # get fields
        out: list[Array] = []
        for header in (fields,) if isinstance(fields, str) else fields:
            found: Array = np.where(targetHeaders == header)[0]
            if found.size == 0:
                raise ValueError(
                    f"field '{header}' not available at position '{position}'; available fields: " +
                    ", ".join(f"'{h}'" for h in targetHeaders)
                )
            i: int = int(found[0])
            out.append(targetData[i][j, :][:, k])
        return out[0] if isinstance(fields, str) else tuple(out)

    def add(
        self,
        data: Mapping[str, Array],
        position: Literal["nodes", "centroids"],
        subset: str | None = None,
        timeMask: Array | None = None
    ) -> None:
        """
        Add field output arrays to the database.

        Parameters
        ----------
        data : mapping of strings to arrays
            A dict-like object mapping names/headers to the corresponding data arrays to be inserted in the database.
            The names/headers must be unique, and the arrays must have the correct shape for the position, region, and
            time frame(s).
        position : {'nodes', 'centroids'}
            The spatial location where the new data should be added.
        subset : string, optional
            Optional node (if `position='nodes'`) or element (if `position='centroids'`) set name defining the region
            for which the data is to be added. If not specified, adds data for all nodes or centroids. If specified, 
            nodes/centroids outside this subset will be padded with NaN.
        timeMask : array, optional
            Optional mask used to filter the time steps for which the data is to be added. If not specified, adds data
            for all time frames. If specified, time frames outside this mask will be padded with NaN.
        """

        # get requested position
        dataAttribute: str; headerAttribute: str
        targetData: Array; targetSets: dict[str, Array]; targetHeaders: Array
        match position:
            case "nodes":
                targetData = self.nodeData
                targetSets = self.nodeSets
                targetHeaders = self.nodeHeaders
                dataAttribute, headerAttribute = "nodeData", "nodeHeaders"
            case "centroids":
                targetData = self.centroidData
                targetSets = self.elementSets
                targetHeaders = self.centroidHeaders
                dataAttribute, headerAttribute = "centroidData", "centroidHeaders"
            case _:
                raise ValueError(f"invalid position '{position}'; position must be 'nodes' or 'centroids'")

        # get j-indexing
        j: slice | Array = slice(None)
        if subset is not None:
            if subset not in targetSets.keys():
                raise ValueError(
                    f"set '{subset}' not available for position '{position}'; available sets: " +
                    ", ".join(f"'{key}'" for key in targetSets.keys())
                )
            j = targetSets[subset]

        # get k-indexing
        if isinstance(timeMask, Array) and not np.isdtype(timeMask.dtype, "bool"):
            raise ValueError(f"time mask array must have a boolean data type, not '{timeMask.dtype}'")
        k: slice | Array = slice(None) if timeMask is None else timeMask

        # get expected array shape
        expectedEntityCount: int = int(targetData.shape[1]) if isinstance(j, slice) else j.size
        expectedFrameCount: int = int(targetData.shape[2]) if isinstance(k, slice) else int(k.sum())
        expectedShape: tuple[int, int] = expectedEntityCount, expectedFrameCount
        newArray: Array = np.full(
            shape=(len(data), targetData.shape[1], targetData.shape[2]),
            fill_value=np.nan,
            dtype=targetData.dtype
        )

        # loop provided data arrays
        for i, (header, array) in enumerate(data.items()):
            if np.where(targetHeaders == header)[0].size > 0:
                raise ValueError(f"header '{header}' already exists at position '{position}'")
            if array.shape != expectedShape:
                raise ValueError(
                    f"bad shape for '{header}' field output array at position '{position}'; "
                    f"expected shape {expectedShape}, but got {array.shape}"
                )
            if isinstance(j, Array) and isinstance(k, Array):
                newArray[i][np.ix_(j, k)] = array
            else:
                newArray[i][j, k] = array

        # concatenate
        object.__setattr__(self, dataAttribute, np.concatenate((targetData, newArray), axis=0))
        object.__setattr__(self, headerAttribute, np.append(targetHeaders, [*data.keys()]))
        getattr(self, dataAttribute).setflags(write=False)
        getattr(self, headerAttribute).setflags(write=False)

    def save(self) -> None:
        """Save the database state to disk."""
        with open(self.path, "wb") as file:
            np.savez(file, allow_pickle=False, **{
                "__nodes__": self.nodes,
                "__types__": self.types,
                "__elements__": np.ma.getdata(self.elements),
                **{f"__node_set__.\"{name}\"": array for name, array in self.nodeSets.items()},
                **{f"__element_set__.\"{name}\"": array for name, array in self.elementSets.items()},
                "__times__": self.times,
                "__node_data__": self.nodeData,
                "__centroid_data__": self.centroidData,
                "__node_headers__": self.nodeHeaders,
                "__centroid_headers__": self.centroidHeaders,
            })
