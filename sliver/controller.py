"""Application controller tying windows, configuration and overlays together."""

from __future__ import annotations

import os
import uuid
from dataclasses import replace

import win32gui
from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QMenu, QSystemTrayIcon, QWidget

from .capture import SelectionOverlay
from .config import ConfigStore, get_config_path
from .models import AppConfig, MATCH_APP, MATCH_TITLE, Region
from .overlay_window import DwmOverlayWidget
from .resources import app_icon
from .settings import SettingsStore, get_settings_path, resolve_config_path
from .ui.control_window import ControlWindow
from .ui.dialogs import ConfirmDialog, SettingsDialog
from .ui.source_picker import SourcePickerDialog
from .windows import (
    find_source_window,
    list_monitors,
    list_source_windows,
    match_source,
    monitor_index_for,
    snapshot_windows,
    window_source,
)


class OverlayApplication(QObject):
    """Coordinates Qt windows, persistent configuration, and DWM thumbnails."""

    def __init__(self, qt_app: QApplication) -> None:
        super().__init__()
        self.qt_app = qt_app
        self.settings_store = SettingsStore(get_settings_path())
        self.settings = self.settings_store.load()
        self._startup_notice: str | None = None
        config_path = resolve_config_path(self.settings)
        if self.settings.config_dir and not os.path.isdir(self.settings.config_dir):
            self._startup_notice = (
                f"The config folder {self.settings.config_dir} is not available, "
                "so the default location is used for now."
            )
            config_path = get_config_path()
        self.store = ConfigStore(config_path)
        self.config = self.store.load()
        self.overlays: dict[str, DwmOverlayWidget] = {}
        self.source_hwnds: dict[str, int | None] = {}
        self.selection_overlay: SelectionOverlay | None = None
        self.edit_mode = False
        self.preview_enabled = self.config.previews_enabled
        self.quitting = False
        self._shutting_down = False
        self._deleted: tuple[int, Region] | None = None
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(self.save)
        self.control = ControlWindow(self)
        self.tray = self._create_tray()
        self.reconcile_timer = QTimer(self)
        self.reconcile_timer.setInterval(1500)
        self.reconcile_timer.timeout.connect(self.reconcile_overlays)

    def run(self) -> None:
        self.reconcile_overlays()
        self.control.populate_regions(self.config.regions, None)
        self.control.set_previews_enabled(self.preview_enabled)
        self.control.set_edit_mode(self.edit_mode)
        self.control.show()
        if self.store.error or self._startup_notice:
            self.control.set_status(self.store.error or self._startup_notice)
        self.reconcile_timer.start()

    def _create_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray = QSystemTrayIcon(app_icon(), self)
        tray.setToolTip("Sliver")
        self.tray_menu = QMenu()
        self.tray_menu.addAction("Open Sliver", self.show_control)
        self.tray_menu.addAction("New region…", self._new_region_from_tray)
        self.tray_menu.addSeparator()
        self.tray_previews_action = self.tray_menu.addAction("Previews")
        self.tray_previews_action.setCheckable(True)
        self.tray_previews_action.setChecked(self.preview_enabled)
        self.tray_previews_action.triggered.connect(self.set_previews_enabled)
        self.tray_edit_action = self.tray_menu.addAction("Edit layout")
        self.tray_edit_action.setCheckable(True)
        self.tray_edit_action.triggered.connect(self.set_edit_mode)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction("Settings…", self._settings_from_tray)
        self.tray_menu.addAction("Quit", self.quit)
        tray.setContextMenu(self.tray_menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        return tray

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_control()

    def _new_region_from_tray(self) -> None:
        self.show_control()
        self.start_new_region(self.control.new_button)

    def open_config_folder(self) -> None:
        folder = os.path.dirname(self.store.path)
        try:
            os.startfile(folder)
        except OSError as error:
            self.control.set_status(f"Could not open {folder}: {error}")

    def _settings_from_tray(self) -> None:
        self.show_control()
        self.open_settings()

    def open_settings(self) -> None:
        SettingsDialog(self.control, self).exec()

    def _save_settings(self) -> None:
        try:
            self.settings_store.save(self.settings)
        except OSError as error:
            self.control.set_status(f"Could not save settings.json: {error}")

    def set_confirm_delete(self, enabled: bool) -> None:
        self.settings.confirm_delete = enabled
        self._save_settings()

    def set_close_to_tray(self, enabled: bool) -> None:
        self.settings.close_to_tray = enabled
        self._save_settings()

    def change_config_location(self, folder: str, parent: QWidget | None = None) -> bool:
        """Store config.json in another folder; the previous file is left in place."""

        folder = os.path.normpath(folder)
        target = os.path.join(folder, "config.json")
        if os.path.normcase(target) == os.path.normcase(self.store.path):
            return False
        load_existing = False
        if os.path.exists(target):
            choice = ConfirmDialog.ask(
                parent or self.control,
                "That folder already has a config.json",
                f"{target}\n\nLoad the regions saved in that file, or replace it "
                "with your current regions?",
                [
                    ("cancel", "Cancel", None),
                    ("replace", "Replace it", "dangerButton"),
                    ("load", "Load that file", "primaryButton"),
                ],
            )
            if choice not in ("replace", "load"):
                return False
            load_existing = choice == "load"
        if self.save_timer.isActive():
            self.save()
        store = ConfigStore(target)
        if load_existing:
            config = store.load()
            if store.error:
                self.control.set_status(f"{store.error}. The location was not changed.")
                return False
        else:
            try:
                store.save(self.config)
            except OSError as error:
                self.control.set_status(
                    f"Could not write to {folder}: {error}. The location was not changed."
                )
                return False
        self.store = store
        is_default = os.path.normcase(target) == os.path.normcase(get_config_path())
        self.settings.config_dir = None if is_default else folder
        self._save_settings()
        if load_existing:
            self._apply_config(config)
        self.control.set_status(
            f"config.json is now stored in {folder}. The previous file was left in place."
        )
        return True

    def reset_config_location(self, parent: QWidget | None = None) -> bool:
        return self.change_config_location(os.path.dirname(get_config_path()), parent)

    def _apply_config(self, config: AppConfig) -> None:
        """Replace the loaded regions, rebuilding overlays and the region list."""

        for overlay in list(self.overlays.values()):
            overlay.close_thumbnail()
        self.overlays.clear()
        self.config = config
        self._deleted = None
        self.preview_enabled = config.previews_enabled
        self.reconcile_overlays()
        self.control.populate_regions(self.config.regions, None)
        self.control.set_previews_enabled(self.preview_enabled)
        if self.tray is not None:
            self.tray_previews_action.setChecked(self.preview_enabled)

    def show_control(self) -> None:
        self.control.showNormal()
        self.control.raise_()
        self.control.activateWindow()

    def quit(self) -> None:
        self.quitting = True
        self.shutdown()

    def save(self) -> None:
        self.save_timer.stop()
        try:
            self.store.save(self.config)
        except OSError as error:
            self.control.set_status(f"Could not save config.json: {error}")

    def save_soon(self) -> None:
        self.save_timer.start()

    def find_region(self, region_id: str | None) -> Region | None:
        return next(
            (region for region in self.config.regions if region.id == region_id), None
        )

    def selected_region(self) -> Region | None:
        return self.find_region(self.control.selected_region_id())

    def source_hwnd_for(self, region: Region) -> int | None:
        hwnd = self.source_hwnds.get(region.id)
        return hwnd if hwnd and win32gui.IsWindow(hwnd) else None

    def start_new_region(self, anchor: QWidget | None = None) -> None:
        dialog = SourcePickerDialog(
            self.control, list_source_windows, self.config.selected_source
        )
        dialog.place_near(anchor if anchor and anchor.isVisible() else None)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected is None:
            return
        self.config.selected_source = dialog.selected.reference
        self.save()
        self.capture_region(dialog.selected.hwnd)

    def capture_region(self, source_hwnd: int, region_id: str | None = None) -> None:
        if not win32gui.IsWindow(source_hwnd):
            self.control.set_status("That window is no longer open.")
            return
        if win32gui.IsIconic(source_hwnd):
            self.control.set_status(
                "That window is minimized. Restore it, then try again."
            )
            return
        if self.selection_overlay:
            self.selection_overlay.cancel()
        try:
            win32gui.SetForegroundWindow(source_hwnd)
        except win32gui.error:
            pass
        overlay = SelectionOverlay(source_hwnd)
        self.selection_overlay = overlay
        overlay.selected.connect(
            lambda rectangle: self.region_captured(source_hwnd, rectangle, region_id)
        )
        overlay.cancelled.connect(self.capture_cancelled)
        overlay.magnifier_unavailable.connect(self.control.set_status)
        overlay.show_for_source()

    def capture_cancelled(self) -> None:
        self.selection_overlay = None
        self.control.set_status("Selection cancelled.")

    def region_captured(
        self,
        source_hwnd: int,
        rectangle: tuple[int, int, int, int],
        region_id: str | None = None,
    ) -> None:
        self.selection_overlay = None
        if not win32gui.IsWindow(source_hwnd):
            self.control.set_status(
                "The source window closed before the region was saved."
            )
            return
        left, top, right, bottom = rectangle
        width, height = right - left, bottom - top
        region = self.find_region(region_id)
        if region is not None:
            region.source = replace(
                window_source(source_hwnd), match_mode=region.source.match_mode
            )
            region.x, region.y, region.width, region.height = left, top, width, height
            region.overlay_width = max(1, round(width * region.scale / 100))
            region.overlay_height = max(1, round(height * region.scale / 100))
            overlay = self.overlays.pop(region.id, None)
            if overlay:
                overlay.close_thumbnail()
            self.save()
            self.reconcile_overlays()
            self.control.refresh_region(region.id)
            self.control.set_status("Area updated.")
            return

        offset = len(self.config.regions) * 30
        region = Region(
            id=str(uuid.uuid4()),
            source=replace(window_source(source_hwnd), match_mode=MATCH_APP),
            x=left,
            y=top,
            width=width,
            height=height,
            name=f"Region {len(self.config.regions) + 1}",
            scale=100,
            overlay_x=100 + offset,
            overlay_y=100 + offset,
            overlay_width=width,
            overlay_height=height,
        )
        self.config.regions.append(region)
        self.save()
        self.reconcile_overlays()
        self.control.populate_regions(self.config.regions, region.id)
        self.show_control()
        if self.preview_enabled:
            self.control.set_status(
                "Region captured. Give it a name, or turn on Edit layout to place it.",
                "Edit layout",
                lambda: self.set_edit_mode(True),
            )
        else:
            self.control.set_status(
                "Region captured. Previews are off, so it's hidden for now.",
                "Turn on",
                lambda: self.set_previews_enabled(True),
            )

    def set_region_visible(self, region_id: str, visible: bool) -> None:
        region = self.find_region(region_id)
        if region is None or region.enabled == visible:
            return
        region.enabled = visible
        self.save()
        self.reconcile_overlays()
        self.control.refresh_region(region_id)

    def rename_region(self, region_id: str, name: str) -> str | None:
        region = self.find_region(region_id)
        if region is None:
            return None
        name = name.strip()
        if not name or name == region.name:
            return region.name
        region.name = name
        self.save()
        self.control.refresh_region(region_id)
        return name

    def set_region_opacity(self, region_id: str, opacity: int) -> None:
        region = self.find_region(region_id)
        if region is None or region.opacity == opacity:
            return
        region.opacity = opacity
        overlay = self.overlays.get(region.id)
        if overlay:
            overlay.update_thumbnail()
        self.save_soon()

    def set_region_scale(self, region_id: str, scale: int) -> None:
        region = self.find_region(region_id)
        if region is None or region.scale == scale:
            return
        region.scale = scale
        region.overlay_width = max(1, round(region.width * scale / 100))
        region.overlay_height = max(1, round(region.height * scale / 100))
        overlay = self.overlays.get(region.id)
        if overlay:
            overlay.sync_size_to_capture()
        self.save_soon()
        self.control.refresh_overlay_geometry(region)

    def set_region_overlay_geometry(
        self, region_id: str, x: int, y: int, width: int, height: int
    ) -> None:
        region = self.find_region(region_id)
        if region is None:
            return
        geometry = (x, y, max(1, width), max(1, height))
        if geometry == (
            region.overlay_x,
            region.overlay_y,
            region.overlay_width,
            region.overlay_height,
        ):
            return
        (
            region.overlay_x,
            region.overlay_y,
            region.overlay_width,
            region.overlay_height,
        ) = geometry
        self._sync_scale_to_overlay(region)
        overlay = self.overlays.get(region.id)
        if overlay:
            overlay.sync_size_to_capture()
        self.save_soon()
        self.control.refresh_overlay_geometry(region)

    def move_region_to_monitor(
        self, region_id: str, rect: tuple[int, int, int, int]
    ) -> None:
        region = self.find_region(region_id)
        if region is None:
            return
        monitors = list_monitors()
        current = monitor_index_for(region, monitors)
        offset_x = offset_y = 40
        if current is not None:
            offset_x = region.overlay_x - monitors[current].rect[0]
            offset_y = region.overlay_y - monitors[current].rect[1]
        left, top, right, bottom = rect
        x = left + max(0, min(offset_x, right - left - region.overlay_width))
        y = top + max(0, min(offset_y, bottom - top - region.overlay_height))
        self.set_region_overlay_geometry(
            region_id, x, y, region.overlay_width, region.overlay_height
        )

    def overlay_geometry_changed(self, region: Region) -> None:
        """Called when an overlay is dragged or resized in Edit layout."""

        self._sync_scale_to_overlay(region)
        self.control.refresh_overlay_geometry(region)

    @staticmethod
    def _sync_scale_to_overlay(region: Region) -> None:
        scale = round(region.overlay_width * 100 / max(1, region.width))
        region.scale = max(25, min(400, scale))

    def set_region_crop(
        self, region_id: str, x: int, y: int, width: int, height: int
    ) -> None:
        region = self.find_region(region_id)
        if region is None or (region.x, region.y, region.width, region.height) == (
            x,
            y,
            width,
            height,
        ):
            return
        size_changed = (region.width, region.height) != (width, height)
        region.x, region.y, region.width, region.height = x, y, width, height
        if size_changed:
            region.overlay_width = max(1, round(width * region.scale / 100))
            region.overlay_height = max(1, round(height * region.scale / 100))
        overlay = self.overlays.get(region.id)
        if overlay:
            if size_changed:
                overlay.sync_size_to_capture()
            else:
                overlay.update_thumbnail()
        self.save()
        self.control.refresh_region(region_id)

    def set_region_match_mode(self, region_id: str, mode: str) -> None:
        region = self.find_region(region_id)
        if region is None or mode not in (MATCH_TITLE, MATCH_APP):
            return
        if region.source.match_mode != mode:
            region.source.match_mode = mode
            self.save()
            self.reconcile_overlays()
        self.control.refresh_region(region_id)

    def rebind_region(self, region_id: str, anchor: QWidget | None = None) -> None:
        """Attach a region to another window, keeping its area, size and mode."""

        region = self.find_region(region_id)
        if region is None:
            return
        dialog = SourcePickerDialog(
            self.control,
            list_source_windows,
            region.source,
            title="Choose a window to connect this region to",
            action_text="Connect",
        )
        dialog.place_near(anchor if anchor and anchor.isVisible() else None)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected is None:
            return
        region.source = replace(
            dialog.selected.reference, match_mode=region.source.match_mode
        )
        overlay = self.overlays.pop(region.id, None)
        if overlay:
            overlay.close_thumbnail()
        self.save()
        self.reconcile_overlays()
        self.control.refresh_region(region_id)
        self.control.set_status(f'Connected to "{region.source.title}".')

    def recapture_region(self, region_id: str) -> None:
        region = self.find_region(region_id)
        if region is None:
            return
        source_hwnd = find_source_window(region.source)
        if not source_hwnd:
            self.control.set_status(
                "The source window for this region isn't running. Open it and try again."
            )
            return
        self.capture_region(source_hwnd, region_id)

    def duplicate_region(self, region_id: str) -> None:
        region = self.find_region(region_id)
        if region is None:
            return
        copy = replace(
            region,
            id=str(uuid.uuid4()),
            source=replace(region.source),
            name=f"{region.name} copy",
            overlay_x=region.overlay_x + 30,
            overlay_y=region.overlay_y + 30,
        )
        self.config.regions.insert(self.config.regions.index(region) + 1, copy)
        self.save()
        self.reconcile_overlays()
        self.control.populate_regions(self.config.regions, copy.id)
        self.control.set_status(f'Duplicated "{region.name}".')

    def request_delete_region(self, region_id: str) -> None:
        """Delete a region, asking first unless the user turned that off."""

        region = self.find_region(region_id)
        if region is None:
            return
        if self.settings.confirm_delete:
            choice = ConfirmDialog.ask(
                self.control,
                f'Delete "{region.name}"?',
                "The overlay will be removed. You can undo this right after deleting.",
                [("cancel", "Cancel", None), ("delete", "Delete", "dangerButton")],
            )
            if choice != "delete":
                return
        self.delete_region(region_id)

    def delete_region(self, region_id: str) -> None:
        region = self.find_region(region_id)
        if region is None:
            return
        overlay = self.overlays.pop(region.id, None)
        if overlay:
            overlay.close_thumbnail()
        index = self.config.regions.index(region)
        self.config.regions.remove(region)
        self._deleted = (index, region)
        self.save()
        neighbour = (
            self.config.regions[min(index, len(self.config.regions) - 1)]
            if self.config.regions
            else None
        )
        self.control.populate_regions(
            self.config.regions, neighbour.id if neighbour else None
        )
        self.control.set_status(f'Deleted "{region.name}".', "Undo", self.undo_delete)

    def undo_delete(self) -> None:
        if self._deleted is None:
            return
        index, region = self._deleted
        self._deleted = None
        self.config.regions.insert(min(index, len(self.config.regions)), region)
        self.save()
        self.reconcile_overlays()
        self.control.populate_regions(self.config.regions, region.id)
        self.control.set_status(f'Restored "{region.name}".')

    def set_edit_mode(self, enabled: bool) -> None:
        self.edit_mode = enabled
        for overlay in self.overlays.values():
            overlay.set_edit_mode(enabled)
        self.control.set_edit_mode(enabled)
        if self.tray is not None:
            self.tray_edit_action.setChecked(enabled)
        if enabled and not self.preview_enabled:
            self.set_previews_enabled(True)

    def set_previews_enabled(self, enabled: bool) -> None:
        self.preview_enabled = enabled
        if self.config.previews_enabled != enabled:
            self.config.previews_enabled = enabled
            self.save()
        self.reconcile_overlays()
        self.control.set_previews_enabled(enabled)
        if self.tray is not None:
            self.tray_previews_action.setChecked(enabled)

    def reconcile_overlays(self) -> None:
        if self._shutting_down:
            return
        snapshot = snapshot_windows()
        self.source_hwnds = {
            region.id: match_source(region.source, snapshot)
            for region in self.config.regions
        }
        # Regions saved by older versions learn their program name once found.
        for region in self.config.regions:
            window = snapshot.window(self.source_hwnds[region.id])
            if window and not region.source.exe_name:
                region.source.exe_name = snapshot.exe_name(window.process_id)
                if region.source.exe_name:
                    self.save_soon()
        for region_id, overlay in list(self.overlays.items()):
            region = self.find_region(region_id)
            source_hwnd = self.source_hwnds.get(region_id)
            if (
                region is None
                or not self.preview_enabled
                or not region.enabled
                or not source_hwnd
                or win32gui.IsIconic(source_hwnd)
                or source_hwnd != overlay.source_hwnd
            ):
                self.overlays.pop(region_id, None)
                overlay.close_thumbnail()
                continue
            overlay.region = region
            overlay.set_edit_mode(self.edit_mode)
            try:
                overlay.update_thumbnail()
            except RuntimeError:
                self.overlays.pop(region_id, None)
                overlay.close_thumbnail()

        for region in self.config.regions:
            if (
                not self.preview_enabled
                or not region.enabled
                or region.id in self.overlays
            ):
                continue
            source_hwnd = self.source_hwnds.get(region.id)
            if not source_hwnd or win32gui.IsIconic(source_hwnd):
                continue
            overlay = DwmOverlayWidget(self, region, source_hwnd)
            try:
                overlay.create_thumbnail()
                self.overlays[region.id] = overlay
            except RuntimeError as error:
                overlay.close_thumbnail()
                self.control.set_status(f"Could not create overlay: {error}")
        self.control.refresh_region_status()

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self.quitting = True
        self.reconcile_timer.stop()
        if self.save_timer.isActive():
            self.save()
        if self.selection_overlay:
            self.selection_overlay.cancel()
            self.selection_overlay = None
        for overlay in list(self.overlays.values()):
            overlay.close_thumbnail()
        self.overlays.clear()
        if self.tray is not None:
            self.tray.hide()
        self.qt_app.quit()
