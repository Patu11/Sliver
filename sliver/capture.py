"""Region selection overlay with its magnifier."""

from __future__ import annotations

import win32con
import win32gui
from PyQt6.QtCore import pyqtSignal, QObject, QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from .thumbnail import DwmThumbnail


class MagnifierCrosshair(QWidget):
    """A transparent top-level crosshair kept above a DWM thumbnail window."""

    SIZE = 25
    OUTLINE_WIDTH = 5
    INNER_WIDTH = 1
    MARGIN = 3

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def move_to_center(self, center: QPoint) -> None:
        """Place this top-level widget around a global content-coordinate center."""

        x = center.x() - self.width() // 2
        y = center.y() - self.height() // 2
        self.move(x, y)
        hwnd = int(self.winId())
        extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        extended_style |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, extended_style)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            x,
            y,
            self.width(),
            self.height(),
            win32con.SWP_NOACTIVATE,
        )

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()
        horizontal_start = self.MARGIN
        horizontal_end = self.width() - self.MARGIN - 1
        vertical_start = self.MARGIN
        vertical_end = self.height() - self.MARGIN - 1

        painter.setPen(QPen(QColor(0, 0, 0), self.OUTLINE_WIDTH))
        painter.drawLine(horizontal_start, center.y(), horizontal_end, center.y())
        painter.drawLine(center.x(), vertical_start, center.x(), vertical_end)
        painter.setPen(QPen(QColor(255, 235, 80), self.INNER_WIDTH))
        painter.drawLine(horizontal_start, center.y(), horizontal_end, center.y())
        painter.drawLine(center.x(), vertical_start, center.x(), vertical_end)


class CaptureMagnifier(QWidget):
    """A temporary, click-through DWM view of client pixels beneath a capture cursor."""

    SOURCE_SIZE = 25
    SCALE = 4
    DISPLAY_SIZE = SOURCE_SIZE * SCALE
    BORDER_WIDTH = 2
    CURSOR_GAP = 16

    unavailable = pyqtSignal(str)

    def __init__(self, source_hwnd: int, client_width: int, client_height: int) -> None:
        super().__init__()
        self.source_hwnd = source_hwnd
        self.client_width = client_width
        self.client_height = client_height
        self.thumbnail: DwmThumbnail | None = None
        self.crosshair: MagnifierCrosshair | None = MagnifierCrosshair()
        self._disabled = False
        self._reported_unavailable = False

        self.setFixedSize(
            self.DISPLAY_SIZE + self.BORDER_WIDTH * 2,
            self.DISPLAY_SIZE + self.BORDER_WIDTH * 2,
        )
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def _content_rect(self) -> QRect:
        return self.rect().adjusted(
            self.BORDER_WIDTH,
            self.BORDER_WIDTH,
            -self.BORDER_WIDTH,
            -self.BORDER_WIDTH,
        )

    def _disable(self) -> None:
        if self._disabled:
            return
        self._disabled = True
        self.close_thumbnail()
        self.hide()
        if not self._reported_unavailable:
            self._reported_unavailable = True
            self.unavailable.emit("Live DWM magnifier unavailable; capture continues.")

    def _ensure_thumbnail(self) -> bool:
        if self._disabled:
            return False
        if self.thumbnail is not None:
            return True
        try:
            self.thumbnail = DwmThumbnail(int(self.winId()), self.source_hwnd)
            return True
        except Exception:
            self._disable()
            return False

    def update_for_cursor(
        self, source_position: tuple[int, int], global_position: QPoint
    ) -> None:
        """Update a bounded DWM source crop and place the viewport near the cursor."""

        screen = QApplication.screenAt(global_position) or QApplication.primaryScreen()
        if screen is None or self.client_width <= 0 or self.client_height <= 0:
            self._disable()
            return

        source_x = max(0, min(self.client_width - 1, source_position[0]))
        source_y = max(0, min(self.client_height - 1, source_position[1]))
        fragment_width = min(self.SOURCE_SIZE, self.client_width)
        fragment_height = min(self.SOURCE_SIZE, self.client_height)
        fragment_x = max(
            0,
            min(source_x - self.SOURCE_SIZE // 2, self.client_width - fragment_width),
        )
        fragment_y = max(
            0,
            min(source_y - self.SOURCE_SIZE // 2, self.client_height - fragment_height),
        )
        self._position_near_cursor(screen.availableGeometry(), global_position)
        if not self.isVisible():
            self.show()
        self.raise_()
        if not self._ensure_thumbnail():
            return
        try:
            self.thumbnail.update(
                (
                    fragment_x,
                    fragment_y,
                    fragment_x + fragment_width,
                    fragment_y + fragment_height,
                ),
                destination_rect=(
                    self._content_rect().left(),
                    self._content_rect().top(),
                    self._content_rect().right() + 1,
                    self._content_rect().bottom() + 1,
                ),
            )
            self._show_crosshair()
        except Exception:
            self._disable()

    def _position_near_cursor(self, available: QRect, cursor: QPoint) -> None:
        right_x = cursor.x() + self.CURSOR_GAP
        left_x = cursor.x() - self.width() - self.CURSOR_GAP
        x = right_x if right_x + self.width() <= available.right() + 1 else left_x
        above_y = cursor.y() - self.height() - self.CURSOR_GAP
        below_y = cursor.y() + self.CURSOR_GAP
        y = above_y if above_y >= available.top() else below_y
        x = max(available.left(), min(x, available.right() - self.width() + 1))
        y = max(available.top(), min(y, available.bottom() - self.height() + 1))
        self.move(x, y)
        hwnd = int(self.winId())
        extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        extended_style |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, extended_style)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            x,
            y,
            self.width(),
            self.height(),
            win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
        )
        self._position_crosshair()

    def _position_crosshair(self) -> None:
        """Center the separate crosshair over the DWM thumbnail content rectangle."""

        if self.crosshair is None:
            return
        content = self._content_rect()
        center = QPoint(
            self.x() + content.left() + content.width() // 2,
            self.y() + content.top() + content.height() // 2,
        )
        self.crosshair.move_to_center(center)

    def _show_crosshair(self) -> None:
        if self.crosshair is None:
            return
        self.crosshair.show()
        self.crosshair.raise_()
        self._position_crosshair()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(102, 210, 255))

    def close_thumbnail(self) -> None:
        thumbnail = self.thumbnail
        self.thumbnail = None
        try:
            if thumbnail is not None:
                thumbnail.close()
        finally:
            self._close_crosshair()

    def _close_crosshair(self) -> None:
        crosshair = self.crosshair
        self.crosshair = None
        if crosshair is not None:
            crosshair.hide()
            crosshair.close()
            crosshair.deleteLater()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.close_thumbnail()
        event.accept()


class SelectionOverlay(QWidget):
    """A topmost selector whose local coordinates map to source client pixels."""

    selected = pyqtSignal(tuple)
    cancelled = pyqtSignal()
    magnifier_unavailable = pyqtSignal(str)

    def __init__(self, source_hwnd: int) -> None:
        super().__init__()
        self.source_hwnd = source_hwnd
        self._done = False
        self._start: QPoint | None = None
        self._current: QPoint | None = None
        self._client_origin = win32gui.ClientToScreen(source_hwnd, (0, 0))
        _, _, self._client_width, self._client_height = win32gui.GetClientRect(
            source_hwnd
        )
        self._magnifier: CaptureMagnifier | None = CaptureMagnifier(
            source_hwnd, self._client_width, self._client_height
        )
        self._magnifier.unavailable.connect(self.magnifier_unavailable.emit)
        self.destroyed.connect(self._selection_destroyed)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    def show_for_source(self) -> None:
        self.resize(self._client_width, self._client_height)
        self.show()
        self._set_native_geometry()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self._update_magnifier(QCursor.pos())

    def _set_native_geometry(self) -> None:
        hwnd = int(self.winId())
        left, top = self._client_origin
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            left,
            top,
            self._client_width,
            self._client_height,
            win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
        )

    def _clamp_widget_point(self, point: QPoint) -> QPoint:
        return QPoint(
            max(0, min(self.width(), point.x())),
            max(0, min(self.height(), point.y())),
        )

    def _source_point(self, point: QPoint) -> tuple[int, int]:
        point = self._clamp_widget_point(point)
        x = round(point.x() * self._client_width / max(1, self.width()))
        y = round(point.y() * self._client_height / max(1, self.height()))
        return (
            max(0, min(self._client_width, x)),
            max(0, min(self._client_height, y)),
        )

    def _update_magnifier(self, global_position: QPoint) -> None:
        if self._magnifier is None:
            return
        local_position = self._clamp_widget_point(self.mapFromGlobal(global_position))
        self._magnifier.update_for_cursor(
            self._source_point(local_position), global_position
        )

    def _close_magnifier(self) -> None:
        magnifier = self._magnifier
        self._magnifier = None
        if magnifier is not None:
            magnifier.close()
            magnifier.deleteLater()

    def _selection_destroyed(self, _: QObject | None = None) -> None:
        self._close_magnifier()

    def _widget_rectangle(self) -> QRect | None:
        if self._start is None or self._current is None:
            return None
        return QRect(self._start, self._current).normalized()

    def _source_rectangle(self) -> tuple[int, int, int, int] | None:
        if self._start is None or self._current is None:
            return None
        start_x, start_y = self._source_point(self._start)
        current_x, current_y = self._source_point(self._current)
        left, right = sorted((start_x, current_x))
        top, bottom = sorted((start_y, current_y))
        if right - left < 2 or bottom - top < 2:
            return None
        return left, top, right, bottom

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._update_magnifier(event.globalPosition().toPoint())
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = self._clamp_widget_point(event.position().toPoint())
            self._current = self._start
            self.grabMouse()
            self.update()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._update_magnifier(event.globalPosition().toPoint())
        if self._start is not None:
            self._current = self._clamp_widget_point(event.position().toPoint())
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        self._update_magnifier(event.globalPosition().toPoint())
        self._current = self._clamp_widget_point(event.position().toPoint())
        self.releaseMouse()
        rectangle = self._source_rectangle()
        self._done = True
        self.hide()
        self._close_magnifier()
        if rectangle:
            self.selected.emit(rectangle)
        else:
            self.cancelled.emit()
        self.deleteLater()
        event.accept()

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._close_magnifier()
        if not self._done:
            self._done = True
            self.cancelled.emit()
        event.accept()

    def cancel(self) -> None:
        if self._done:
            return
        self._done = True
        if self._start is not None:
            self.releaseMouse()
        self.hide()
        self._close_magnifier()
        self.cancelled.emit()
        self.deleteLater()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(5, 10, 18, 188))

        rectangle = self._widget_rectangle()
        if rectangle and rectangle.width() > 0 and rectangle.height() > 0:
            painter.fillRect(rectangle, QColor(71, 177, 255, 58))
            painter.setPen(QPen(QColor(133, 210, 255), 2))
            painter.drawRect(rectangle.adjusted(1, 1, -1, -1))
        else:
            painter.setPen(QColor(225, 238, 250))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Drag to select a capture region\nPress Esc to cancel",
            )
