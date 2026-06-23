import numpy as np
from numpy import ndarray as Array
from numpy.ma import MaskedArray
from dataclasses import dataclass, fields
from collections.abc import Sequence, Mapping
from typing import Literal, Any

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
        for field in fields(self):
            value: Any = getattr(self, field.name)
            for x in value.values() if isinstance(value, dict) else (value,):
                if isinstance(x, (Array, MaskedArray)):
                    x.setflags(write=False)

    def get(
        self,
        position: Literal["nodes", "centroids"],
        fields: Sequence[str],
        subset: str | None = None,
        frame: int | None = None
    ) -> tuple[Array, ...]:
        """
        Retrieve field output data for the specified position, region, and time.

        Parameters
        ----------
        position : {'nodes', 'centroids'}
            The spatial location of the requested data.
        fields : sequence of strings
            The names/headers of the requested fields, e.g., `['U.U1', 'U.U2', 'U.U3']`, `['S.MISES', 'S.TRESCA']`.
        subset : string, optional
            Optional node (if `position='nodes'`) or element (if `position='centroids'`) set name defining the region
            for which the data is to be extracted. If not specified, extracts data for all nodes or centroids.
        frame : integer, optional
            The time frame index for which the data is to be extracted. If not specified, extracts data for all frames.

        Returns
        -------
        out : tuple of arrays
            Arrays containing the requested field output data. If the data is requested at a specific frame, the
            returned arrays are vectors of size `m`; otherwise, they are matrices of size `m`-by-`n`, where `m` is the
            number of nodes (if `position='nodes'`) or elements (if `position='centroids'`) and `n` is the number of
            available frames.
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
        k: slice | int = slice(None) if frame is None else frame

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
            out.append(targetData[i, j, k])
        return tuple(out)

    def add(
        self,
        data: Mapping[str, Array],
        position: Literal["nodes", "centroids"],
        subset: str | None = None,
        frame: int | None = None
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
        frame : integer, optional
            The time frame index for which the data is to be added. If not specified, adds data for all frames. If
            specified, frames outside this index will be padded with NaN.
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
        k: slice | int = slice(None) if frame is None else frame

        # get expected array shape
        expectedEntityCount: int = int(targetData.shape[1]) if isinstance(j, slice) else j.size
        expectedShape: tuple[int, ...] = \
            (expectedEntityCount, int(targetData.shape[2])) if frame is None else (expectedEntityCount,)
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
            newArray[i, j, k] = array

        # concatenate
        object.__setattr__(self, dataAttribute, np.concatenate((targetData, newArray), axis=0))
        object.__setattr__(self, headerAttribute, np.append(targetHeaders, [*data.keys()]))
        getattr(self, dataAttribute).setflags(write=False)
        getattr(self, headerAttribute).setflags(write=False)
