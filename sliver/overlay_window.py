"""Always-on-top overlay windows that host a DWM thumbnail."""

from __future__ import annotations

from typing import TYPE_CHECKING

import win32con
import win32gui
from PyQt6.QtCore import QEvent, QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from .models import Region
from .thumbnail import DwmThumbnail

if TYPE_CHECKING:
    from .controller import OverlayApplication


class EditBorderOverlay(QWidget):
    """A click-through top-level outline shown while an overlay is editable."""

    BORDER_WIDTH = 3
    BORDER_COLOR = QColor(46, 204, 113)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def sync_to_overlay(self, overlay: "DwmOverlayWidget") -> None:
        """Place the outline around the overlay's native outer rectangle."""

        if not overlay.isVisible():
            self.hide()
            return
        left, top, right, bottom = win32gui.GetWindowRect(overlay.hwnd)
        width = right - left
        height = bottom - top
        border = self.BORDER_WIDTH
        self.setGeometry(
            left - border,
            top - border,
            width + border * 2,
            height + border * 2,
        )
        self.show()

        # Qt's transparent-input flag handles Qt events; these styles make the
        # native top-level window click-through as well.
        hwnd = int(self.winId())
        extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        extended_style |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, extended_style)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            left - border,
            top - border,
            width + border * 2,
            height + border * 2,
            win32con.SWP_SHOWWINDOW
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_FRAMECHANGED,
        )
        self.raise_()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.BORDER_COLOR, self.BORDER_WIDTH))
        inset = (self.BORDER_WIDTH + 1) // 2
        painter.drawRect(self.rect().adjusted(inset, inset, -inset, -inset))


class DwmOverlayWidget(QWidget):
    """A Qt host window for a DWM-clipped thumbnail."""

    def __init__(
        self,
        controller: "OverlayApplication",
        region: Region,
        source_hwnd: int,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.region = region
        self.source_hwnd = source_hwnd
        self.thumbnail: DwmThumbnail | None = None
        self._edit_border: EditBorderOverlay | None = None
        self._positioning = False
        self._is_edit_mode: bool | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setMinimumSize(1, 1)
        self.setMouseTracking(True)

    @property
    def hwnd(self) -> int:
        return int(self.winId())

    def create_thumbnail(self) -> None:
        self.resize(self.region.overlay_width, self.region.overlay_height)
        self.setWindowOpacity(self.region.opacity / 100)
        self.show()
        self._set_native_geometry()
        try:
            self.thumbnail = DwmThumbnail(self.hwnd, self.source_hwnd)
            self.update_thumbnail()
            self.set_edit_mode(self.controller.edit_mode)
        except Exception:
            self.close_thumbnail()
            raise

    def _set_native_geometry(self) -> None:
        self._positioning = True
        try:
            win32gui.SetWindowPos(
                self.hwnd,
                win32con.HWND_TOPMOST,
                self.region.overlay_x,
                self.region.overlay_y,
                self.region.overlay_width,
                self.region.overlay_height,
                win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
            )
        finally:
            self._positioning = False
        self._sync_edit_border()

    def _sync_edit_border(self) -> None:
        if self._edit_border and self._is_edit_mode:
            self._edit_border.sync_to_overlay(self)

    def _set_edit_border_visible(self, visible: bool) -> None:
        if visible:
            if self._edit_border is None:
                self._edit_border = EditBorderOverlay()
            self._sync_edit_border()
        elif self._edit_border:
            self._edit_border.hide()

    def _close_edit_border(self) -> None:
        if self._edit_border:
            self._edit_border.close()
            self._edit_border.deleteLater()
            self._edit_border = None

    def set_edit_mode(self, enabled: bool) -> None:
        if self._is_edit_mode == enabled:
            self._set_edit_border_visible(enabled)
            return
        extended_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
        if enabled:
            extended_style &= ~(win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE)
        else:
            extended_style |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE
            self.unsetCursor()
        win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, extended_style)
        win32gui.SetWindowPos(
            self.hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_FRAMECHANGED,
        )
        self._is_edit_mode = enabled
        self._set_edit_border_visible(enabled)
        self.update_thumbnail()

    def update_thumbnail(self) -> None:
        self.setWindowOpacity(self.region.opacity / 100)
        if self.thumbnail is None:
            return
        self.thumbnail.update(
            (
                self.region.x,
                self.region.y,
                self.region.x + self.region.width,
                self.region.y + self.region.height,
            ),
            0,
        )

    def sync_size_to_capture(self) -> None:
        self._set_native_geometry()
        self.update_thumbnail()

    def close_thumbnail(self) -> None:
        if self.thumbnail:
            self.thumbnail.close()
            self.thumbnail = None
        self._close_edit_border()
        self.hide()
        self.deleteLater()

    def _resize_edges(self, point: QPoint) -> Qt.Edge:
        border = 8
        edges = Qt.Edge(0)
        if point.x() <= border:
            edges |= Qt.Edge.LeftEdge
        elif point.x() >= self.width() - border:
            edges |= Qt.Edge.RightEdge
        if point.y() <= border:
            edges |= Qt.Edge.TopEdge
        elif point.y() >= self.height() - border:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self.controller.edit_mode or event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        window = self.windowHandle()
        edges = self._resize_edges(event.position().toPoint())
        if window and edges:
            window.startSystemResize(edges)
        elif window:
            window.startSystemMove()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self.controller.edit_mode:
            event.ignore()
            return
        edges = self._resize_edges(event.position().toPoint())
        cursor = (
            Qt.CursorShape.SizeFDiagCursor
            if edges
            in (
                Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
                Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
            )
            else (
                Qt.CursorShape.SizeBDiagCursor
                if edges
                in (
                    Qt.Edge.RightEdge | Qt.Edge.TopEdge,
                    Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
                )
                else (
                    Qt.CursorShape.SizeHorCursor
                    if edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge)
                    else (
                        Qt.CursorShape.SizeVerCursor
                        if edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge)
                        else Qt.CursorShape.SizeAllCursor
                    )
                )
            )
        )
        self.setCursor(cursor)
        event.accept()

    def moveEvent(self, event: QEvent) -> None:
        super().moveEvent(event)
        self._sync_edit_border()
        self._store_geometry()

    def resizeEvent(self, event: QEvent) -> None:
        super().resizeEvent(event)
        if self.thumbnail:
            QTimer.singleShot(0, self.update_thumbnail)
        self._sync_edit_border()
        self._store_geometry()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._close_edit_border()
        if self.thumbnail:
            self.thumbnail.close()
            self.thumbnail = None
        super().closeEvent(event)

    def _store_geometry(self) -> None:
        if self._positioning or not self.isVisible() or not self.thumbnail:
            return
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        width, height = right - left, bottom - top
        if (
            left == self.region.overlay_x
            and top == self.region.overlay_y
            and width == self.region.overlay_width
            and height == self.region.overlay_height
        ):
            return
        self.region.overlay_x = left
        self.region.overlay_y = top
        self.region.overlay_width = max(1, width)
        self.region.overlay_height = max(1, height)
        self.controller.save_soon()
        self.controller.overlay_geometry_changed(self.region)
