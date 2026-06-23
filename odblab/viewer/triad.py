from vtkmodules.vtkRenderingAnnotation import vtkAxesActor
from vtkmodules.vtkInteractionWidgets import vtkOrientationMarkerWidget
from vtkmodules.vtkRenderingCore import vtkRenderWindowInteractor

class Triad:
    """Viewport triad."""

    def __init__(self) -> None:
        """Viewport triad constructor."""

        # axes actor
        self._actor: vtkAxesActor = vtkAxesActor()
        self._actor.GetXAxisCaptionActor2D().GetTextActor().SetTextScaleModeToNone()
        self._actor.GetYAxisCaptionActor2D().GetTextActor().SetTextScaleModeToNone()
        self._actor.GetZAxisCaptionActor2D().GetTextActor().SetTextScaleModeToNone()
        self._actor.GetXAxisCaptionActor2D().GetCaptionTextProperty().SetFontSize(18)
        self._actor.GetYAxisCaptionActor2D().GetCaptionTextProperty().SetFontSize(18)
        self._actor.GetZAxisCaptionActor2D().GetCaptionTextProperty().SetFontSize(18)
        self._actor.GetXAxisCaptionActor2D().GetCaptionTextProperty().SetFontFamilyToCourier()
        self._actor.GetYAxisCaptionActor2D().GetCaptionTextProperty().SetFontFamilyToCourier()
        self._actor.GetZAxisCaptionActor2D().GetCaptionTextProperty().SetFontFamilyToCourier()
        self._actor.GetXAxisCaptionActor2D().GetCaptionTextProperty().ItalicOff()
        self._actor.GetYAxisCaptionActor2D().GetCaptionTextProperty().ItalicOff()
        self._actor.GetZAxisCaptionActor2D().GetCaptionTextProperty().ItalicOff()
        self._actor.GetXAxisCaptionActor2D().GetCaptionTextProperty().ShadowOn()
        self._actor.GetYAxisCaptionActor2D().GetCaptionTextProperty().ShadowOn()
        self._actor.GetZAxisCaptionActor2D().GetCaptionTextProperty().ShadowOn()
        self._actor.GetXAxisCaptionActor2D().GetCaptionTextProperty().BoldOff()
        self._actor.GetYAxisCaptionActor2D().GetCaptionTextProperty().BoldOff()
        self._actor.GetZAxisCaptionActor2D().GetCaptionTextProperty().BoldOff()
        self._actor.SetTipTypeToCone()
        self._actor.SetShaftTypeToCylinder()
        self._actor.SetConeResolution(64)
        self._actor.SetCylinderResolution(64)
        self._actor.SetConeRadius(0.5)
        self._actor.SetCylinderRadius(0.08)
        self._actor.SetNormalizedTipLength(0.3, 0.3, 0.3)
        self._actor.SetNormalizedShaftLength(0.7, 0.7, 0.7)
        self._actor.SetNormalizedLabelPosition(1.25, 1.25, 1.25)

        # orientation marker widget
        self._widget: vtkOrientationMarkerWidget = vtkOrientationMarkerWidget()
        self._widget.SetOrientationMarker(self._actor)
        self._widget.SetViewport(0.75, 0.0, 1.0, 0.25)

    def setInteractor(self, interactor: vtkRenderWindowInteractor) -> None:
        """Sets the render window interactor."""
        self._widget.SetInteractor(interactor)
        self._widget.EnabledOn()
        self._widget.InteractiveOff()

    def textColor(self) -> tuple[float, float, float]:
        """Gets the text color."""
        return self._actor.GetXAxisCaptionActor2D().GetCaptionTextProperty().GetColor()

    def setTextColor(self, value: tuple[float, float, float]) -> None:
        """Sets the text color."""
        self._actor.GetXAxisCaptionActor2D().GetCaptionTextProperty().SetColor(value)
        self._actor.GetYAxisCaptionActor2D().GetCaptionTextProperty().SetColor(value)
        self._actor.GetZAxisCaptionActor2D().GetCaptionTextProperty().SetColor(value)
