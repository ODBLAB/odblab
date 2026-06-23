from vtkmodules.vtkRenderingCore import vtkRenderer, vtkProp, vtkActor

class Renderable:
    """Represents a VTK-based renderable object."""

    def __init__(self) -> None:
        """Constructor."""
        self._props: list[vtkProp] = []
        self._renderedProps: list[vtkProp] = []
        self._renderer: vtkRenderer | None = None

    def attach(self, renderer: vtkRenderer) -> None:
        """Attaches this object to the specified VTK renderer."""
        if self._renderer is renderer: return
        if self._renderer is not None: self.detach()
        self._renderer = renderer
        for prop in self._props:
            if not self._renderer.GetViewProps().IsItemPresent(prop):
                self._renderer.AddViewProp(prop)
                self._renderedProps.append(prop)

    def detach(self) -> None:
        """Detaches this object from the current VTK renderer."""
        if self._renderer is None: return
        for prop in self._renderedProps:
            if self._renderer.GetViewProps().IsItemPresent(prop):
                self._renderer.RemoveViewProp(prop)
        self._renderedProps.clear()
        self._renderer = None

    def reattach(self) -> None:
        """Reattach this object to the current VTK renderer."""
        if self._renderer is None: return
        renderer: vtkRenderer = self._renderer
        self.detach()
        self.attach(renderer)

    def setLightingEnabled(self, value: bool) -> None:
        """Sets lighting enabled/disabled."""
        for actor in (prop for prop in self._props if isinstance(prop, vtkActor)):
            actor.GetProperty().SetLighting(value)

    def lightingEnabled(self) -> bool:
        """Gets lighting enabled/disabled."""
        for actor in (prop for prop in self._props if isinstance(prop, vtkActor)):
            return actor.GetProperty().GetLighting()
        return False
