"""Searchable popup for choosing a source window."""

from __future__ import annotations

import os
from typing import Callable

from PyQt6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import SourceReference, SourceWindow
from ..resources import process_icon
from ..win32_api import process_image_path
from ..windows import source_matches
from .widgets import ElidedLabel


class SourceRow(QWidget):
    """One window entry in the source picker."""

    def __init__(self, source: SourceWindow, recent: bool) -> None:
        super().__init__()
        path = process_image_path(source.reference.process_id)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)
        icon = QLabel()
        icon.setPixmap(process_icon(path).pixmap(24, 24))
        icon.setFixedSize(24, 24)
        layout.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(0)
        title = ElidedLabel(source.reference.title)
        title.setObjectName("cardTitle")
        process = os.path.basename(path) if path else source.reference.class_name
        subtitle = ElidedLabel(
            f"{'Last used · ' if recent else ''}{process} · PID {source.reference.process_id}"
        )
        subtitle.setObjectName("cardSubtitle")
        text.addWidget(title)
        text.addWidget(subtitle)
        layout.addLayout(text, 1)
        self.search_text = f"{source.reference.title} {process}".lower()


class SourcePickerDialog(QDialog):
    """A searchable popup that lists windows available for capture."""

    def __init__(
        self,
        parent: QWidget,
        load_sources: Callable[[], list[SourceWindow]],
        recent: SourceReference | None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("sourcePicker")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.resize(560, 460)
        self._load_sources = load_sources
        self._recent = recent
        self._sources: list[SourceWindow] = []
        self.selected: SourceWindow | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        title = QLabel("Choose a window to capture from")
        title.setObjectName("pickerTitle")
        layout.addWidget(title)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by window title or app…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._accept_current)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.setObjectName("sourceList")
        self.list.itemActivated.connect(lambda _: self._accept_current())
        self.list.itemDoubleClicked.connect(lambda _: self._accept_current())
        layout.addWidget(self.list, 1)
        self.empty_label = QLabel("No matching windows. Minimized windows are not listed.")
        self.empty_label.setObjectName("muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        footer = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._populate)
        footer.addWidget(refresh)
        footer.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.capture_button = QPushButton("Select area")
        self.capture_button.setObjectName("primaryButton")
        self.capture_button.clicked.connect(self._accept_current)
        footer.addWidget(self.capture_button)
        layout.addLayout(footer)
        self._populate()

    def place_near(self, anchor: QWidget | None) -> None:
        parent = self.parentWidget()
        if anchor is not None:
            position = anchor.mapToGlobal(QPoint(0, anchor.height() + 6))
        elif parent is not None:
            center = parent.mapToGlobal(parent.rect().center())
            position = QPoint(center.x() - self.width() // 2, center.y() - self.height() // 2)
        else:
            position = QCursor.pos()
        screen = QApplication.screenAt(position) or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            position.setX(max(available.left(), min(position.x(), available.right() - self.width())))
            position.setY(max(available.top(), min(position.y(), available.bottom() - self.height())))
        self.move(position)

    def _populate(self) -> None:
        self._sources = self._load_sources()
        recent_index = next(
            (
                index
                for index, source in enumerate(self._sources)
                if self._recent and source_matches(source.reference, self._recent)
            ),
            None,
        )
        if recent_index is not None:
            self._sources.insert(0, self._sources.pop(recent_index))
        self.list.clear()
        for index, source in enumerate(self._sources):
            row = SourceRow(source, recent_index is not None and index == 0)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setData(Qt.ItemDataRole.UserRole + 1, row.search_text)
            item.setSizeHint(QSize(0, 50))
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        self._filter(self.search.text())

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        first_visible: QListWidgetItem | None = None
        for row in range(self.list.count()):
            item = self.list.item(row)
            hidden = bool(needle) and needle not in str(
                item.data(Qt.ItemDataRole.UserRole + 1)
            )
            item.setHidden(hidden)
            if not hidden and first_visible is None:
                first_visible = item
        current = self.list.currentItem()
        if current is None or current.isHidden():
            self.list.setCurrentItem(first_visible)
        self.empty_label.setVisible(first_visible is None)
        self.capture_button.setEnabled(first_visible is not None)

    def _accept_current(self) -> None:
        item = self.list.currentItem()
        if item is None or item.isHidden():
            return
        self.selected = self._sources[int(item.data(Qt.ItemDataRole.UserRole))]
        self.accept()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched is self.search
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)
        ):
            QApplication.sendEvent(self.list, event)
            return True
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        self.search.setFocus()
