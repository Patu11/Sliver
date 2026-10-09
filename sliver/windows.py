"""Discovery of source windows and monitors."""

from __future__ import annotations

import os

import win32api
import win32con
import win32gui
import win32process

from .models import Monitor, Region, SourceReference, SourceWindow
from .win32_api import is_window_cloaked


def window_source(hwnd: int) -> SourceReference:
    _, process_id = win32process.GetWindowThreadProcessId(hwnd)
    return SourceReference(
        title=win32gui.GetWindowText(hwnd),
        class_name=win32gui.GetClassName(hwnd),
        process_id=process_id,
    )


def source_matches(first: SourceReference, second: SourceReference) -> bool:
    return (
        first.title == second.title
        and first.class_name == second.class_name
        and first.process_id == second.process_id
    )


def find_source_window(source: SourceReference) -> int | None:
    candidates: list[tuple[int, int]] = []

    def enumerate_window(hwnd: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if win32gui.GetClassName(hwnd) != source.class_name:
            return True
        if win32gui.GetWindowText(hwnd) != source.title:
            return True
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        candidates.append((hwnd, process_id))
        return True

    win32gui.EnumWindows(enumerate_window, None)
    for hwnd, process_id in candidates:
        if process_id == source.process_id:
            return hwnd
    return candidates[0][0] if candidates else None


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
