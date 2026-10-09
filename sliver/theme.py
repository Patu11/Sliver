"""Colors, stylesheet and palette."""

from __future__ import annotations

from string import Template

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


THEME = {
    "window": "#1b1b1f",
    "sidebar": "#202026",
    "surface": "#2a2a31",
    "surface_hover": "#33333b",
    "surface_pressed": "#25252b",
    "border": "#393941",
    "border_strong": "#4d4d57",
    "text": "#f2f2f5",
    "muted": "#a3a3ae",
    "subtle": "#6e6e7a",
    "accent": "#4cc2ff",
    "accent_hover": "#6fd0ff",
    "on_accent": "#00263a",
    "danger": "#ff7b7b",
    "danger_surface": "#3b2327",
    "success": "#6ccb5f",
    "preview": "#111114",
}


STYLESHEET = Template("""
QMainWindow, QWidget#root { background: $window; }
QWidget {
    color: $text;
    font-family: "Segoe UI Variable Text", "Segoe UI";
    font-size: 10pt;
}
QLabel { background: transparent; }
QWidget#header { background: $sidebar; border-bottom: 1px solid $border; }
QWidget#sidebar { background: $sidebar; border-right: 1px solid $border; }
QLabel#appTitle { font-size: 12pt; font-weight: 600; }
QLabel#fieldLabel, QLabel#muted { color: $muted; }
QLabel#cardTitle { font-weight: 600; }
QLabel#cardSubtitle { color: $muted; font-size: 9pt; }
QLabel#emptyTitle { font-size: 18pt; font-weight: 600; }
QLabel#pickerTitle, QLabel#dialogTitle { font-size: 12pt; font-weight: 600; }
QLabel#stepNumber {
    background: $surface;
    border: 1px solid $border;
    border-radius: 12px;
    color: $accent;
    font-weight: 600;
}
QLabel#statusPill {
    border-radius: 9px;
    padding: 1px 9px;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#statusPill[state="ok"] { color: $success; background: #213326; }
QLabel#statusPill[state="off"] { color: $muted; background: $surface; }
QPushButton {
    background: $surface;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover { background: $surface_hover; border-color: $border_strong; }
QPushButton:pressed { background: $surface_pressed; }
QPushButton:disabled { color: $subtle; }
QPushButton#primaryButton {
    background: $accent;
    border: 1px solid $accent;
    color: $on_accent;
    font-weight: 600;
}
QPushButton#primaryButton:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton#dangerButton { color: $danger; }
QPushButton#dangerButton:hover { background: $danger_surface; border-color: $danger; }
QPushButton#chipButton { padding: 2px 10px; border-radius: 11px; font-size: 9pt; }
QPushButton#linkButton {
    background: transparent;
    border: none;
    color: $accent;
    font-weight: 600;
    padding: 4px 8px;
}
QPushButton#linkButton:hover { color: $accent_hover; }
QLineEdit, QSpinBox, QComboBox {
    background: $surface;
    border: 1px solid $border;
    border-bottom: 1px solid $border_strong;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover { background: $surface_hover; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-bottom: 2px solid $accent; }
QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border_strong;
    outline: 0;
    selection-background-color: $surface_hover;
    selection-color: $text;
}
QLineEdit#nameEdit {
    background: transparent;
    border: 1px solid transparent;
    font-size: 16pt;
    font-weight: 600;
    padding: 2px 6px;
}
QLineEdit#nameEdit:hover { border-color: $border; }
QLineEdit#nameEdit:focus { background: $surface; border-bottom: 2px solid $accent; }
QSlider::groove:horizontal { height: 4px; background: $border_strong; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal {
    background: $accent;
    border: 4px solid $surface_hover;
    width: 12px;
    height: 12px;
    margin: -8px 0;
    border-radius: 10px;
}
QSlider::handle:horizontal:hover { background: $accent_hover; }
QListWidget { background: transparent; border: none; outline: 0; }
QListWidget#regionList::item {
    background: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    margin: 2px 0;
}
QListWidget#regionList::item:hover { background: $surface_hover; }
QListWidget#regionList::item:selected { background: $surface_hover; border: 1px solid $accent; }
QListWidget#sourceList::item { border-radius: 6px; margin: 1px 0; }
QListWidget#sourceList::item:hover { background: $surface; }
QListWidget#sourceList::item:selected { background: $surface_hover; border: 1px solid $accent; }
QFrame#previewFrame { background: $preview; border: 1px solid $border; border-radius: 10px; }
QFrame#banner {
    background: $surface;
    border: 1px solid $border;
    border-left: 3px solid $accent;
    border-radius: 6px;
}
QFrame#toast { background: #3a3a43; border: 1px solid $border_strong; border-radius: 8px; }
QDialog#sourcePicker { background: $sidebar; border: 1px solid $border_strong; }
QMenu { background: $surface; border: 1px solid $border_strong; padding: 4px; }
QMenu::item { padding: 6px 28px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background: $surface_hover; }
QMenu::item:disabled { color: $subtle; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }
QToolTip { background: $surface; color: $text; border: 1px solid $border_strong; padding: 4px 8px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical {
    background: $border_strong;
    border-radius: 3px;
    min-height: 24px;
    margin: 2px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
""")


def apply_theme(qt_app: QApplication) -> None:
    """Apply the Fluent-style dark theme, tinted with the Windows accent color."""

    accent = qt_app.palette().color(QPalette.ColorRole.Accent)
    if accent.isValid() and accent.saturation() > 40:
        for _ in range(8):
            if accent.lightness() >= 165:
                break
            accent = accent.lighter(115)
        THEME["accent"] = accent.name()
        THEME["accent_hover"] = accent.lighter(112).name()
        THEME["on_accent"] = "#000000" if accent.lightness() >= 150 else "#ffffff"

    qt_app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: "window",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "surface",
        QPalette.ColorRole.AlternateBase: "sidebar",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "surface",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.Highlight: "accent",
        QPalette.ColorRole.HighlightedText: "on_accent",
        QPalette.ColorRole.ToolTipBase: "surface",
        QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.PlaceholderText: "subtle",
        QPalette.ColorRole.Link: "accent",
        QPalette.ColorRole.Accent: "accent",
        QPalette.ColorRole.Mid: "border",
        QPalette.ColorRole.Dark: "border",
    }
    for role, token in roles.items():
        palette.setColor(role, QColor(THEME[token]))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(THEME["subtle"]))
    qt_app.setPalette(palette)
    qt_app.setStyleSheet(STYLESHEET.substitute(THEME))
