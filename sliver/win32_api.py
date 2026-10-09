"""Win32, DWM and kernel32 declarations used through ctypes."""

from __future__ import annotations

import ctypes
from ctypes import HRESULT, wintypes

from PyQt6.QtGui import QColor


DWM_TNP_RECTDESTINATION = 0x00000001


DWM_TNP_RECTSOURCE = 0x00000002


DWM_TNP_OPACITY = 0x00000004


DWM_TNP_VISIBLE = 0x00000008


DWM_TNP_SOURCECLIENTAREAONLY = 0x00000010


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("dwFlags", wintypes.DWORD),
        ("rcDestination", wintypes.RECT),
        ("rcSource", wintypes.RECT),
        ("opacity", ctypes.c_ubyte),
        ("fVisible", wintypes.BOOL),
        ("fSourceClientAreaOnly", wintypes.BOOL),
    ]


HTHUMBNAIL = wintypes.HANDLE


dwmapi = ctypes.windll.dwmapi


dwmapi.DwmRegisterThumbnail.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.POINTER(HTHUMBNAIL),
]


dwmapi.DwmRegisterThumbnail.restype = HRESULT


dwmapi.DwmUpdateThumbnailProperties.argtypes = [
    HTHUMBNAIL,
    ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES),
]


dwmapi.DwmUpdateThumbnailProperties.restype = HRESULT


dwmapi.DwmUnregisterThumbnail.argtypes = [HTHUMBNAIL]


dwmapi.DwmUnregisterThumbnail.restype = HRESULT


dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]


dwmapi.DwmGetWindowAttribute.restype = HRESULT


dwmapi.DwmSetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]


dwmapi.DwmSetWindowAttribute.restype = HRESULT


DWMWA_USE_IMMERSIVE_DARK_MODE = 20


DWMWA_CLOAKED = 14


DWMWA_CAPTION_COLOR = 35


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


kernel32 = ctypes.windll.kernel32


kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]


kernel32.OpenProcess.restype = wintypes.HANDLE


kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]


kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


kernel32.CloseHandle.restype = wintypes.BOOL


def is_window_cloaked(hwnd: int) -> bool:
    cloaked = wintypes.DWORD()
    result = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return result == 0 and cloaked.value != 0


def process_image_path(process_id: int) -> str | None:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return None
    finally:
        kernel32.CloseHandle(handle)


def apply_window_theme(hwnd: int, caption_color: str) -> None:
    """Ask DWM for a dark title bar that matches the window background."""

    dark = ctypes.c_int(1)
    dwmapi.DwmSetWindowAttribute(
        hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), ctypes.sizeof(dark)
    )
    color = QColor(caption_color)
    colorref = wintypes.DWORD(color.red() | color.green() << 8 | color.blue() << 16)
    dwmapi.DwmSetWindowAttribute(
        hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(colorref), ctypes.sizeof(colorref)
    )


def set_app_user_model_id() -> None:
    """Give the process its own taskbar identity so Windows shows our icon, not python.exe's."""

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Sliver.App")
    except (AttributeError, OSError):
        pass


def enable_per_monitor_dpi_awareness() -> None:
    """Keep Win32 client bounds and Qt's native windows in the same DPI context."""

    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass
