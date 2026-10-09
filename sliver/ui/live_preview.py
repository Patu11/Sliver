"""Live DWM preview of the selected region."""

from __future__ import annotations

import win32gui
from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from ..models import Region
from ..thumbnail import DwmThumbnail


class LivePreview(QFrame):
    """Shows the selected region inside the control window through DWM."""

    PADDING = 8

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("previewFrame")
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        self.placeholder = QLabel()
        self.placeholder.setObjectName("muted")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)
        layout.addWidget(self.placeholder)
        self._region: Region | None = None
        self._source_hwnd: int | None = None
        self._thumbnail: DwmThumbnail | None = None

    def set_target(self, region: Region | None, source_hwnd: int | None) -> None:
        if source_hwnd != self._source_hwnd:
            self._close()
        self._region = region
        self._source_hwnd = source_hwnd
        self.refresh()

    def refresh(self) -> None:
        region, source_hwnd = self._region, self._source_hwnd
        if region is None:
            self._close()
            return
        if not source_hwnd or not win32gui.IsWindow(source_hwnd):
            self._close()
            self._show_placeholder(
                "The source window isn't running.\nOpen it to see a live preview."
            )
            return
        if win32gui.IsIconic(source_hwnd):
            self._close()
            self._show_placeholder("The source window is minimized.")
            return
        destination = self._destination_rect(region)
        if destination is None or not self.isVisible():
            self._close()
            return
        try:
            if self._thumbnail is None:
                self._thumbnail = DwmThumbnail(int(self.window().winId()), source_hwnd)
            self._thumbnail.update(
                (region.x, region.y, region.x + region.width, region.y + region.height),
                destination_rect=destination,
            )
        except RuntimeError:
            self._close()
            self._show_placeholder("Live preview is unavailable.")
            return
        self.placeholder.hide()

    def _destination_rect(self, region: Region) -> tuple[int, int, int, int] | None:
        available_width = self.width() - self.PADDING * 2
        available_height = self.height() - self.PADDING * 2
        if available_width <= 0 or available_height <= 0:
            return None
        ratio = self.devicePixelRatioF()
        aspect = region.width / max(1, region.height)
        width = min(float(available_width), region.width * 2 / ratio)
        height = width / aspect
        if height > available_height:
            height = float(available_height)
            width = height * aspect
        origin = self.mapTo(self.window(), QPoint(0, 0))
        left = origin.x() + (self.width() - width) / 2
        top = origin.y() + (self.height() - height) / 2
        return (
            round(left * ratio),
            round(top * ratio),
            round((left + width) * ratio),
            round((top + height) * ratio),
        )

    def _show_placeholder(self, text: str) -> None:
        self.placeholder.setText(text)
        self.placeholder.show()

    def _close(self) -> None:
        if self._thumbnail:
            self._thumbnail.close()
            self._thumbnail = None

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        QTimer.singleShot(0, self.refresh)

    def moveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().moveEvent(event)
        QTimer.singleShot(0, self.refresh)

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh)

    def hideEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._close()
        super().hideEvent(event)
