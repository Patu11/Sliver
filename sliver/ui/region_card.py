"""Sidebar card for one region."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..models import Region
from ..theme import THEME
from .widgets import ElidedLabel, ToggleSwitch


class RegionCard(QWidget):
    """One region row in the sidebar list."""

    visibility_toggled = pyqtSignal(str, bool)

    def __init__(self, region_id: str) -> None:
        super().__init__()
        self.region_id = region_id
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        layout.addWidget(self.status_dot)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.title = ElidedLabel()
        self.title.setObjectName("cardTitle")
        self.subtitle = ElidedLabel()
        self.subtitle.setObjectName("cardSubtitle")
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        layout.addLayout(text, 1)
        self.switch = ToggleSwitch()
        self.switch.setToolTip("Show this overlay")
        self.switch.toggled.connect(
            lambda checked: self.visibility_toggled.emit(self.region_id, checked)
        )
        layout.addWidget(self.switch)

    def update_region(self, region: Region, available: bool) -> None:
        self.title.set_full_text(region.name)
        source = region.source.title or region.source.class_name
        self.subtitle.set_full_text(f"{region.width}×{region.height} · {source}")
        color = THEME["success"] if available else THEME["subtle"]
        self.status_dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        self.status_dot.setToolTip(
            "Source window is running" if available else "Source window not found"
        )
        self.switch.set_checked_silently(region.enabled)
