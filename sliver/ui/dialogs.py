"""Confirmation and settings dialogs."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import get_config_path
from ..theme import THEME
from ..win32_api import apply_window_theme
from .widgets import ClickableLabel, ElidedLabel, ToggleSwitch

if TYPE_CHECKING:
    from ..controller import OverlayApplication


class ConfirmDialog(QDialog):
    """A small modal question with one button per possible answer."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        buttons: list[tuple[str, str, str | None]],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sliver")
        self.setModal(True)
        self.setMinimumWidth(420)
        apply_window_theme(int(self.winId()), THEME["sidebar"])
        self.choice: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        message_label = QLabel(message)
        message_label.setObjectName("muted")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        layout.addSpacing(10)

        row = QHBoxLayout()
        row.addStretch(1)
        # The first button is the safe answer: it has focus and Enter picks it.
        for index, (key, text, object_name) in enumerate(buttons):
            button = QPushButton(text)
            if object_name:
                button.setObjectName(object_name)
            button.setAutoDefault(index == 0)
            button.setDefault(index == 0)
            button.clicked.connect(lambda _=False, chosen=key: self._choose(chosen))
            row.addWidget(button)
            if index == 0:
                button.setFocus()
        layout.addLayout(row)

    def _choose(self, key: str) -> None:
        self.choice = key
        self.accept()

    @staticmethod
    def ask(
        parent: QWidget | None,
        title: str,
        message: str,
        buttons: list[tuple[str, str, str | None]],
    ) -> str | None:
        """Show the question and return the chosen key, or None when dismissed."""

        dialog = ConfirmDialog(parent, title, message, buttons)
        dialog.exec()
        return dialog.choice


class SettingsDialog(QDialog):
    """Application settings: config file location and behavior."""

    def __init__(self, parent: QWidget | None, controller: "OverlayApplication") -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Sliver")
        self.setModal(True)
        self.setMinimumWidth(520)
        apply_window_theme(int(self.winId()), THEME["sidebar"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(10)
        title = QLabel("Settings")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        layout.addSpacing(6)

        layout.addWidget(self._section("Config file"))
        hint = QLabel("Your regions and their layout are saved in config.json.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_label = ElidedLabel()
        path_row.addWidget(self.path_label, 1)
        self.default_pill = QLabel("Default")
        self.default_pill.setObjectName("statusPill")
        self.default_pill.setProperty("state", "off")
        path_row.addWidget(self.default_pill)
        layout.addLayout(path_row)
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        change_button = QPushButton("Change…")
        change_button.setToolTip("Choose another folder for config.json")
        change_button.clicked.connect(self._change_location)
        button_row.addWidget(change_button)
        self.reset_button = QPushButton("Reset to default")
        self.reset_button.clicked.connect(self._reset_location)
        button_row.addWidget(self.reset_button)
        open_button = QPushButton("Open folder")
        open_button.clicked.connect(self.controller.open_config_folder)
        button_row.addWidget(open_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        layout.addSpacing(14)

        layout.addWidget(self._section("Behavior"))
        confirm_row = QHBoxLayout()
        confirm_label = ClickableLabel("Ask before deleting a region")
        confirm_row.addWidget(confirm_label, 1)
        self.confirm_switch = ToggleSwitch()
        self.confirm_switch.set_checked_silently(self.controller.settings.confirm_delete)
        self.confirm_switch.toggled.connect(self.controller.set_confirm_delete)
        confirm_label.clicked.connect(self.confirm_switch.toggle)
        confirm_row.addWidget(self.confirm_switch)
        layout.addLayout(confirm_row)
        tray_row = QHBoxLayout()
        tray_label = ClickableLabel("Keep running in the tray when the window is closed")
        tray_label.setToolTip(
            "On: the X button hides the window and overlays stay on screen.\n"
            "Off: the X button quits Sliver."
        )
        tray_row.addWidget(tray_label, 1)
        self.tray_switch = ToggleSwitch()
        self.tray_switch.setToolTip(tray_label.toolTip())
        self.tray_switch.set_checked_silently(self.controller.settings.close_to_tray)
        self.tray_switch.toggled.connect(self.controller.set_close_to_tray)
        tray_label.clicked.connect(self.tray_switch.toggle)
        tray_row.addWidget(self.tray_switch)
        layout.addLayout(tray_row)
        layout.addSpacing(16)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton("Close")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        layout.addLayout(footer)
        self.refresh()

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("cardTitle")
        return label

    def refresh(self) -> None:
        path = self.controller.store.path
        is_default = os.path.normcase(path) == os.path.normcase(get_config_path())
        self.path_label.set_full_text(path)
        self.default_pill.setVisible(is_default)
        self.reset_button.setEnabled(not is_default)

    def _change_location(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose a folder for config.json",
            os.path.dirname(self.controller.store.path),
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self.controller.change_config_location(folder, self)
            self.refresh()

    def _reset_location(self) -> None:
        self.controller.reset_config_location(self)
        self.refresh()

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        # Enter inside the dialog should not trigger a location button.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            return
        super().keyPressEvent(event)
