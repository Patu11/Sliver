"""Plain data classes shared across the application."""

from __future__ import annotations

from dataclasses import dataclass, field


CONFIG_VERSION = 1


@dataclass
class SourceReference:
    title: str
    class_name: str
    process_id: int


@dataclass
class Region:
    id: str
    source: SourceReference
    x: int
    y: int
    width: int
    height: int
    name: str = "Unnamed region"
    enabled: bool = True
    opacity: int = 100
    scale: float = 100
    overlay_x: int = 100
    overlay_y: int = 100
    overlay_width: int = 300
    overlay_height: int = 200


@dataclass
class AppConfig:
    version: int = CONFIG_VERSION
    regions: list[Region] = field(default_factory=list)
    selected_source: SourceReference | None = None
    previews_enabled: bool = True


@dataclass
class SourceWindow:
    hwnd: int
    reference: SourceReference

    @property
    def label(self) -> str:
        return (
            f"{self.reference.title}  "
            f"[{self.reference.class_name} | PID {self.reference.process_id}]"
        )


@dataclass
class Monitor:
    rect: tuple[int, int, int, int]
    label: str
