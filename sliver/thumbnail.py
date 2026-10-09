"""DWM thumbnail wrapper."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

import win32gui

from .win32_api import (
    DWM_THUMBNAIL_PROPERTIES,
    DWM_TNP_OPACITY,
    DWM_TNP_RECTDESTINATION,
    DWM_TNP_RECTSOURCE,
    DWM_TNP_SOURCECLIENTAREAONLY,
    DWM_TNP_VISIBLE,
    dwmapi,
    HTHUMBNAIL,
)


class DwmThumbnail:
    """Owns a DWM thumbnail directed to one native Qt window."""

    def __init__(self, destination_hwnd: int, source_hwnd: int) -> None:
        self.destination_hwnd = destination_hwnd
        self.handle = HTHUMBNAIL()
        result = dwmapi.DwmRegisterThumbnail(
            wintypes.HWND(destination_hwnd),
            wintypes.HWND(source_hwnd),
            ctypes.byref(self.handle),
        )
        if result != 0:
            raise RuntimeError(
                f"DwmRegisterThumbnail failed (HRESULT 0x{result & 0xFFFFFFFF:08X})"
            )

    @staticmethod
    def destination_rect(
        client_rect: tuple[int, int, int, int],
        destination_inset: int = 0,
        desired_rect: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int, int, int]:
        """Return a valid destination rectangle clipped to the destination client area."""

        client_left, client_top, client_right, client_bottom = client_rect
        if desired_rect is None:
            inset = max(
                0,
                min(
                    destination_inset,
                    max(0, (client_right - client_left - 2) // 2),
                    max(0, (client_bottom - client_top - 2) // 2),
                ),
            )
            return (
                client_left + inset,
                client_top + inset,
                client_right - inset,
                client_bottom - inset,
            )

        left, top, right, bottom = desired_rect
        return (
            max(client_left, min(left, client_right)),
            max(client_top, min(top, client_bottom)),
            max(client_left, min(right, client_right)),
            max(client_top, min(bottom, client_bottom)),
        )

    def update(
        self,
        source_rect: tuple[int, int, int, int],
        destination_inset: int = 0,
        *,
        destination_rect: tuple[int, int, int, int] | None = None,
    ) -> None:
        left, top, right, bottom = source_rect
        client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(
            self.destination_hwnd
        )
        destination_left, destination_top, destination_right, destination_bottom = (
            self.destination_rect(
                (client_left, client_top, client_right, client_bottom),
                destination_inset,
                destination_rect,
            )
        )
        if (
            destination_right <= destination_left
            or destination_bottom <= destination_top
        ):
            raise RuntimeError("DWM thumbnail destination has no visible area")
        properties = DWM_THUMBNAIL_PROPERTIES()
        properties.dwFlags = (
            DWM_TNP_RECTDESTINATION
            | DWM_TNP_RECTSOURCE
            | DWM_TNP_OPACITY
            | DWM_TNP_VISIBLE
            | DWM_TNP_SOURCECLIENTAREAONLY
        )
        properties.rcDestination = wintypes.RECT(
            destination_left,
            destination_top,
            destination_right,
            destination_bottom,
        )
        properties.rcSource = wintypes.RECT(left, top, right, bottom)
        properties.opacity = 255
        properties.fVisible = True
        properties.fSourceClientAreaOnly = True
        result = dwmapi.DwmUpdateThumbnailProperties(
            self.handle, ctypes.byref(properties)
        )
        if result != 0:
            raise RuntimeError(
                f"DwmUpdateThumbnailProperties failed (HRESULT 0x{result & 0xFFFFFFFF:08X})"
            )

    def close(self) -> None:
        if self.handle:
            dwmapi.DwmUnregisterThumbnail(self.handle)
            self.handle = HTHUMBNAIL()
