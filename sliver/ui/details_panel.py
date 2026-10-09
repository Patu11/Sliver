"""Editable properties of the selected region."""

from __future__ import annotations

from typing import TYPE_CHECKING

import win32gui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..models import MATCH_APP, MATCH_TITLE, Region
from ..windows import list_monitors, monitor_index_for
from .live_preview import LivePreview
from .widgets import ClickableLabel, ElidedLabel, ToggleSwitch

if TYPE_CHECKING:
    from ..controller import OverlayApplication


class RegionDetailsPanel(QWidget):
    """Editable properties of the selected region."""

    def __init__(self, controller: "OverlayApplication") -> None:
        super().__init__()
        self.controller = controller
        self.region_id: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("nameEdit")
        self.name_edit.setToolTip("Click to rename (F2)")
        self.name_edit.editingFinished.connect(self._name_edited)
        layout.addWidget(self.name_edit)

        self.preview = LivePreview()
        layout.addWidget(self.preview, 1)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)

        source_label = self._field_label("Source")
        source_label.setContentsMargins(0, 7, 0, 0)
        grid.addWidget(source_label, 0, 0, Qt.AlignmentFlag.AlignTop)
        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        self.source_label = ElidedLabel()
        source_row.addWidget(self.source_label, 1)
        self.status_pill = QLabel()
        self.status_pill.setObjectName("statusPill")
        source_row.addWidget(self.status_pill)
        self.recapture_button = QPushButton("Reselect area")
        self.recapture_button.setToolTip("Drag a new area over the source window")
        self.recapture_button.clicked.connect(
            lambda: self.region_id and self.controller.recapture_region(self.region_id)
        )
        source_row.addWidget(self.recapture_button)
        match_row = QHBoxLayout()
        match_row.setSpacing(8)
        self.match_combo = QComboBox()
        self.match_combo.addItem("Follow this exact window title", MATCH_TITLE)
        self.match_combo.addItem("Follow any window of this app", MATCH_APP)
        self.match_combo.setToolTip(
            "Exact title: the region waits for a window with the same title.\n"
            "Any window of this app: if that title is gone, another window of the "
            "same program is shown instead."
        )
        self.match_combo.activated.connect(self._match_mode_chosen)
        match_row.addWidget(self.match_combo, 1)
        self.connect_button = QPushButton("Connect to window…")
        self.connect_button.setToolTip(
            "Attach this region to another window, keeping its area and size"
        )
        self.connect_button.clicked.connect(
            lambda: self.region_id
            and self.controller.rebind_region(self.region_id, self.connect_button)
        )
        match_row.addWidget(self.connect_button)
        source_cell = QVBoxLayout()
        source_cell.setSpacing(8)
        source_cell.addLayout(source_row)
        source_cell.addLayout(match_row)
        grid.addLayout(source_cell, 0, 1)

        grid.addWidget(self._field_label("Opacity"), 1, 0)
        opacity_row = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.valueChanged.connect(self._opacity_changed)
        opacity_row.addWidget(self.opacity_slider, 1)
        self.opacity_value = QLabel()
        self.opacity_value.setFixedWidth(44)
        self.opacity_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacity_row.addWidget(self.opacity_value)
        grid.addLayout(opacity_row, 1, 1)

        grid.addWidget(self._field_label("Size"), 2, 0)
        scale_row = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(25, 400)
        self.scale_slider.setPageStep(25)
        self.scale_slider.valueChanged.connect(self._scale_changed)
        scale_row.addWidget(self.scale_slider, 1)
        self.scale_value = QLabel()
        self.scale_value.setFixedWidth(44)
        self.scale_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        scale_row.addWidget(self.scale_value)
        scale_row.addSpacing(6)
        for preset in (50, 100, 200):
            chip = QPushButton(f"{preset}%")
            chip.setObjectName("chipButton")
            chip.clicked.connect(lambda _=False, value=preset: self.scale_slider.setValue(value))
            scale_row.addWidget(chip)
        grid.addLayout(scale_row, 2, 1)

        area_label = self._field_label("Area")
        area_label.setToolTip("Source area in pixels, relative to the window's client area")
        grid.addWidget(area_label, 3, 0)
        area_layout = QHBoxLayout()
        area_layout.setSpacing(8)
        self.crop_spins: list[QSpinBox] = []
        for label, minimum in (("X", 0), ("Y", 0), ("Width", 1), ("Height", 1)):
            area_layout.addWidget(self._field_label(label))
            spin = QSpinBox()
            spin.setRange(minimum, 100000)
            spin.setKeyboardTracking(False)
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            spin.setMinimumWidth(64)
            spin.valueChanged.connect(self._crop_changed)
            area_layout.addWidget(spin, 1)
            self.crop_spins.append(spin)
        grid.addLayout(area_layout, 3, 1)

        overlay_label = self._field_label("Overlay")
        overlay_label.setToolTip("Position and size of the overlay in screen pixels")
        grid.addWidget(overlay_label, 4, 0)
        overlay_layout = QHBoxLayout()
        overlay_layout.setSpacing(8)
        self.overlay_spins: list[QSpinBox] = []
        for index, (label, minimum) in enumerate(
            (("X", -100000), ("Y", -100000), ("Width", 1), ("Height", 1))
        ):
            overlay_layout.addWidget(self._field_label(label))
            spin = QSpinBox()
            spin.setRange(minimum, 100000)
            spin.setKeyboardTracking(False)
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            spin.setMinimumWidth(64)
            spin.valueChanged.connect(
                lambda _=0, changed=index: self._overlay_changed(changed)
            )
            overlay_layout.addWidget(spin, 1)
            self.overlay_spins.append(spin)
        grid.addLayout(overlay_layout, 4, 1)

        grid.addWidget(self._field_label("Monitor"), 5, 0)
        monitor_layout = QHBoxLayout()
        monitor_layout.setSpacing(8)
        self.monitor_combo = QComboBox()
        self.monitor_combo.setToolTip("Move the overlay to another monitor")
        self.monitor_combo.activated.connect(self._monitor_chosen)
        monitor_layout.addWidget(self.monitor_combo, 1)
        monitor_layout.addSpacing(10)
        self.proportions_switch = ToggleSwitch()
        self.proportions_switch.set_checked_silently(True)
        proportions_tooltip = (
            "Changing the overlay width or height keeps the shape of the source area"
        )
        self.proportions_switch.setToolTip(proportions_tooltip)
        proportions_label = ClickableLabel("Keep proportions")
        proportions_label.setObjectName("fieldLabel")
        proportions_label.setToolTip(proportions_tooltip)
        proportions_label.clicked.connect(self.proportions_switch.toggle)
        monitor_layout.addWidget(proportions_label)
        monitor_layout.addWidget(self.proportions_switch)
        grid.addLayout(monitor_layout, 5, 1)
        layout.addLayout(grid)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.clicked.connect(
            lambda: self.region_id and self.controller.duplicate_region(self.region_id)
        )
        footer.addWidget(self.duplicate_button)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.setToolTip("Delete this region (Del)")
        self.delete_button.clicked.connect(
            lambda: self.region_id
            and self.controller.request_delete_region(self.region_id)
        )
        footer.addWidget(self.delete_button)
        layout.addLayout(footer)

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def set_region(self, region: Region | None, source_hwnd: int | None) -> None:
        self.region_id = region.id if region else None
        if region is None:
            self.preview.set_target(None, None)
            return
        widgets = [self.name_edit, self.opacity_slider, self.scale_slider, *self.crop_spins]
        for widget in widgets:
            widget.blockSignals(True)
        self.name_edit.setText(region.name)
        self.opacity_slider.setValue(region.opacity)
        self.scale_slider.setValue(round(region.scale))
        for spin, value in zip(
            self.crop_spins, (region.x, region.y, region.width, region.height)
        ):
            spin.setValue(value)
        for widget in widgets:
            widget.blockSignals(False)
        self.opacity_value.setText(f"{region.opacity}%")
        self.refresh_geometry(region, force=True)
        self.match_combo.setCurrentIndex(
            max(0, self.match_combo.findData(region.source.match_mode))
        )
        self.refresh_status(region, source_hwnd)

    def refresh_status(self, region: Region, source_hwnd: int | None) -> None:
        available = source_hwnd is not None
        title = win32gui.GetWindowText(source_hwnd) if available else ""
        title = title or region.source.title or region.source.class_name
        program = region.source.exe_name
        self.source_label.set_full_text(f"{program} — {title}" if program else title)
        # Following the app needs the program name, known once the window was seen.
        self.match_combo.model().item(1).setEnabled(bool(program))
        self.status_pill.setText("Running" if available else "Not running")
        self.status_pill.setProperty("state", "ok" if available else "off")
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)
        self.recapture_button.setEnabled(available)
        self.preview.set_target(region, source_hwnd)

    def refresh_geometry(self, region: Region, force: bool = False) -> None:
        """Mirror the overlay's on-screen geometry without disturbing typing."""

        values = (
            region.overlay_x,
            region.overlay_y,
            region.overlay_width,
            region.overlay_height,
        )
        for spin, value in zip(self.overlay_spins, values):
            if not force and spin.hasFocus() and spin.lineEdit().isModified():
                continue
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        self.scale_slider.blockSignals(True)
        self.scale_slider.setValue(round(region.scale))
        self.scale_slider.blockSignals(False)
        self.scale_value.setText(f"{round(region.scale)}%")

        if self.monitor_combo.view().isVisible():
            return
        monitors = list_monitors()
        current = monitor_index_for(region, monitors)
        self.monitor_combo.blockSignals(True)
        self.monitor_combo.clear()
        if current is None:
            self.monitor_combo.addItem("Off screen — choose a monitor", None)
        for monitor in monitors:
            self.monitor_combo.addItem(monitor.label, monitor.rect)
        self.monitor_combo.setCurrentIndex(0 if current is None else current)
        self.monitor_combo.blockSignals(False)

    def focus_name(self) -> None:
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _name_edited(self) -> None:
        if self.region_id is None:
            return
        name = self.controller.rename_region(self.region_id, self.name_edit.text())
        if name is not None and name != self.name_edit.text():
            self.name_edit.setText(name)

    def _opacity_changed(self, value: int) -> None:
        self.opacity_value.setText(f"{value}%")
        if self.region_id:
            self.controller.set_region_opacity(self.region_id, value)

    def _scale_changed(self, value: int) -> None:
        self.scale_value.setText(f"{value}%")
        if self.region_id:
            self.controller.set_region_scale(self.region_id, value)

    def _match_mode_chosen(self, index: int) -> None:
        if self.region_id:
            self.controller.set_region_match_mode(
                self.region_id, self.match_combo.itemData(index)
            )

    def _crop_changed(self, *_: object) -> None:
        if self.region_id:
            x, y, width, height = (spin.value() for spin in self.crop_spins)
            self.controller.set_region_crop(self.region_id, x, y, width, height)

    def _overlay_changed(self, changed: int) -> None:
        region = self.controller.find_region(self.region_id)
        if region is None:
            return
        x, y, width, height = (spin.value() for spin in self.overlay_spins)
        if self.proportions_switch.isChecked():
            if changed == 2:
                height = max(1, round(width * region.height / max(1, region.width)))
            elif changed == 3:
                width = max(1, round(height * region.width / max(1, region.height)))
        self.controller.set_region_overlay_geometry(region.id, x, y, width, height)
        self.refresh_geometry(region, force=True)

    def _monitor_chosen(self, index: int) -> None:
        rect = self.monitor_combo.itemData(index)
        if self.region_id and rect is not None:
            self.controller.move_region_to_monitor(self.region_id, tuple(rect))
