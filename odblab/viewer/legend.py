from odblab.viewer import Spectrums, Renderable
from vtkmodules.vtkCommonCore import vtkLookupTable
from vtkmodules.vtkRenderingAnnotation import vtkScalarBarActor
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction, vtkMapper

class Legend(Renderable):
    """Viewport legend."""

    def __init__(self) -> None:
        """Legend constructor."""
        super().__init__()

        # lookup table
        self._lookupTable: vtkLookupTable = vtkLookupTable()

        # actor
        self._actor: vtkScalarBarActor = vtkScalarBarActor()
        self._actor.SetLookupTable(self._lookupTable)
        self._actor.UnconstrainedFontSizeOn()
        self._actor.GetLabelTextProperty().SetFontSize(18)
        self._actor.GetLabelTextProperty().SetFontFamilyToCourier()
        self._actor.GetLabelTextProperty().ItalicOff()
        self._actor.GetLabelTextProperty().ShadowOn()
        self._actor.GetLabelTextProperty().BoldOff()
        self._actor.SetPosition(0.025, 0.45)
        self._actor.SetWidth(0.075)
        self._actor.SetHeight(0.5)
        self._actor.SetLabelFormat("{:+.3E}")

        # prop list
        self._props += [self._actor]

        # first build
        self._spectrum: Spectrums = Spectrums.Abaqus
        self._intervals: int = 12
        self._continuous: bool = False
        self._reversed: bool = False
        self._log: bool = False
        self.rebuild(self._spectrum, self._intervals, self._continuous, self._reversed)

    def assignLookupTableToMapper(self, mapper: vtkMapper) -> None:
        """Assigns the internal lookup table to the specified mapper."""
        mapper.SetLookupTable(self._lookupTable)

    def rebuild(self, spectrum: Spectrums | None = None, intervals: int | None = None, continuous: bool | None = None,
        reversed: bool | None = None, log: bool | None = None) -> None:
        """Rebuilds the legend."""
        if spectrum is not None: self._spectrum = spectrum
        if intervals is not None: self._intervals = intervals
        if continuous is not None: self._continuous = continuous
        if reversed is not None: self._reversed = reversed
        if log is not None: self._log = log

        # counts
        colorCount: int = self._intervals if not self._continuous else 128
        labelCount: int = (self._intervals + 1) if not continuous else 10

        # color function
        colorFunction: vtkColorTransferFunction = vtkColorTransferFunction()
        for i, rgb in enumerate(self._spectrum.baseColors): colorFunction.AddRGBPoint(i, *rgb)

        # weights
        n: int = len(self._spectrum.baseColors) - 1
        a, b = (0, n) if not reversed else (n, 0)
        weights: list[float] = [a + i*(b - a)/(colorCount - 1) for i in range(colorCount)]

        # update lookup table
        self._lookupTable.SetNanColor(1.0, 1.0, 1.0, 1.0)
        self._lookupTable.SetNumberOfTableValues(colorCount)
        for i, weight in enumerate(weights): self._lookupTable.SetTableValue(i, *colorFunction.GetColor(weight))
        if self._log: self._lookupTable.SetScaleToLog10()
        else: self._lookupTable.SetScaleToLinear()
        self._lookupTable.Build()

        # update actor
        self._actor.SetNumberOfLabels(labelCount)

    def isVisible(self) -> bool:
        """Gets the legend visibility."""
        return bool(self._actor.GetVisibility())

    def setVisible(self, value: bool) -> None:
        """Sets the legend visibility."""
        self._actor.SetVisibility(value)

    def textColor(self) -> tuple[float, float, float]:
        """Gets the text color."""
        return self._actor.GetLabelTextProperty().GetColor()

    def setTextColor(self, value: tuple[float, float, float]) -> None:
        """Sets the text color."""
        self._actor.GetLabelTextProperty().SetColor(value)
