"""Application files and icons."""

from __future__ import annotations

import os

from PyQt6.QtCore import QFileInfo
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFileIconProvider


def resource_path(name: str) -> str:
    """Resolve a file that ships next to sliver.py, above this package."""

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, name)


def app_icon() -> QIcon:
    return QIcon(resource_path("icon.ico"))


_icon_provider: QFileIconProvider | None = None


_process_icons: dict[str, QIcon] = {}


def process_icon(path: str | None) -> QIcon:
    global _icon_provider
    if not path:
        return app_icon()
    if path not in _process_icons:
        if _icon_provider is None:
            _icon_provider = QFileIconProvider()
        _process_icons[path] = _icon_provider.icon(QFileInfo(path))
    return _process_icons[path]
