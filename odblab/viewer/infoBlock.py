from pathlib import Path
from odblab.viewer import Renderable
from vtkmodules.vtkRenderingCore import vtkTextActor

class InfoBlock(Renderable):
    """Viewport information text block."""

    def __init__(self) -> None:
        """Info block constructor."""
        super().__init__()
        self._lines: list[str] = [""]*4
        self._actor: vtkTextActor = vtkTextActor()
        self._actor.SetTextScaleModeToNone()
        self._actor.GetTextProperty().SetFontSize(18)
        self._actor.GetTextProperty().SetFontFamilyToCourier()
        self._actor.GetTextProperty().ItalicOff()
        self._actor.GetTextProperty().ShadowOn()
        self._actor.GetTextProperty().BoldOff()
        self._actor.GetTextProperty().SetJustificationToLeft()
        self._actor.GetTextProperty().SetVerticalJustificationToBottom()
        self._actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        self._actor.GetPositionCoordinate().SetValue(0.05, 0.05)
        self._props += [self._actor]

    def setFilePath(self, value: str | Path) -> None:
        """Sets the file path."""
        if not isinstance(value, Path): value = Path(value)
        self._lines[0] = str(value.resolve())
        self._actor.SetInput("\n".join(self._lines))

    def setDeformationScaleFactor(self, value: float) -> None:
        """Sets the deformation scale factor."""
        self._lines[1] = f"Deformation Scale Factor: {value:+.6E}"
        self._actor.SetInput("\n".join(self._lines))

    def setTime(self, value: float) -> None:
        """Sets the frame time/frequency."""
        self._lines[2] = f"Time: {value:+.9E}"
        self._actor.SetInput("\n".join(self._lines))

    def setVariable(self, value: str) -> None:
        """Sets the variable name."""
        self._lines[3] = f"Variable: {value}"
        self._actor.SetInput("\n".join(self._lines))

    def clear(self) -> None:
        """Clears all text."""
        self._lines = [""]*len(self._lines)
        self._actor.SetInput("")

    def clearVariable(self) -> None:
        """Clears the variable name."""
        self._lines[3] = ""
        self._actor.SetInput("\n".join(self._lines))

    def textColor(self) -> tuple[float, float, float]:
        """Gets the text color."""
        return self._actor.GetTextProperty().GetColor()

    def setTextColor(self, value: tuple[float, float, float]) -> None:
        """Sets the text color."""
        self._actor.GetTextProperty().SetColor(value)
