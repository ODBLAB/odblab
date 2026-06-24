from odblab.viewer import Renderable
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkRenderingCore import vtkCoordinate, vtkPolyDataMapper2D, vtkActor2D

class Border(Renderable):
    """Viewport border."""

    def __init__(self) -> None:
        """Viewport border constructor."""
        super().__init__()

        # points
        self._points: vtkPoints = vtkPoints()
        self._points.SetNumberOfPoints(4)
        self._points.SetPoint(0, 0.0, 0.0, 0.0)
        self._points.SetPoint(1, 1.0, 0.0, 0.0)
        self._points.SetPoint(2, 1.0, 1.0, 0.0)
        self._points.SetPoint(3, 0.0, 1.0, 0.0)

        # lines
        self._lines: vtkCellArray = vtkCellArray()
        self._lines.InsertNextCell(5, (0, 1, 2, 3, 0))

        # poly data
        self._polyData: vtkPolyData = vtkPolyData()
        self._polyData.SetPoints(self._points)
        self._polyData.SetLines(self._lines)

        # coordinate system
        self._coordSystem: vtkCoordinate = vtkCoordinate()
        self._coordSystem.SetCoordinateSystemToNormalizedViewport()

        # mapper
        self._mapper: vtkPolyDataMapper2D = vtkPolyDataMapper2D()
        self._mapper.SetInputData(self._polyData)
        self._mapper.SetTransformCoordinate(self._coordSystem)

        # actor
        self._actor: vtkActor2D = vtkActor2D()
        self._actor.SetMapper(self._mapper)
        self._actor.GetProperty().SetLineWidth(2.0)
        self._actor.GetProperty().SetColor(1.0, 0.0, 0.0)

        # prop list
        self._props += [self._actor]
