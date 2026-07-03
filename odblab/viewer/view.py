import sys
from typing import Literal
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from odblab.viewer import MainWindow
from odblab.core import Database

def view(database: Database, theme: Literal["light", "dark"] | None = None) -> int:
    """Launches the viewer application."""

    # create application object
    app: QApplication = obj if isinstance(obj := QApplication.instance(), QApplication) else QApplication(sys.argv)
    app.setStyle("Fusion")
    if theme is not None:
        match theme:
            case "dark": app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
            case "light": app.styleHints().setColorScheme(Qt.ColorScheme.Light)
            case _: raise ValueError(f"invalid theme; available options: 'light', 'dark'")

    # create main window
    mainWindow: MainWindow = MainWindow()
    mainWindow.setDatabase(database)
    mainWindow.show()

    # launch application
    return app.exec()
