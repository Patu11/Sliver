"""Discovery of source windows and monitors."""

from __future__ import annotations

import os

import win32api
import win32con
import win32gui
import win32process

from .models import (
    MATCH_APP,
    Monitor,
    Region,
    SourceReference,
    SourceWindow,
    WindowInfo,
)
from .win32_api import is_window_cloaked, process_image_path


def process_exe_name(process_id: int) -> str:
    """Return the lower-case file name of a process's program, or "" if unknown."""

    path = process_image_path(process_id)
    return os.path.basename(path).lower() if path else ""


def window_source(hwnd: int) -> SourceReference:
    _, process_id = win32process.GetWindowThreadProcessId(hwnd)
    return SourceReference(
        title=win32gui.GetWindowText(hwnd),
        class_name=win32gui.GetClassName(hwnd),
        process_id=process_id,
        exe_name=process_exe_name(process_id),
    )


def source_matches(first: SourceReference, second: SourceReference) -> bool:
    return (
        first.title == second.title
        and first.class_name == second.class_name
        and first.process_id == second.process_id
    )


class WindowSnapshot:
    """Visible top-level windows from one enumeration, with cached program names."""

    def __init__(
        self, windows: list[WindowInfo], exe_names: dict[int, str] | None = None
    ) -> None:
        self.windows = windows
        self._exe_names: dict[int, str] = dict(exe_names or {})

    def exe_name(self, process_id: int) -> str:
        if process_id not in self._exe_names:
            self._exe_names[process_id] = process_exe_name(process_id)
        return self._exe_names[process_id]

    def window(self, hwnd: int | None) -> WindowInfo | None:
        return next((window for window in self.windows if window.hwnd == hwnd), None)


def snapshot_windows() -> WindowSnapshot:
    """Enumerate visible top-level windows once, in Z order (topmost first)."""

    windows: list[WindowInfo] = []

    def enumerate_window(hwnd: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        is_main = bool(
            title
            and not win32gui.GetWindow(hwnd, win32con.GW_OWNER)
            and not extended_style & win32con.WS_EX_TOOLWINDOW
        )
        windows.append(
            WindowInfo(hwnd, title, win32gui.GetClassName(hwnd), process_id, is_main)
        )
        return True

    win32gui.EnumWindows(enumerate_window, None)
    return WindowSnapshot(windows)


def match_source(source: SourceReference, snapshot: WindowSnapshot) -> int | None:
    """Pick the window a region should show, or None when its source is absent.

    A window with the saved title always wins. In MATCH_APP mode, when no such
    window exists, another main window of the same program is used instead.
    """

    same_class = [w for w in snapshot.windows if w.class_name == source.class_name]
    candidates = [w for w in same_class if w.title == source.title]
    if not candidates and source.match_mode == MATCH_APP and source.exe_name:
        candidates = [
            w
            for w in same_class
            if w.is_main and snapshot.exe_name(w.process_id) == source.exe_name
        ]
    for window in candidates:
        if window.process_id == source.process_id:
            return window.hwnd
    return candidates[0].hwnd if candidates else None


def find_source_window(source: SourceReference) -> int | None:
    return match_source(source, snapshot_windows())


def list_monitors() -> list[Monitor]:
    """Return connected monitors with bounds in physical screen pixels."""

    found: list[tuple[int, Monitor]] = []
    for handle, _, _ in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(handle)
        left, top, right, bottom = info["Monitor"]
        digits = "".join(character for character in info["Device"] if character.isdigit())
        number = int(digits) if digits else len(found) + 1
        label = f"{number} · {right - left}×{bottom - top}"
        if info["Flags"] & win32con.MONITORINFOF_PRIMARY:
            label += " · primary"
        found.append((number, Monitor((left, top, right, bottom), label)))
    return [monitor for _, monitor in sorted(found, key=lambda item: item[0])]


def monitor_index_for(region: Region, monitors: list[Monitor]) -> int | None:
    """Return the monitor containing the overlay's center, if any."""

    center_x = region.overlay_x + region.overlay_width // 2
    center_y = region.overlay_y + region.overlay_height // 2
    for index, monitor in enumerate(monitors):
        left, top, right, bottom = monitor.rect
        if left <= center_x < right and top <= center_y < bottom:
            return index
    return None


def list_source_windows() -> list[SourceWindow]:
    """Return visible, titled top-level windows owned by other processes."""

    own_process = os.getpid()
    sources: list[SourceWindow] = []

    def enumerate_window(hwnd: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd) or win32gui.GetWindow(
            hwnd, win32con.GW_OWNER
        ):
            return True
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        if process_id == own_process:
            return True
        if not win32gui.GetWindowText(hwnd) or is_window_cloaked(hwnd):
            return True
        extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if extended_style & win32con.WS_EX_TOOLWINDOW:
            return True
        if win32gui.GetClassName(hwnd) in ("Progman", "WorkerW"):
            return True
        sources.append(SourceWindow(hwnd, window_source(hwnd)))
        return True

    win32gui.EnumWindows(enumerate_window, None)
    sources.sort(key=lambda source: source.label.lower())
    return sources
