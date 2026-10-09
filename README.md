# Sliver

A Windows-only Python application that keeps selected parts of other application windows on screen as live, always-on-top, click-through overlays. Each overlay is a DWM thumbnail, so it stays live without capturing or copying pixels.

## Requirements

- Windows 10 or 11 with Desktop Window Manager enabled
- Python 3.10 or newer
- `PyQt6` 6.6 or newer
- `pywin32`

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python sliver.py
```

To start it without a console window, use `pythonw` instead:

```powershell
pythonw sliver.py
```

`python -m sliver` works as well.

## Usage

### Creating a region

1. Click **+ New region** (<kbd>Ctrl</kbd>+<kbd>N</kbd>). A searchable list of open windows appears, with the most recently used window first. Minimized windows, tool windows and the desktop are not listed; **Refresh** reloads the list.
2. Pick a window and click **Select area**, then drag a rectangle over it. A live 4× magnifier follows the cursor; press <kbd>Esc</kbd> to cancel.
3. The new region appears in the sidebar and as an overlay on screen.

### Editing a region

Select a region in the sidebar to edit it on the right:

- **Name** — click the title (or press <kbd>F2</kbd>) to rename it.
- **Live preview** — shows exactly what the overlay displays.
- **Source** — the program and title of the source window, a **Running / Not running** badge, and **Reselect area** to drag a new rectangle over the same window.
- **Follow** (the dropdown under Source) — how the region finds its window again:
  - *Follow this exact window title* — the region waits for a window with the same title. Use it to keep a region tied to one specific window, for example one of several game clients.
  - *Follow any window of this app* — a window with the saved title is still preferred, but when it is gone another window of the same program is shown instead. This is the default for new regions and keeps them working when the title changes.
- **Connect to window…** — attaches the region to another window while keeping its area, size and position.
- **Opacity** — 10–100 %.
- **Size** — 25–400 % of the source area, with 50 / 100 / 200 % shortcuts.
- **Area** — exact X, Y, Width and Height of the source crop, in pixels of the source window's client area.
- **Overlay** — the overlay's position and size on screen in pixels. The fields follow the overlay while you drag it in Edit layout. With **Keep proportions** on, changing the width or height keeps the shape of the source area.
- **Monitor** — shows which monitor the overlay is on and moves it to another one, also when it was left off screen on a disconnected monitor.
- **Duplicate** and **Delete** — deleting asks for confirmation first and can still be undone from the notification or with <kbd>Ctrl</kbd>+<kbd>Z</kbd>.

### Sidebar and header

- Each sidebar card has a dot showing whether the source window was found and a switch that shows or hides that one overlay. Right-click a card for Rename, Reselect area, Duplicate and Delete. A filter box appears once there are more than three regions.
- **Previews** (header) shows or hides every overlay at once and is remembered between launches.
- **Edit layout** (header, <kbd>Ctrl</kbd>+<kbd>E</kbd>) lets you drag an overlay or resize it from an edge or corner. Click **Done** in the banner to make overlays click-through again.

### Tray icon

By default, closing the window keeps Sliver running in the system tray, so your overlays stay on screen. The tray menu offers **Open Sliver**, **New region…**, **Previews**, **Edit layout**, **Settings…** and **Quit**.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| <kbd>Ctrl</kbd>+<kbd>N</kbd> | New region |
| <kbd>Ctrl</kbd>+<kbd>E</kbd> | Toggle Edit layout |
| <kbd>F2</kbd> | Rename the selected region |
| <kbd>Del</kbd> | Delete the selected region (with the region list focused) |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> | Undo the last delete |
| <kbd>Esc</kbd> | Cancel area selection |

## Settings

Open **Settings** at the bottom of the sidebar or from the tray menu.

| Setting | Default | Effect |
|---|---|---|
| **Config file** — Change… / Reset to default / Open folder | `%APPDATA%\Sliver` | Folder that holds `config.json` |
| **Ask before deleting a region** | On | Show a confirmation before a region is deleted |
| **Keep running in the tray when the window is closed** | On | On: the X button hides the window. Off: the X button quits the app |

When you choose another folder for `config.json`:

- if the folder has no `config.json`, the current regions are written there;
- if it already has one, you choose whether to load that file or replace it with the current regions;
- the previous file is left in place.

If the chosen folder is unavailable at startup (for example, a disconnected drive), the default location is used for that session and the setting is kept.

## Files

| File | Location | Contents |
|---|---|---|
| `config.json` | `%APPDATA%\Sliver` by default, or the folder chosen in Settings | Regions, their overlay layout, the last used source window and the Previews state |
| `settings.json` | always `%APPDATA%\Sliver` | Config folder, delete confirmation, close-to-tray behavior |

Every change is saved automatically. Configuration files from earlier versions remain compatible.

The application used to be called Region Overlay and kept its data in `%APPDATA%\overlay`. On the first start, `config.json` and `settings.json` are copied from there to `%APPDATA%\Sliver`; the old folder is left in place as a backup.

## Limitations

- In *Follow this exact window title* mode a region shows **Not running** whenever the window title changes (a different browser tab, another character or document in the title) until the title matches again. Regions created before this option existed use that mode until you switch them.
- In *Follow any window of this app* mode, with several windows of the same program open and the saved title gone, the region picks the topmost one, which may not be the one you want. Use **Connect to window…** to choose.
- An overlay is hidden while its source window is minimized.
- Source areas use fixed client-area pixels and do not scale when the source window is resized.
- Overlays rely on the Windows DWM and pywin32 APIs, so the application is Windows-only.

## Project structure

`sliver.py` is a thin launcher; the application lives in the `sliver` package:

| Module | Contents |
|---|---|
| `__main__.py` | Entry point for `python -m sliver` |
| `app.py` | `main()` — startup sequence |
| `controller.py` | `OverlayApplication` — ties configuration, settings, overlays and the UI together |
| `models.py` | Data classes: `Region`, `SourceReference`, `AppConfig`, `SourceWindow`, `Monitor` |
| `config.py` | Reading and writing `config.json`, data folder and migration from the old name |
| `settings.py` | Reading and writing `settings.json` |
| `windows.py` | Finding source windows and monitors |
| `win32_api.py` | ctypes declarations for DWM and kernel32, DPI and taskbar helpers |
| `thumbnail.py` | `DwmThumbnail` wrapper |
| `overlay_window.py` | The always-on-top overlay window and its edit border |
| `capture.py` | Area selection overlay and magnifier |
| `theme.py` | Colors, stylesheet and palette (dark theme tinted with the Windows accent color) |
| `resources.py` | Application icon and per-process icons |
| `ui/control_window.py` | Main window: header, sidebar, banner |
| `ui/details_panel.py` | Editable properties of the selected region |
| `ui/live_preview.py` | Live DWM preview inside the details panel |
| `ui/region_card.py` | Sidebar card for one region |
| `ui/source_picker.py` | Searchable window picker |
| `ui/dialogs.py` | Delete confirmation and Settings dialogs |
| `ui/widgets.py` | Toggle switch, labels, toast notifications |
