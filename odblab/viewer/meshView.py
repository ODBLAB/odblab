import warnings
import numpy as np
from odblab.core import Database
from odblab.viewer import RenderStyles, Renderable, Legend, getCellType
from vtkmodules.vtkCommonCore import vtkPoints, vtkFloatArray, vtkBitArray
from vtkmodules.vtkCommonDataModel import vtkUnstructuredGrid, VTK_EMPTY_CELL, VTK_VERTEX
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersCore import vtkExtractEdges, vtkThreshold
from vtkmodules.vtkFiltersGeneral import vtkWarpVector
from vtkmodules.vtkFiltersGeometry import vtkUnstructuredGridGeometryFilter
from vtkmodules.vtkRenderingCore import vtkDataSetMapper, vtkActor
from itertools import combinations
from numpy import ndarray as Array

class MeshView(Renderable):
    """A renderable finite element mesh view object."""

    @property
    def database(self) -> Database:
        """The finite element database."""
        return self._database

    def __init__(self, database: Database) -> None:
        """Mesh view constructor."""
        super().__init__()
        self._database: Database = database
        self._renderStyle: RenderStyles = RenderStyles.Filled
        self._renderUnconnectedPoints: bool = False

        # get unconnected nodes/points
        self._unusedPoints: Array = np.setdiff1d(
            np.arange(self._database.nodes.shape[0], dtype=self._database.elements.dtype),
            np.unique(self._database.elements.compressed())
        )

        # data set
        self._cellVisibilityMask: vtkBitArray = vtkBitArray()
        self._cellVisibilityMask.SetNumberOfValues(self._database.elements.shape[0] + self._unusedPoints.size)
        self._cellVisibilityMask.SetName("CellVisibilityMask")
        self._cellVisibilityMask.Fill(1)
        self._warpVectors: vtkFloatArray = vtkFloatArray()
        self._warpVectors.SetNumberOfComponents(3)
        self._warpVectors.SetNumberOfTuples(self._database.nodes.shape[0])
        self._warpVectors.Fill(0.0)
        self._pointScalars: vtkFloatArray = vtkFloatArray()
        self._pointScalars.SetNumberOfValues(self._database.nodes.shape[0])
        self._pointScalars.Fill(0.0)
        self._cellScalars: vtkFloatArray = vtkFloatArray()
        self._cellScalars.SetNumberOfValues(self._database.elements.shape[0] + self._unusedPoints.size)
        self._cellScalars.Fill(0.0)
        self._points: vtkPoints = vtkPoints()
        self._points.SetNumberOfPoints(self._database.nodes.shape[0])
        for index, coordinates in enumerate(self._database.nodes):
            self._points.SetPoint(index, coordinates)
        self._grid: vtkUnstructuredGrid = vtkUnstructuredGrid()
        self._grid.GetPointData().SetVectors(self._warpVectors)
        self._grid.GetPointData().SetScalars(self._pointScalars)
        self._grid.GetCellData().SetScalars(self._cellScalars)
        self._grid.GetCellData().AddArray(self._cellVisibilityMask)
        self._grid.SetPoints(self._points)
        for elementType, connectivity in zip(self._database.types, self._database.elements):
            connectivity = connectivity.compressed()
            cellType = getCellType(elementType)
            if cellType == VTK_EMPTY_CELL:
                self._grid.InsertNextCell(VTK_EMPTY_CELL, 0, [])
                warnings.warn(
                    f"could not map element type '{elementType}' to a VTK cell type; "
                    "unmapped elements are not rendered"
                )
            else:
                self._grid.InsertNextCell(cellType, connectivity.size, connectivity)
        for i, point in enumerate(self._unusedPoints):
            self._grid.InsertNextCell(VTK_VERTEX, 1, [point])
            self._cellScalars.SetValue(self._database.elements.shape[0] + i, np.nan)

        # visibility filter
        self._visibilityFilter: vtkThreshold = vtkThreshold()
        self._visibilityFilter.SetInputData(self._grid)
        self._visibilityFilter.SetInputArrayToProcess("CellVisibilityMask", vtkUnstructuredGrid.FIELD_ASSOCIATION_CELLS)
        self._visibilityFilter.SetThresholdFunction(vtkThreshold.THRESHOLD_UPPER)
        self._visibilityFilter.SetUpperThreshold(1)

        # warp filter
        self._warpFilter: vtkWarpVector = vtkWarpVector()
        self._warpFilter.SetInputConnection(self._visibilityFilter.GetOutputPort())
        self._warpFilter.SetScaleFactor(1.0)

        # mapper
        self._gridMapper: vtkDataSetMapper = vtkDataSetMapper()
        self._gridMapper.SetInputConnection(self._warpFilter.GetOutputPort())
        self._gridMapper.InterpolateScalarsBeforeMappingOn()
        self._gridMapper.ScalarVisibilityOff()

        # actor
        self._gridActor: vtkActor = vtkActor()
        self._gridActor.SetMapper(self._gridMapper)
        self._gridActor.SetObjectName("__grid__")
        self._gridActor.GetProperty().SetPointSize(10)

        # geometry filter
        self._geometryFilter: vtkUnstructuredGridGeometryFilter = vtkUnstructuredGridGeometryFilter()
        self._geometryFilter.SetInputConnection(self._warpFilter.GetOutputPort())

        # edges filter
        self._edgesFilter: vtkExtractEdges = vtkExtractEdges()
        self._edgesFilter.SetInputConnection(self._geometryFilter.GetOutputPort())

        # edges mapper
        self._edgesMapper: vtkDataSetMapper = vtkDataSetMapper()
        self._edgesMapper.SetInputConnection(self._edgesFilter.GetOutputPort())
        self._edgesMapper.InterpolateScalarsBeforeMappingOn()
        self._edgesMapper.ScalarVisibilityOff()

        # edges actor
        self._edgesActor: vtkActor = vtkActor()
        self._edgesActor.SetMapper(self._edgesMapper)
        self._edgesActor.SetObjectName("__edges__")
        self._edgesActor.GetProperty().SetColor(0.0, 0.0, 0.0)
        self._edgesActor.GetProperty().SetPointSize(10)

        # prop list
        self._props += [self._gridActor, self._edgesActor]

        # apply initial settings
        self.setRenderUnconnectedPoints(False)

    def setLegend(self, legend: Legend) -> None:
        """Sets the legend for the scalar contour plot."""
        legend.assignLookupTableToMapper(self._gridMapper)
        legend.assignLookupTableToMapper(self._edgesMapper)

    def setContourPlotRange(self, min: float, max: float) -> None:
        """Sets the range for the current scalar contour plot."""
        self._gridMapper.SetScalarRange(min, max)
        self._edgesMapper.SetScalarRange(min, max)

    def plotNodeContour(self, scalarField: Array) -> None:
        """Plots the contour for the given node scalar field."""
        for i in range(self._database.nodes.shape[0]):
            self._pointScalars.SetValue(i, scalarField[i])
        self._pointScalars.Modified()
        self._gridMapper.SetScalarModeToUsePointData()
        self._edgesMapper.SetScalarModeToUsePointData()
        self._gridMapper.ScalarVisibilityOn()
        self._edgesMapper.SetScalarVisibility(not self._gridActor.GetVisibility())

    def plotCentroidContour(self, scalarField: Array) -> None:
        """Plots the contour for the given element (centroid) scalar field."""
        for i in range(self._database.elements.shape[0]):
            self._cellScalars.SetValue(i, scalarField[i])
        self._cellScalars.Modified()
        self._gridMapper.SetScalarModeToUseCellData()
        self._edgesMapper.SetScalarModeToUseCellData()
        self._gridMapper.ScalarVisibilityOn()
        self._edgesMapper.SetScalarVisibility(not self._gridActor.GetVisibility())

    def clearContourPlot(self) -> None:
        """Clears the current scalar contour plot."""
        self._gridMapper.ScalarVisibilityOff()
        self._edgesMapper.ScalarVisibilityOff()

    def applyDeformation(self, displacements: Array | None = None, scale: float | None = None) -> None:
        """Applies the nodal displacement vector field."""
        if displacements is not None:
            for i in range(self._database.nodes.shape[0]):
                self._warpVectors.SetTuple3(i, *displacements[i])
            self._warpVectors.Modified()
        if scale is not None:
            self._warpFilter.SetScaleFactor(scale)
            self._warpFilter.Modified()

    def applyCellVisibilityMask(self, mask: Array) -> None:
        """Applies the provided cell visibility boolean mask."""
        for i in range(self._database.elements.shape[0]):
            self._cellVisibilityMask.SetValue(i, mask[i])
        self._cellVisibilityMask.Modified()

    def getCellVisibilityMask(self) -> Array:
        """Returns a cell visibility mask array."""
        out: Array = np.empty(shape=(self._database.elements.shape[0],), dtype=np.bool)
        for i in range(self._database.elements.shape[0]):
            out[i] = self._cellVisibilityMask.GetValue(i)
        return out

    def getPointVisibilityMask(self) -> Array:
        """Returns a point visibility mask array."""
        mask: Array = np.zeros(shape=(self._database.nodes.shape[0],), dtype=np.bool)
        mask[self._database.elements[self.getCellVisibilityMask(), :].compressed()] = 1
        mask[self._unusedPoints] = self._renderUnconnectedPoints
        return mask

    def mirror(self, planeYZ: bool = False, planeXZ: bool = False, planeXY: bool = False) -> None:
        """Mirrors the displayed object."""
        enabled: list[int] = [i for i, x in enumerate((planeYZ, planeXZ, planeXY)) if x]
        transformMatrix: list[list[int]] = []
        for r in range(1, len(enabled) + 1):
            for c in combinations(enabled, r):
                row: list[int] = [1, 1, 1]
                for i in c: row[i] = -1
                transformMatrix.append(row)
        newActors: list[vtkActor] = []
        self._props = [prop for prop in self._props if "__mirror__" not in prop.GetObjectName()]
        for actor in (prop for prop in self._props if isinstance(prop, vtkActor)):
            for row in transformMatrix:
                transform: vtkTransform = vtkTransform()
                transform.Scale(row)
                newActor: vtkActor = vtkActor()
                newActor.SetMapper(actor.GetMapper())
                newActor.SetProperty(actor.GetProperty())
                newActor.SetVisibility(actor.GetVisibility())
                newActor.SetObjectName(f"{actor.GetObjectName()}.__mirror__")
                newActor.SetUserTransform(transform)
                newActors.append(newActor)
        self._props += newActors
        self.reattach()

    def setRenderStyle(self, value: RenderStyles) -> None:
        """Sets the current render style."""
        self._renderStyle = value
        for actor in (prop for prop in self._props if isinstance(prop, vtkActor)):
            if actor.GetObjectName().startswith("__grid__"):
                actor.SetVisibility(value in (RenderStyles.Filled, RenderStyles.FilledNoEdges))
            elif actor.GetObjectName().startswith("__edges__"):
                actor.SetVisibility(value in (RenderStyles.Filled, RenderStyles.Wireframe))
        contour: bool = bool(self._gridMapper.GetScalarVisibility() + self._edgesMapper.GetScalarVisibility())
        self._gridMapper.SetScalarVisibility(contour and value in (RenderStyles.Filled, RenderStyles.FilledNoEdges))
        self._edgesMapper.SetScalarVisibility(contour and value is RenderStyles.Wireframe)

    def renderUnconnectedPoints(self) -> bool:
        """Unconnected point rendering flag."""
        return self._renderUnconnectedPoints

    def setRenderUnconnectedPoints(self, value: bool) -> None:
        """Sets the unconnected point rendering flag."""
        self._renderUnconnectedPoints = value
        for i in range(self._database.elements.shape[0], self._database.elements.shape[0] + self._unusedPoints.size):
            self._cellVisibilityMask.SetValue(i, value)
        self._cellVisibilityMask.Modified()
