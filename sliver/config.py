"""Loading and saving config.json."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict

from .models import AppConfig, CONFIG_VERSION, Region, SourceReference


DATA_FOLDER = "Sliver"
# Data folder used while the application was called Region Overlay.
LEGACY_DATA_FOLDER = "overlay"


def _data_root() -> str:
    return os.environ.get("APPDATA", os.path.expanduser("~"))


def get_config_path():
    base = os.path.join(_data_root(), DATA_FOLDER)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "config.json")


def migrate_legacy_data() -> None:
    """Copy config.json and settings.json from the old data folder on first start.

    Nothing is overwritten and the old folder is left in place as a backup.
    """

    old = os.path.join(_data_root(), LEGACY_DATA_FOLDER)
    new = os.path.join(_data_root(), DATA_FOLDER)
    names = ("config.json", "settings.json")
    if not os.path.isdir(old):
        return
    if any(os.path.exists(os.path.join(new, name)) for name in names):
        return
    os.makedirs(new, exist_ok=True)
    for name in names:
        source = os.path.join(old, name)
        if os.path.isfile(source):
            try:
                shutil.copy2(source, os.path.join(new, name))
            except OSError:
                pass


def source_from_dict(data: dict) -> SourceReference:
    return SourceReference(
        title=str(data["title"]),
        class_name=str(data["class_name"]),
        process_id=int(data.get("process_id", 0)),
    )


def region_from_dict(data: dict) -> Region:
    width = max(1, int(data["width"]))
    height = max(1, int(data["height"]))
    scale = max(25, min(400, float(data.get("scale", 100))))
    overlay_width = max(1, int(data.get("overlay_width", width)))
    overlay_height = max(1, int(data.get("overlay_height", height)))
    if width < 50 and overlay_width == 50:
        overlay_width = width
    if height < 50 and overlay_height == 50:
        overlay_height = height
    return Region(
        id=str(data["id"]),
        source=source_from_dict(data["source"]),
        x=int(data["x"]),
        y=int(data["y"]),
        width=width,
        height=height,
        name=str(data.get("name") or f"Region {str(data['id'])[:8]}"),
        enabled=bool(data.get("enabled", True)),
        opacity=max(10, min(100, int(data.get("opacity", 100)))),
        scale=scale,
        overlay_x=int(data.get("overlay_x", 100)),
        overlay_y=int(data.get("overlay_y", 100)),
        overlay_width=overlay_width,
        overlay_height=overlay_height,
    )


class ConfigStore:
    """Reads and writes the original version-1 configuration format."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.error: str | None = None

    def load(self) -> AppConfig:
        if not os.path.exists(self.path):
            return AppConfig()
        try:
            with open(self.path, "r", encoding="utf-8") as config_file:
                data = json.load(config_file)
            if data.get("version") != CONFIG_VERSION:
                raise ValueError("unsupported configuration version")
            return AppConfig(
                version=CONFIG_VERSION,
                regions=[region_from_dict(item) for item in data.get("regions", [])],
                selected_source=(
                    source_from_dict(data["selected_source"])
                    if data.get("selected_source")
                    else None
                ),
                previews_enabled=bool(data.get("previews_enabled", True)),
            )
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            self.error = f"Could not load config.json: {error}"
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        temporary_path = f"{self.path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as config_file:
            json.dump(asdict(config), config_file, indent=2)
            config_file.write("\n")
        os.replace(temporary_path, self.path)
