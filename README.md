# Project Zomboid Day Length Changer

A small Windows utility for changing only the `DayLength` setting in a Project Zomboid Build 42.21 save.

## Features

- Simple graphical interface; no command-line knowledge needed.
- Supports the vanilla day-length choices from 15 minutes to real-time.
- Changes only the `DayLength` value in `map_sand.bin`; all other settings are preserved.
- Creates a timestamped backup beside the save before writing.
- Refuses files whose version does not match Build 42.21 (world version 249, sandbox version 6).
- Uses only Python's standard library.

## Requirements

- Windows
- Python 3 with Tkinter installed and `python` available on `PATH`

## Usage

1. Close Project Zomboid.
2. Download or clone this repository.
3. Run `DayLengthChanger.bat`.
4. Browse to the save's `map_sand.bin`, choose a duration, and click **Apply with backup**.
5. Keep the generated backup until you have confirmed the save loads correctly.

For example, a single-player Sandbox save is usually located at:

```text
%UserProfile%\Zomboid\Saves\Sandbox\<SaveName>\map_sand.bin
```

## Build 42.21 day-length values

| Value | Duration |
| ---: | --- |
| 1 | 15 minutes |
| 2 | 30 minutes |
| 3 | 1 hour |
| 4 | 1 hour, 30 minutes |
| 5 | 2 hours |
| 6–26 | 3–23 hours |
| 27 | Real-time (24 hours) |

## Safety and compatibility

The tool is intentionally limited to Build 42.21 saves with world version `249` and sandbox version `6`. It rejects other versions rather than guessing their format or option numbering. Back up the whole save before editing, and do not run the tool while the game is open.

This utility has been validated against Build 42.21's `map_sand.bin` format. It is provided as-is; test on a copy of an important save first.
