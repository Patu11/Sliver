"""Application entry point."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from .config import migrate_legacy_data
from .controller import OverlayApplication
from .resources import app_icon
from .theme import apply_theme
from .win32_api import enable_per_monitor_dpi_awareness, set_app_user_model_id


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("This application requires Windows.")
    set_app_user_model_id()
    enable_per_monitor_dpi_awareness()
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Sliver")
    qt_app.setWindowIcon(app_icon())
    qt_app.setQuitOnLastWindowClosed(False)
    apply_theme(qt_app)
    migrate_legacy_data()
    controller = OverlayApplication(qt_app)
    qt_app.aboutToQuit.connect(controller.shutdown)
    controller.run()
    return qt_app.exec()
