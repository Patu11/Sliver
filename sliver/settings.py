"""Application settings kept in a fixed place, separate from config.json."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from .config import get_config_path


@dataclass
class AppSettings:
    # Folder holding config.json; None means the default location.
    config_dir: str | None = None
    confirm_delete: bool = True
    # Closing the window hides it to the tray instead of quitting.
    close_to_tray: bool = True


def get_settings_path() -> str:
    return os.path.join(os.path.dirname(get_config_path()), "settings.json")


def resolve_config_path(settings: AppSettings) -> str:
    """Return the config.json path chosen in the settings, or the default one."""

    if settings.config_dir:
        return os.path.join(settings.config_dir, "config.json")
    return get_config_path()


class SettingsStore:
    """Reads and writes settings.json; a missing or broken file means defaults."""

    def __init__(self, path: str) -> None:
        self.path = path

    def load(self) -> AppSettings:
        try:
            with open(self.path, "r", encoding="utf-8") as settings_file:
                data = json.load(settings_file)
            config_dir = data.get("config_dir")
            return AppSettings(
                config_dir=str(config_dir) if config_dir else None,
                confirm_delete=bool(data.get("confirm_delete", True)),
                close_to_tray=bool(data.get("close_to_tray", True)),
            )
        except (OSError, ValueError, TypeError, AttributeError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        temporary_path = f"{self.path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as settings_file:
            json.dump(asdict(settings), settings_file, indent=2)
            settings_file.write("\n")
        os.replace(temporary_path, self.path)
