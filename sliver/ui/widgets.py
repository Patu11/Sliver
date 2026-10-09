"""Small reusable widgets."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import (
    pyqtProperty,
    pyqtSignal,
    QEasingCurve,
    QEvent,
    QObject,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ..theme import THEME


class ToggleSwitch(QAbstractButton):
    """A compact Windows 11 style on/off switch."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._position = 0.0
        self._animation = QPropertyAnimation(self, b"position", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(40, 20)

    def _get_position(self) -> float:
        return self._position

    def _set_position(self, value: float) -> None:
        self._position = value
        self.update()

    position = pyqtProperty(float, _get_position, _set_position)

    def set_checked_silently(self, checked: bool) -> None:
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self._animation.stop()
        self._set_position(1.0 if checked else 0.0)

    def _animate(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def enterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        radius = track.height() / 2
        accent = QColor(THEME["accent"])
        off = QColor(THEME["muted"])
        knob_on = QColor(THEME["on_accent"])
        if not self.isEnabled():
            for color in (accent, off, knob_on):
                color.setAlpha(90)
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent)
        else:
            painter.setPen(QPen(off, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(track, radius, radius)

        diameter = track.height() - 8 + (2 if self.underMouse() else 0)
        travel = track.width() - track.height()
        center = QPointF(
            track.left() + track.height() / 2 + travel * self._position,
            track.center().y(),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(knob_on if self.isChecked() else off)
        painter.drawEllipse(center, diameter / 2, diameter / 2)


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ElidedLabel(QLabel):
    """A single-line label that shortens its text with an ellipsis."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(1)
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        super().setText(
            self.fontMetrics().elidedText(
                self._full_text, Qt.TextElideMode.ElideRight, max(0, self.width())
            )
        )


class Toast(QFrame):
    """A transient notification anchored to the bottom of its parent."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 8, 8)
        layout.setSpacing(12)
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.action_button = QPushButton()
        self.action_button.setObjectName("linkButton")
        self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_button.clicked.connect(self._run_action)
        layout.addWidget(self.action_button)
        self._action: Callable[[], None] | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        parent.installEventFilter(self)
        self.hide()

    def show_message(
        self,
        message: str,
        action_text: str | None = None,
        action: Callable[[], None] | None = None,
    ) -> None:
        self.label.setText(message)
        self._action = action
        self.action_button.setVisible(action is not None)
        self.action_button.setText(action_text or "")
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(6000 if action else min(8000, 2500 + len(message) * 35))

    def _run_action(self) -> None:
        action = self._action
        self._action = None
        self.hide()
        if action:
            action()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        # Stay left of the details footer buttons so they remain clickable.
        width = max(220, min(440, parent.width() - 48 - 200))
        self.setFixedWidth(width)
        layout = self.layout()
        height = layout.heightForWidth(width) if layout.hasHeightForWidth() else -1
        self.setFixedHeight(height if height > 0 else self.sizeHint().height())
        self.move(24, parent.height() - self.height() - 16)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self._reposition()
        return False
