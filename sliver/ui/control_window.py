"""Main control window."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from PyQt6.QtCore import QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..models import Region
from ..resources import app_icon
from ..theme import THEME
from ..win32_api import apply_window_theme
from .details_panel import RegionDetailsPanel
from .region_card import RegionCard
from .widgets import ClickableLabel, Toast, ToggleSwitch

if TYPE_CHECKING:
    from ..controller import OverlayApplication


class ControlWindow(QMainWindow):
    """Main window: region list on the left, details of the selection on the right."""

    def __init__(self, controller: "OverlayApplication") -> None:
        super().__init__()
        self.controller = controller
        self._close_hint_shown = False
        self.setWindowTitle("Sliver")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(760, 620)
        self.resize(960, 740)
        apply_window_theme(int(self.winId()), THEME["sidebar"])

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 12, 20, 12)
        header_layout.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(24, 24))
        header_layout.addWidget(logo)
        title = QLabel("Sliver")
        title.setObjectName("appTitle")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self.previews_switch = self._header_switch(
            header_layout,
            "Previews",
            "Show or hide all overlays at once",
            self.controller.set_previews_enabled,
        )
        header_layout.addSpacing(18)
        self.edit_switch = self._header_switch(
            header_layout,
            "Edit layout",
            "Drag overlays to move them, drag an edge to resize (Ctrl+E)",
            self.controller.set_edit_mode,
        )
        outer.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        sidebar.setFixedWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(10)
        self.new_button = QPushButton("+  New region")
        self.new_button.setObjectName("primaryButton")
        self.new_button.setToolTip("Pick a window and select an area (Ctrl+N)")
        self.new_button.setMinimumHeight(36)
        self.new_button.clicked.connect(
            lambda: self.controller.start_new_region(self.new_button)
        )
        sidebar_layout.addWidget(self.new_button)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter regions")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)
        sidebar_layout.addWidget(self.filter_edit)
        self.region_list = QListWidget()
        self.region_list.setObjectName("regionList")
        self.region_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.region_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.region_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.region_list.customContextMenuRequested.connect(self._show_context_menu)
        self.region_list.currentItemChanged.connect(lambda *_: self._selection_changed())
        sidebar_layout.addWidget(self.region_list, 1)
        self.list_hint = QLabel("Your captured regions will appear here.")
        self.list_hint.setObjectName("muted")
        self.list_hint.setWordWrap(True)
        self.list_hint.setAlignment(Qt.AlignmentFlag.AlignTop)
        sidebar_layout.addWidget(self.list_hint)
        self.settings_button = QPushButton("Settings")
        self.settings_button.setToolTip("Config file location and app behavior")
        self.settings_button.clicked.connect(self.controller.open_settings)
        sidebar_layout.addWidget(self.settings_button)
        body.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(14, 6, 6, 6)
        self.banner_label = QLabel()
        self.banner_label.setWordWrap(True)
        banner_layout.addWidget(self.banner_label, 1)
        self.banner_button = QPushButton()
        self.banner_button.setObjectName("linkButton")
        self.banner_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.banner_button.clicked.connect(self._banner_action)
        banner_layout.addWidget(self.banner_button)
        banner_holder = QVBoxLayout()
        banner_holder.setContentsMargins(24, 14, 24, 0)
        banner_holder.addWidget(self.banner)
        content_layout.addLayout(banner_holder)
        self.stack = QStackedWidget()
        self.empty_page = self._build_empty_page()
        self.details = RegionDetailsPanel(controller)
        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.details)
        content_layout.addWidget(self.stack, 1)
        body.addWidget(content, 1)
        outer.addLayout(body, 1)

        self.toast = Toast(content)

        QShortcut(
            QKeySequence("Ctrl+N"),
            self,
            lambda: self.controller.start_new_region(self.new_button),
        )
        QShortcut(
            QKeySequence("Ctrl+E"),
            self,
            lambda: self.controller.set_edit_mode(not self.controller.edit_mode),
        )
        QShortcut(QKeySequence("Ctrl+Z"), self, self.controller.undo_delete)
        QShortcut(QKeySequence("F2"), self, self.details.focus_name)
        delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.region_list)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        delete_shortcut.activated.connect(self._delete_selected)

    def _header_switch(
        self,
        layout: QHBoxLayout,
        text: str,
        tooltip: str,
        handler: Callable[[bool], None],
    ) -> ToggleSwitch:
        switch = ToggleSwitch()
        switch.setToolTip(tooltip)
        switch.toggled.connect(handler)
        label = ClickableLabel(text)
        label.setToolTip(tooltip)
        label.clicked.connect(switch.toggle)
        layout.addWidget(label)
        layout.addWidget(switch)
        return switch

    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 32, 48, 48)
        layout.addStretch(1)
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(56, 56))
        layout.addWidget(icon)
        layout.addSpacing(8)
        title = QLabel("Capture your first region")
        title.setObjectName("emptyTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            "Keep any part of another app's window on top of everything else as a "
            "live, click-through mini view."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(16)
        steps = (
            "Choose the window you want to watch.",
            "Drag over the area you care about.",
            "Turn on Edit layout to move and resize the overlay.",
        )
        for number, text in enumerate(steps, start=1):
            row = QHBoxLayout()
            row.setSpacing(12)
            badge = QLabel(str(number))
            badge.setObjectName("stepNumber")
            badge.setFixedSize(24, 24)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(badge)
            row.addWidget(QLabel(text), 1)
            layout.addLayout(row)
            layout.addSpacing(6)
        layout.addSpacing(14)
        button = QPushButton("+  New region")
        button.setObjectName("primaryButton")
        button.setMinimumHeight(38)
        button.setFixedWidth(180)
        button.clicked.connect(lambda: self.controller.start_new_region(button))
        layout.addWidget(button)
        layout.addStretch(2)
        return page

    def set_status(
        self,
        message: str,
        action_text: str | None = None,
        action: Callable[[], None] | None = None,
    ) -> None:
        self.toast.show_message(message, action_text, action)

    def set_previews_enabled(self, enabled: bool) -> None:
        self.previews_switch.set_checked_silently(enabled)
        self.update_banner()

    def set_edit_mode(self, enabled: bool) -> None:
        self.edit_switch.set_checked_silently(enabled)
        self.update_banner()

    def update_banner(self) -> None:
        if self.controller.edit_mode:
            self.banner_label.setText(
                "Edit layout is on — drag an overlay to move it, or drag its edge to resize."
            )
            self.banner_button.setText("Done")
        elif not self.controller.preview_enabled and self.controller.config.regions:
            self.banner_label.setText("Previews are off, so your overlays are hidden.")
            self.banner_button.setText("Turn on")
        else:
            self.banner.hide()
            return
        self.banner.show()

    def _banner_action(self) -> None:
        if self.controller.edit_mode:
            self.controller.set_edit_mode(False)
        else:
            self.controller.set_previews_enabled(True)

    def populate_regions(self, regions: list[Region], selected_id: str | None) -> None:
        self.region_list.blockSignals(True)
        self.region_list.clear()
        selected_item: QListWidgetItem | None = None
        for region in regions:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, region.id)
            item.setSizeHint(QSize(0, 58))
            card = RegionCard(region.id)
            card.update_region(region, self.controller.source_hwnd_for(region) is not None)
            card.visibility_toggled.connect(self.controller.set_region_visible)
            self.region_list.addItem(item)
            self.region_list.setItemWidget(item, card)
            if region.id == selected_id:
                selected_item = item
        if selected_item is None and self.region_list.count():
            selected_item = self.region_list.item(0)
        self.region_list.setCurrentItem(selected_item)
        self.region_list.blockSignals(False)
        self.list_hint.setVisible(not regions)
        self.filter_edit.setVisible(len(regions) > 3)
        if not self.filter_edit.isVisibleTo(self):
            self.filter_edit.clear()
        self._apply_filter(self.filter_edit.text())
        self._selection_changed()
        self.update_banner()

    def _card(self, region_id: str) -> RegionCard | None:
        for row in range(self.region_list.count()):
            item = self.region_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == region_id:
                widget = self.region_list.itemWidget(item)
                return widget if isinstance(widget, RegionCard) else None
        return None

    def refresh_region(self, region_id: str) -> None:
        region = self.controller.find_region(region_id)
        card = self._card(region_id)
        if region is None:
            return
        source_hwnd = self.controller.source_hwnd_for(region)
        if card:
            card.update_region(region, source_hwnd is not None)
        if self.details.region_id == region_id:
            self.details.set_region(region, source_hwnd)

    def refresh_overlay_geometry(self, region: Region) -> None:
        if self.details.region_id == region.id:
            self.details.refresh_geometry(region)

    def refresh_region_status(self) -> None:
        for region in self.controller.config.regions:
            source_hwnd = self.controller.source_hwnd_for(region)
            card = self._card(region.id)
            if card:
                card.update_region(region, source_hwnd is not None)
            if self.details.region_id == region.id:
                self.details.refresh_status(region, source_hwnd)

    def selected_region_id(self) -> str | None:
        item = self.region_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _selection_changed(self) -> None:
        region = self.controller.find_region(self.selected_region_id())
        if region is None:
            self.details.set_region(None, None)
            self.stack.setCurrentWidget(self.empty_page)
            return
        self.stack.setCurrentWidget(self.details)
        self.details.set_region(region, self.controller.source_hwnd_for(region))

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for row in range(self.region_list.count()):
            item = self.region_list.item(row)
            region = self.controller.find_region(item.data(Qt.ItemDataRole.UserRole))
            haystack = f"{region.name} {region.source.title}".lower() if region else ""
            item.setHidden(bool(needle) and needle not in haystack)

    def _show_context_menu(self, position: QPoint) -> None:
        item = self.region_list.itemAt(position)
        if item is None:
            return
        self.region_list.setCurrentItem(item)
        region_id = str(item.data(Qt.ItemDataRole.UserRole))
        menu = QMenu(self)
        menu.addAction("Rename", self.details.focus_name)
        menu.addAction("Reselect area", lambda: self.controller.recapture_region(region_id))
        menu.addAction("Duplicate", lambda: self.controller.duplicate_region(region_id))
        menu.addSeparator()
        menu.addAction(
            "Delete", lambda: self.controller.request_delete_region(region_id)
        )
        menu.exec(self.region_list.viewport().mapToGlobal(position))

    def _delete_selected(self) -> None:
        region_id = self.selected_region_id()
        if region_id:
            self.controller.request_delete_region(region_id)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        QTimer.singleShot(0, self.details.preview.refresh)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        tray = self.controller.tray
        if (
            self.controller.settings.close_to_tray
            and tray is not None
            and tray.isVisible()
            and not self.controller.quitting
        ):
            event.ignore()
            self.hide()
            if not self._close_hint_shown:
                self._close_hint_shown = True
                tray.showMessage(
                    "Sliver is still running",
                    "Your overlays stay on screen. Use the tray icon to reopen or quit.",
                    app_icon(),
                    4000,
                )
            return
        self.controller.shutdown()
        event.accept()
