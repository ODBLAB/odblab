import numpy as np
from numpy import ndarray as Array
from odblab.core import Database
from odblab.viewer import Viewport, MeshView, RenderStyles, Spectrums, Views
from importlib.resources import files
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShowEvent, QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QMainWindow, QSplitter, QSizePolicy, QTreeWidget, QTreeWidgetItem, QMenuBar, QMenu, \
    QToolBar, QFileDialog, QInputDialog

class MainWindow(QMainWindow):
    """The main window of the viewer application."""

    def __init__(self) -> None:
        """Main window constructor."""
        super().__init__()

        # main window
        self.setWindowIcon(QIcon(str(files("odblab.icons") / "odblab.ico")))
        self.setWindowTitle("ODBLAB Viewer")
        self.resize(1280, 720)

        # vertical splitter
        vSplitterSizePolicy: QSizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        vSplitterSizePolicy.setVerticalStretch(0)
        self._verticalSplitter: QSplitter = QSplitter(self)
        self._verticalSplitter.setSizePolicy(vSplitterSizePolicy)
        self._verticalSplitter.setOrientation(Qt.Orientation.Vertical)
        self._verticalSplitter.setContentsMargins(6, 6, 6, 6)
        self._verticalSplitter.setHandleWidth(6)
        self.setCentralWidget(self._verticalSplitter)

        # horizontal splitter
        hSplitterSizePolicy: QSizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        hSplitterSizePolicy.setVerticalStretch(1)
        self._horizontalSplitter: QSplitter = QSplitter(self._verticalSplitter)
        self._horizontalSplitter.setSizePolicy(hSplitterSizePolicy)
        self._horizontalSplitter.setOrientation(Qt.Orientation.Horizontal)
        self._horizontalSplitter.setContentsMargins(6, 6, 6, 6)
        self._horizontalSplitter.setHandleWidth(6)
        self._verticalSplitter.addWidget(self._horizontalSplitter)

        # results tree
        resultsTreeSizePolicy: QSizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        resultsTreeSizePolicy.setHorizontalStretch(0)
        self._resultsTree: QTreeWidget = QTreeWidget(self._horizontalSplitter)
        self._resultsTree.setSizePolicy(resultsTreeSizePolicy)
        self._resultsTree.setHeaderHidden(True)
        self._resultsTree.setIndentation(15)
        self._resultsTree.currentItemChanged.connect(self._onResultsTreeCurrentItemChanged)
        self._horizontalSplitter.addWidget(self._resultsTree)

        # viewport
        viewportSizePolicy: QSizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        viewportSizePolicy.setHorizontalStretch(1)
        viewportSizePolicy.setVerticalStretch(1)
        self._viewport: Viewport = Viewport(self._horizontalSplitter)
        self._viewport.setSizePolicy(viewportSizePolicy)
        self._horizontalSplitter.addWidget(self._viewport)

        # menu bar
        self._menuBar: QMenuBar = QMenuBar(self)
        self.setMenuBar(self._menuBar)

        # file menu
        self._fileMenu: QMenu = QMenu(self._menuBar)
        self._fileMenu.setTitle("File")
        self._menuBar.addMenu(self._fileMenu)

        # file > exit action
        self._fileExitAction: QAction = QAction(self._fileMenu)
        self._fileExitAction.setText("Exit")
        self._fileExitAction.setIcon(QIcon(str(files("odblab.icons") / "file-exit.svg")))
        self._fileExitAction.triggered.connect(self.close)
        self._fileMenu.addAction(self._fileExitAction)

        # view menu
        self._viewMenu: QMenu = QMenu(self._menuBar)
        self._viewMenu.setTitle("View")
        self._menuBar.addMenu(self._viewMenu)

        # view > region menu
        self._viewRegionMenu: QMenu = QMenu(self._viewMenu)
        self._viewRegionMenu.setTitle("Region")
        self._viewRegionMenu.setIcon(QIcon(str(files("odblab.icons") / "view-region.svg")))
        self._viewMenu.addMenu(self._viewRegionMenu)
        self._viewRegionElementSetsActionGroup: QActionGroup = QActionGroup(self._viewRegionMenu)
        self._viewRegionElementTypesActionGroup: QActionGroup = QActionGroup(self._viewRegionMenu)
        self._viewRegionElementSetsActionGroup.setExclusive(True)
        self._viewRegionElementTypesActionGroup.setExclusive(False)

        # view > mirror menu
        self._viewMirrorMenu: QMenu = QMenu(self._viewMenu)
        self._viewMirrorMenu.setTitle("Mirror")
        self._viewMirrorMenu.setIcon(QIcon(str(files("odblab.icons") / "view-mirror.svg")))
        self._viewMenu.addMenu(self._viewMirrorMenu)

        # view > mirror > x action
        self._viewMirrorXAction: QAction = QAction(self._viewMirrorMenu)
        self._viewMirrorXAction.setText("YZ Plane (X Symmetry)")
        self._viewMirrorXAction.setCheckable(True)
        self._viewMirrorXAction.triggered.connect(self._onViewMirrorActionTriggered)
        self._viewMirrorMenu.addAction(self._viewMirrorXAction)

        # view > mirror > y action
        self._viewMirrorYAction: QAction = QAction(self._viewMirrorMenu)
        self._viewMirrorYAction.setText("XZ Plane (Y Symmetry)")
        self._viewMirrorYAction.setCheckable(True)
        self._viewMirrorYAction.triggered.connect(self._onViewMirrorActionTriggered)
        self._viewMirrorMenu.addAction(self._viewMirrorYAction)

        # view > mirror > z action
        self._viewMirrorZAction: QAction = QAction(self._viewMirrorMenu)
        self._viewMirrorZAction.setText("XY Plane (Z Symmetry)")
        self._viewMirrorZAction.setCheckable(True)
        self._viewMirrorZAction.triggered.connect(self._onViewMirrorActionTriggered)
        self._viewMirrorMenu.addAction(self._viewMirrorZAction)

        # view > render style menu
        self._viewRenderStyleMenu: QMenu = QMenu(self._viewMenu)
        self._viewRenderStyleMenu.setTitle("Render Style")
        self._viewRenderStyleMenu.setIcon(QIcon(str(files("odblab.icons") / "view-render-style.svg")))
        self._viewMenu.addMenu(self._viewRenderStyleMenu)

        # view > render style > actions
        self._viewRenderStyleActionGroup: QActionGroup = QActionGroup(self._viewRenderStyleMenu)
        for renderStyle in RenderStyles:
            viewRenderStyleAction: QAction = QAction(self._viewRenderStyleMenu)
            viewRenderStyleAction.setText(renderStyle.value)
            viewRenderStyleAction.setCheckable(True)
            viewRenderStyleAction.setChecked(renderStyle is RenderStyles.Filled)
            viewRenderStyleAction.triggered.connect(self._onViewRenderStyleActionTriggered)
            self._viewRenderStyleMenu.addAction(viewRenderStyleAction)
            self._viewRenderStyleActionGroup.addAction(viewRenderStyleAction)

        # separator
        self._viewRenderStyleMenu.addSeparator()

        # view > render style > lighting action
        self._viewRenderStyleLightingAction: QAction = QAction(self._viewRenderStyleMenu)
        self._viewRenderStyleLightingAction.setText("Lighting")
        self._viewRenderStyleLightingAction.setCheckable(True)
        self._viewRenderStyleLightingAction.setChecked(True)
        self._viewRenderStyleLightingAction.triggered.connect(self._onViewRenderStyleLightingActionTriggered)
        self._viewRenderStyleMenu.addAction(self._viewRenderStyleLightingAction)

        # view > render style > parallel projection action
        self._renderStyleParallelProjectionAction: QAction = QAction(self._viewRenderStyleMenu)
        self._renderStyleParallelProjectionAction.setText("Parallel Projection")
        self._renderStyleParallelProjectionAction.setCheckable(True)
        self._renderStyleParallelProjectionAction.triggered.connect(self._viewport.setParallelProjection)
        self._viewRenderStyleMenu.addAction(self._renderStyleParallelProjectionAction)

        # view > colormap menu
        self._viewColormapMenu: QMenu = QMenu(self._viewMenu)
        self._viewColormapMenu.setTitle("Colormap")
        self._viewColormapMenu.setIcon(QIcon(str(files("odblab.icons") / "view-colormap.svg")))
        self._viewMenu.addMenu(self._viewColormapMenu)

        # view > colormap > actions
        self._viewColormapActionGroup: QActionGroup = QActionGroup(self._viewColormapMenu)
        for spectrum in Spectrums:
            viewColormapAction: QAction = QAction(self._viewColormapMenu)
            viewColormapAction.setText(spectrum.value)
            viewColormapAction.setCheckable(True)
            viewColormapAction.setChecked(spectrum is Spectrums.Abaqus)
            viewColormapAction.triggered.connect(self._onViewColormapActionTriggered)
            self._viewColormapMenu.addAction(viewColormapAction)
            self._viewColormapActionGroup.addAction(viewColormapAction)

        # view > deformation scale factor action
        self._viewDeformationScaleFactorAction: QAction = QAction(self._viewMenu)
        self._viewDeformationScaleFactorAction.setText("Deformation Scale Factor...")
        self._viewDeformationScaleFactorAction.setIcon(QIcon(str(files("odblab.icons") / "view-deformation.svg")))
        self._viewDeformationScaleFactorAction.triggered.connect(self._onViewDeformationScaleFactorActionTriggered)
        self._viewMenu.addAction(self._viewDeformationScaleFactorAction)

        # utilities tool bar
        self._utilitiesToolBar: QToolBar = QToolBar(self)
        self._utilitiesToolBar.setWindowTitle("Utilities Toolbar")
        self.addToolBar(self._utilitiesToolBar)

        # print action
        self._printAction: QAction = QAction(self._utilitiesToolBar)
        self._printAction.setIcon(QIcon(str(files("odblab.icons") / "utilities-print.svg")))
        self._printAction.setToolTip("Print Viewport")
        self._printAction.triggered.connect(self._onPrintActionTriggered)
        self._utilitiesToolBar.addAction(self._printAction)

        # views tool bar
        self._viewsToolBar: QToolBar = QToolBar(self)
        self._viewsToolBar.setWindowTitle("Views Toolbar")
        self.addToolBar(self._viewsToolBar)

        # views > actions
        for view in Views:
            viewAction: QAction = QAction(self._viewsToolBar)
            viewAction.setToolTip(view.value)
            viewAction.setIcon(QIcon(str(files("odblab.icons") / f"views-{view.name.lower()}.svg")))
            viewAction.triggered.connect(lambda _=bool(), v=view: self._viewport.applyView(v))
            self._viewsToolBar.addAction(viewAction)

        # frames tool bar
        self._framesToolBar: QToolBar = QToolBar(self)
        self._framesToolBar.setWindowTitle("Frames Toolbar")
        self.addToolBar(self._framesToolBar)

        # first frame action
        self._firstFrameAction: QAction = QAction(self._framesToolBar)
        self._firstFrameAction.setIcon(QIcon(str(files("odblab.icons") / "frame-first.svg")))
        self._firstFrameAction.setToolTip("First Frame")
        self._firstFrameAction.triggered.connect(lambda:self._viewport.goToFirstFrame(draw=True))
        self._framesToolBar.addAction(self._firstFrameAction)

        # previous frame action
        self._previousFrameAction: QAction = QAction(self._framesToolBar)
        self._previousFrameAction.setIcon(QIcon(str(files("odblab.icons") / "frame-previous.svg")))
        self._previousFrameAction.setToolTip("Previous Frame")
        self._previousFrameAction.triggered.connect(lambda:self._viewport.goToPreviousFrame(draw=True))
        self._framesToolBar.addAction(self._previousFrameAction)

        # pause frame action
        self._pauseFrameAction: QAction = QAction(self._framesToolBar)
        self._pauseFrameAction.setIcon(QIcon(str(files("odblab.icons") / "frame-pause.svg")))
        self._pauseFrameAction.setToolTip("Pause")
        self._pauseFrameAction.triggered.connect(self._onPauseFrameActionTriggered)
        self._framesToolBar.addAction(self._pauseFrameAction)

        # play frame action
        self._playFrameAction: QAction = QAction(self._framesToolBar)
        self._playFrameAction.setIcon(QIcon(str(files("odblab.icons") / "frame-play.svg")))
        self._playFrameAction.setToolTip("Play")
        self._playFrameAction.triggered.connect(self._onPlayFrameActionTriggered)
        self._framesToolBar.addAction(self._playFrameAction)

        # next frame action
        self._nextFrameAction: QAction = QAction(self._framesToolBar)
        self._nextFrameAction.setIcon(QIcon(str(files("odblab.icons") / "frame-next.svg")))
        self._nextFrameAction.setToolTip("Next Frame")
        self._nextFrameAction.triggered.connect(lambda:self._viewport.goToNextFrame(draw=True))
        self._framesToolBar.addAction(self._nextFrameAction)

        # last frame action
        self._lastFrameAction: QAction = QAction(self._framesToolBar)
        self._lastFrameAction.setIcon(QIcon(str(files("odblab.icons") / "frame-last.svg")))
        self._lastFrameAction.setToolTip("Last Frame")
        self._lastFrameAction.triggered.connect(lambda:self._viewport.goToLastFrame(draw=True))
        self._framesToolBar.addAction(self._lastFrameAction)

        # animation timer
        self._animationTimer: QTimer = QTimer(self)
        self._animationTimer.setInterval(100)
        self._animationTimer.timeout.connect(self._onAnimationTimerTimeout)

    def _onViewRegionActionTriggered(self) -> None:
        """On view > region action triggered."""
        if self._viewport.meshView is None: return
        db: Database = self._viewport.meshView.database
        region: str = self._viewRegionElementSetsActionGroup.checkedAction().text()
        visibilityMask: Array = np.zeros(shape=(db.elements.shape[0],), dtype=np.int32)
        if region == "[All Elements]": visibilityMask[:] = 1
        else: visibilityMask[db.elementSets[region]] = 1
        for action in self._viewRegionElementTypesActionGroup.actions():
            if not action.isChecked():
                visibilityMask[np.where(db.types == action.text())[0]] = 0
        self._viewport.meshView.applyCellVisibilityMask(visibilityMask)
        self._viewport.plotNodeContour(draw=False)
        self._viewport.plotCentroidContour(draw=False)
        self._viewport.draw()

    def _onViewRegionShowUnconnectedNodesActionTriggered(self, value: bool) -> None:
        """On view > region > show unconnected nodes action triggered."""
        if self._viewport.meshView is None: return
        self._viewport.meshView.setRenderUnconnectedPoints(value)
        self._viewport.plotNodeContour(draw=False)
        self._viewport.draw()

    def _onViewMirrorActionTriggered(self) -> None:
        """On view > mirror action triggered."""
        if self._viewport.meshView is None: return
        self._viewport.meshView.mirror(
            planeYZ=self._viewMirrorXAction.isChecked(),
            planeXZ=self._viewMirrorYAction.isChecked(),
            planeXY=self._viewMirrorZAction.isChecked(),
        )
        self._viewport.draw()

    def _onViewRenderStyleActionTriggered(self) -> None:
        """On view > render style action triggered."""
        if self._viewport.meshView is None: return
        self._viewport.meshView.setRenderStyle(RenderStyles(self._viewRenderStyleActionGroup.checkedAction().text()))
        self._viewport.draw()

    def _onViewRenderStyleLightingActionTriggered(self) -> None:
        """On view > render style > lighting action triggered."""
        if self._viewport.meshView is None: return
        self._viewport.meshView.setLightingEnabled(self._viewRenderStyleLightingAction.isChecked())
        self._viewport.draw()

    def _onViewColormapActionTriggered(self) -> None:
        """On view > colormap action triggered."""
        self._viewport.legend.rebuild(Spectrums(self._viewColormapActionGroup.checkedAction().text()))
        self._viewport.draw()

    def _onViewDeformationScaleFactorActionTriggered(self) -> None:
        """On view > deformation scale factor action triggered."""
        value, ok = QInputDialog.getDouble(
            self,
            "Apply Deformation Scale Factor",
            "Deformation scale factor:",
            value=1.0,
            decimals=6
        )
        if ok: self._viewport.applyDeformation(scale=value, draw=True)

    def _onPrintActionTriggered(self) -> None:
        """On print action triggered."""
        if pngFile := QFileDialog.getSaveFileName(
            parent=self,
            caption="Print Viewport",
            filter="PNG Image Files (*.png)",
            options=QFileDialog.Option.DontUseNativeDialog
        )[0]:
            if not pngFile.lower().endswith(".png"): pngFile += ".png"
            self._viewport.print(pngFile)

    def _onPauseFrameActionTriggered(self) -> None:
        """On pause frame action triggered."""
        self._viewport.setUseGlobalRange(False)
        self._animationTimer.stop()

    def _onPlayFrameActionTriggered(self) -> None:
        """On play frame action triggered."""
        self._viewport.setUseGlobalRange(True)
        self._animationTimer.start()

    def _onAnimationTimerTimeout(self) -> None:
        """On animation timer timeout."""
        if self._viewport.meshView is None or self._viewport.currentTime is None: return
        timeIndex: int = int(np.where(self._viewport.meshView.database.times == self._viewport.currentTime)[0][0])
        if timeIndex == self._viewport.meshView.database.times.size - 1: self._viewport.goToFirstFrame()
        else: self._viewport.goToNextFrame()

    def _onResultsTreeCurrentItemChanged(self) -> None:
        """On results tree current item changed."""

        # get selected branch
        branch: list[QTreeWidgetItem] = []
        item: QTreeWidgetItem | None = self._resultsTree.currentItem()
        while item is not None: # type: ignore
            branch.append(item)
            item = item.parent()
        branch.reverse()
        depth: int = len(branch)

        # handle selection
        if depth > 2 and branch[-1].childCount() == 0:
            outputType: str = branch[1].text(0)
            header: str = ".".join(item.text(0) for item in branch[2:])
            match outputType:
                case "Node Output": self._viewport.plotNodeContour(header)
                case "Element Output": self._viewport.plotCentroidContour(header)
                case _: raise NotImplementedError()
        else:
            self._viewport.clearContourPlot()

    def showEvent(self, event: QShowEvent) -> None:
        """The show event."""
        super().showEvent(event)
        self._viewport.start()

    def setDatabase(self, database: Database) -> None:
        """Sets the finite element database."""
        self._viewport.setMeshView(MeshView(database))

        # results tree
        self._resultsTree.clear()
        root: QTreeWidgetItem = QTreeWidgetItem(self._resultsTree.invisibleRootItem(), ("Output Database",))
        root.setExpanded(True)
        for title, headers in ("Node Output", database.nodeHeaders), ("Element Output", database.centroidHeaders):
            outputItem: QTreeWidgetItem = QTreeWidgetItem(root, (title,))
            for header in headers:
                parent: QTreeWidgetItem = outputItem
                for token in header.split("."):
                    child: QTreeWidgetItem
                    for i in range(parent.childCount()):
                        if parent.child(i).text(0) == token:
                            child = parent.child(i)
                            break
                    else:
                        child = QTreeWidgetItem(parent, (token,))
                    parent = child

        # dynamic menus
        while len(actions := self._viewRegionMenu.actions()) > 0:
            self._viewRegionMenu.removeAction(action := actions[-1])
            action.deleteLater()
        self._viewRegionMenu.addSection("Element Sets")
        for i, name in enumerate(["[All Elements]"] + [*database.elementSets.keys()]):
            action: QAction = QAction(self._viewRegionMenu)
            action.setText(name)
            action.setChecked(i == 0)
            action.setCheckable(True)
            action.triggered.connect(self._onViewRegionActionTriggered)
            self._viewRegionMenu.addAction(action)
            self._viewRegionElementSetsActionGroup.addAction(action)
        self._viewRegionMenu.addSection("Element Types")
        for type in np.unique(database.types):
            action: QAction = QAction(self._viewRegionMenu)
            action.setText(type)
            action.setChecked(True)
            action.setCheckable(True)
            action.triggered.connect(self._onViewRegionActionTriggered)
            self._viewRegionMenu.addAction(action)
            self._viewRegionElementTypesActionGroup.addAction(action)
        self._viewRegionMenu.addSection("Other Options")
        showUnconnectedNodesAction: QAction = QAction(self._viewRegionMenu)
        showUnconnectedNodesAction.setText("Show Unconnected Nodes")
        showUnconnectedNodesAction.setCheckable(True)
        showUnconnectedNodesAction.setChecked(
            self._viewport.meshView is not None and
            self._viewport.meshView.renderUnconnectedPoints()
        )
        showUnconnectedNodesAction.triggered.connect(self._onViewRegionShowUnconnectedNodesActionTriggered)
        self._viewRegionMenu.addAction(showUnconnectedNodesAction)
