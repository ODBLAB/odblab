import numpy as np
from numpy import ndarray as Array
from odblab.viewer import Views, Triad, Border, Legend, InfoBlock, MeshView
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkRenderWindow, vtkRenderWindowInteractor, vtkWindowToImageFilter
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PySide6.QtWidgets import QWidget, QVBoxLayout

class Viewport(QWidget):
    """A VTK-based viewport widget."""

    @property
    def meshView(self) -> MeshView | None:
        """The finite element mesh view object."""
        return self._meshView

    @property
    def currentTime(self) -> float | None:
        """The current frame time/frequency."""
        return self._currentTime

    @property
    def currentNodeHeader(self) -> str | None:
        """The current node header."""
        return self._currentNodeHeader

    @property
    def currentCentroidHeader(self) -> str | None:
        """The current centroid header."""
        return self._currentCentroidHeader

    @property
    def legend(self) -> Legend:
        """The viewport legend."""
        return self._legend

    def __init__(self, parent: QWidget | None = None) -> None:
        """Viewport constructor."""
        super().__init__(parent)
        self._meshView: MeshView | None = None
        self._currentTime: float | None = None
        self._currentNodeHeader: str | None = None
        self._currentCentroidHeader: str | None = None
        self._useGlobalRange: bool = False

        # layout
        self._layout: QVBoxLayout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        # VTK widget
        self._vtkWidget: QVTKRenderWindowInteractor = QVTKRenderWindowInteractor(self)
        self._layout.addWidget(self._vtkWidget)

        # renderer, render window, render window interactor
        self._renderer: vtkRenderer = vtkRenderer()
        self._renderWindow: vtkRenderWindow = self._vtkWidget.GetRenderWindow()
        self._interactor: vtkRenderWindowInteractor = self._renderWindow.GetInteractor()
        self._interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        self._interactor.RemoveObservers("CharEvent")
        self._renderWindow.AddRenderer(self._renderer)
        self._renderer.GradientBackgroundOn()
        self._renderer.SetBackground(0.6, 0.7, 0.8)
        self._renderer.SetBackground2(0.1, 0.2, 0.3)

        # triad
        self._triad: Triad = Triad()
        self._triad.setInteractor(self._interactor)

        # border
        self._border: Border = Border()
        self._border.attach(self._renderer)

        # legend
        self._legend: Legend = Legend()
        self._legend.setVisible(False)
        self._legend.attach(self._renderer)

        # info block
        self._infoBlock: InfoBlock = InfoBlock()
        self._infoBlock.attach(self._renderer)

    def start(self) -> None:
        """Starts the viewport."""
        self._interactor.Start()

    def draw(self) -> None:
        """Renders the current scene."""
        self._renderWindow.Render()

    def setMeshView(self, meshView: MeshView) -> None:
        """Sets the finite element mesh view object."""
        if self._meshView is not None: self._meshView.detach()
        self._meshView = meshView
        self._meshView.attach(self._renderer)
        self._meshView.setLegend(self._legend)
        self._currentTime = self._meshView.database.times[-1]
        self._currentNodeHeader = None
        self._currentCentroidHeader = None

        # update info block
        self._infoBlock.clear()
        self._infoBlock.setFilePath(self._meshView.database.path)
        self._infoBlock.setDeformationScaleFactor(1.0)
        self._infoBlock.setTime(self._currentTime or 0.0)

        # done
        self.applyDeformation(draw=False)
        self.applyView(Views.Isometric, draw=True)

    def clearContourPlot(self, draw: bool = True) -> None:
        """Clears the current scalar contour plot."""
        if self._meshView is None: return
        self._currentNodeHeader = None
        self._currentCentroidHeader = None
        self._meshView.clearContourPlot()
        self._legend.setVisible(False)
        self._infoBlock.clearVariable()
        if draw: self.draw()

    def plotNodeContour(self, header: str | None = None, draw: bool = True) -> None:
        """Plots the contour for the requested node scalar field."""
        if self._meshView is None or self._currentTime is None: return
        if header is None:
            if self._currentNodeHeader is not None:
                self.plotNodeContour(self._currentNodeHeader, draw)
            return
        self._currentNodeHeader = header

        # get time and header indices
        timeIndex: int = int(np.where(self._meshView.database.times == self._currentTime)[0][0])
        headerIndex: int = int(np.where(self._meshView.database.nodeHeaders == self._currentNodeHeader)[0][0])

        # get scalar range
        subset: Array
        regionMask: Array = self._meshView.getPointVisibilityMask()
        if self._useGlobalRange: subset = self._meshView.database.nodeData[headerIndex, regionMask, :]
        else: subset = self._meshView.database.nodeData[headerIndex, regionMask, timeIndex]
        minValue: float = float(np.nanmin(subset))
        maxValue: float = float(np.nanmax(subset))

        # plot
        self.clearContourPlot(draw=False); self._currentNodeHeader = header
        self._meshView.plotNodeContour(self._meshView.database.nodeData[headerIndex, :, timeIndex])
        self._meshView.setContourPlotRange(minValue, maxValue)
        self._infoBlock.setVariable(self._currentNodeHeader)
        self._legend.setVisible(True)
        if draw: self.draw()

    def plotCentroidContour(self, header: str | None = None, draw: bool = True) -> None:
        """Plots the contour for the requested element (centroid) scalar field."""
        if self._meshView is None or self._currentTime is None: return
        if header is None:
            if self._currentCentroidHeader is not None:
                self.plotCentroidContour(self._currentCentroidHeader, draw)
            return
        self._currentCentroidHeader = header

        # get time and header indices
        timeIndex: int = int(np.where(self._meshView.database.times == self._currentTime)[0][0])
        headerIndex: int = int(np.where(self._meshView.database.centroidHeaders == self._currentCentroidHeader)[0][0])

        # get scalar range
        subset: Array
        regionMask: Array = self._meshView.getCellVisibilityMask()
        if self._useGlobalRange: subset = self._meshView.database.centroidData[headerIndex, regionMask, :]
        else: subset = self._meshView.database.centroidData[headerIndex, regionMask, timeIndex]
        minValue: float = float(np.nanmin(subset))
        maxValue: float = float(np.nanmax(subset))

        # plot
        self.clearContourPlot(draw=False); self._currentCentroidHeader = header
        self._meshView.plotCentroidContour(self._meshView.database.centroidData[headerIndex, :, timeIndex])
        self._meshView.setContourPlotRange(minValue, maxValue)
        self._infoBlock.setVariable(self._currentCentroidHeader)
        self._legend.setVisible(True)
        if draw: self.draw()

    def applyDeformation(self, scale: float | None = None, draw: bool = True) -> None:
        """Applies the nodal displacement vector field."""
        if self._meshView is None or self._currentTime is None: return
        timeIndex: int = int(np.where(self._meshView.database.times == self._currentTime)[0][0])
        displacements: Array = np.zeros(shape=(self._meshView.database.nodes.shape[0], 3), dtype=np.float32)
        for i, header in enumerate(("U.U1", "U.U2", "U.U3")):
            matches: Array = np.where(self._meshView.database.nodeHeaders == header)[0]
            if matches.size > 0: displacements[:, i] = self._meshView.database.nodeData[matches[0], :, timeIndex]
        self._meshView.applyDeformation(displacements, scale)
        if scale is not None: self._infoBlock.setDeformationScaleFactor(scale)

    def goToLastFrame(self, draw: bool = True) -> None:
        """Moves to the last frame."""
        if self._meshView is None or self._currentTime is None: return
        self._currentTime = self._meshView.database.times[-1]
        self._infoBlock.setTime(self._currentTime or 0.0)
        self.applyDeformation(draw=False)
        self.plotNodeContour(draw=False)
        self.plotCentroidContour(draw=False)
        if draw: self.draw()

    def goToFirstFrame(self, draw: bool = True) -> None:
        """Moves to the first frame."""
        if self._meshView is None or self._currentTime is None: return
        self._currentTime = self._meshView.database.times[0]
        self._infoBlock.setTime(self._currentTime or 0.0)
        self.applyDeformation(draw=False)
        self.plotNodeContour(draw=False)
        self.plotCentroidContour(draw=False)
        if draw: self.draw()

    def goToPreviousFrame(self, draw: bool = True) -> None:
        """Moves to the previous frame; returns false if already in the first frame."""
        if self._meshView is None or self._currentTime is None: return
        timeIndex: int = int(np.where(self._meshView.database.times == self._currentTime)[0][0])
        if timeIndex == 0: return
        self._currentTime = self._meshView.database.times[timeIndex - 1]
        self._infoBlock.setTime(self._currentTime or 0.0)
        self.applyDeformation(draw=False)
        self.plotNodeContour(draw=False)
        self.plotCentroidContour(draw=False)
        if draw: self.draw()

    def goToNextFrame(self, draw: bool = True) -> None:
        """Moves to the next frame; returns false if already in the last frame."""
        if self._meshView is None or self._currentTime is None: return
        timeIndex: int = int(np.where(self._meshView.database.times == self._currentTime)[0][0])
        if timeIndex == self._meshView.database.times.size - 1: return
        self._currentTime = self._meshView.database.times[timeIndex + 1]
        self._infoBlock.setTime(self._currentTime or 0.0)
        self.applyDeformation(draw=False)
        self.plotNodeContour(draw=False)
        self.plotCentroidContour(draw=False)
        if draw: self.draw()

    def applyView(self, view: Views, draw: bool = True) -> None:
        """Applies the viewport camera view."""

        # update focal point, position, view-up
        focalPoint: tuple[float, float, float] | None
        position: tuple[float, float, float] | None
        viewUp: tuple[float, float, float] | None
        match view:
            case Views.Front:
                focalPoint = +0.0, +0.0, +0.0
                position   = +0.0, +0.0, +1.0
                viewUp     = +0.0, +1.0, +0.0
            case Views.Back:
                focalPoint = +0.0, +0.0, +0.0
                position   = +0.0, +0.0, -1.0
                viewUp     = +0.0, +1.0, +0.0
            case Views.Top:
                focalPoint = +0.0, +0.0, +0.0
                position   = +0.0, +1.0, +0.0
                viewUp     = +0.0, +0.0, -1.0
            case Views.Bottom:
                focalPoint = +0.0, +0.0, +0.0
                position   = +0.0, -1.0, +0.0
                viewUp     = +0.0, +0.0, +1.0
            case Views.Left:
                focalPoint = +0.0, +0.0, +0.0
                position   = -1.0, +0.0, +0.0
                viewUp     = +0.0, +1.0, +0.0
            case Views.Right:
                focalPoint = +0.0, +0.0, +0.0
                position   = +1.0, +0.0, +0.0
                viewUp     = +0.0, +1.0, +0.0
            case Views.Isometric:
                focalPoint = +0.0, +0.0, +0.0
                position   = +1.0, +1.0, +1.0
                viewUp     = +0.0, +1.0, +0.0
            case Views.RotateCW | Views.RotateCCW | Views.AutoFit:
                focalPoint = None
                position   = None
                viewUp     = None
            case _:
                raise NotImplementedError()
        if focalPoint is not None: self._renderer.GetActiveCamera().SetFocalPoint(focalPoint)
        if position is not None: self._renderer.GetActiveCamera().SetPosition(position)
        if viewUp is not None: self._renderer.GetActiveCamera().SetViewUp(viewUp)

        # auto-fit or rotate view
        match view:
            case Views.RotateCW: self._renderer.GetActiveCamera().Roll(-90.0)
            case Views.RotateCCW: self._renderer.GetActiveCamera().Roll(90.0)
            case _: self._renderer.ResetCamera()

        # done
        if draw: self._renderWindow.Render()

    def print(self, pngPath: str) -> None:
        """Prints the current viewport scene."""

        # save current background and text colors
        backgroundColor1: tuple[float, float, float] = self._renderer.GetBackground()
        backgroundColor2: tuple[float, float, float] = self._renderer.GetBackground2()
        infoBlockTextColor: tuple[float, float, float] = self._infoBlock.textColor()
        legendTextColor: tuple[float, float, float] = self._legend.textColor()
        triadTextColor: tuple[float, float, float] = self._triad.textColor()

        # set white background and black text
        self._renderer.SetBackground(1.0, 1.0, 1.0)
        self._renderer.SetBackground2(1.0, 1.0, 1.0)
        self._infoBlock.setTextColor((0.0, 0.0, 0.0))
        self._legend.setTextColor((0.0, 0.0, 0.0))
        self._triad.setTextColor((0.0, 0.0, 0.0))
        self.draw()

        # create image filter
        filter: vtkWindowToImageFilter = vtkWindowToImageFilter()
        filter.SetInput(self._renderWindow)
        filter.SetInputBufferTypeToRGB()

        # create writer and write to file
        writer: vtkPNGWriter = vtkPNGWriter()
        writer.SetInputConnection(filter.GetOutputPort())
        writer.SetFileName(pngPath)
        writer.Write()

        # reset background and text colors
        self._renderer.SetBackground(backgroundColor1)
        self._renderer.SetBackground2(backgroundColor2)
        self._infoBlock.setTextColor(infoBlockTextColor)
        self._legend.setTextColor(legendTextColor)
        self._triad.setTextColor(triadTextColor)
        self.draw()

    def useGlobalRange(self) -> bool:
        """Gets the use global range property."""
        return self._useGlobalRange

    def setUseGlobalRange(self, value: bool) -> None:
        """Sets the use global range property."""
        self._useGlobalRange = value

    def setParallelProjection(self, value: bool, draw: bool = True) -> None:
        """Sets parallel projection enabled/disabled."""
        self._renderer.GetActiveCamera().SetParallelProjection(value)
        if draw: self._renderWindow.Render()

    def parallelProjection(self) -> bool:
        """Gets parallel projection enabled/disabled."""
        return bool(self._renderer.GetActiveCamera().GetParallelProjection())
