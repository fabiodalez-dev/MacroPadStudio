# ch57x-macropad-manager — User Guide

## Table of contents

1. [Hardware identification](#1-hardware-identification)
2. [Troubleshooting "device not detected"](#2-troubleshooting-device-not-detected)
3. [Installation](#3-installation)
4. [Using the GUI](#4-using-the-gui)
5. [Editing YAML presets by hand](#5-editing-yaml-presets-by-hand)
6. [Knob behaviour](#6-knob-behaviour)
7. [Restoring and backing up presets](#7-restoring-and-backing-up-presets)

---

## 1. Hardware identification

The macro pad supported by this project uses a **CH57x** microcontroller and presents the following USB identifiers:

| Field | Value |
|---|---|
| Vendor ID (VID) | `0x1189` |
| Product ID (PID) | `0x8890` |
| Layout | 3 programmable keys + 1 rotary knob |
| Interface | USB HID (no VIA / QMK firmware) |

**This is NOT a QMK or VIA device.** Do not attempt to flash VIA-compatible firmware or use Vial/QMK Toolbox — the CH57x chip uses a proprietary HID protocol that `ch57x-keyboard-tool` implements.

### Confirming your VID/PID on macOS

**Option A — system_profiler (human-readable)**

```bash
system_profiler SPUSBDataType | grep -A5 -i "1189"
```

You should see something like:

```
Unknown Device:
  Product ID: 0x8890
  Vendor ID:  0x1189
  ...
```

**Option B — ioreg**

```bash
ioreg -p IOUSB -l | grep -i "0x1189"
```

**Option C — verify script**

```bash
bash scripts/verify.sh
```

---

## 2. Troubleshooting "device not detected"

### Charge-only cable (most common cause)

Many USB cables — including those bundled with small gadgets — carry power only and have no data wires. If `system_profiler SPUSBDataType` or `ioreg` show no entry for VID `0x1189`, the first thing to try is a different cable.

How to test: plug the macro pad into a port you know works with another USB HID device, using a cable that you have confirmed carries data (e.g. the one you use for your phone with file transfer).

### Other common causes

| Symptom | Fix |
|---|---|
| Cable swapped, still not detected | Try a different USB port. Some hubs filter HID devices. |
| Detected but upload fails with permission error | Run with `sudo` — macOS requires root for raw HID access. |
| Upload exits immediately with no output | The device may have entered a sleep state. Unplug, replug, then retry within a few seconds. |
| `ch57x-keyboard-tool` says "no device found" | Confirm VID/PID with `system_profiler`; ensure libusb is installed (`brew list libusb`). |
| macOS "USB Accessories Disabled" alert | Go to System Settings → Privacy & Security → USB and re-enable the device, or unplug and replug. |

---

## 3. Installation

### Prerequisites

| Requirement | How to get it |
|---|---|
| macOS 12 or later | — |
| Homebrew | [https://brew.sh](https://brew.sh) |
| Rust toolchain | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| libusb | installed by `scripts/install.sh` |
| Python 3.9+ | ships with macOS; also available via Homebrew |

### Automated install

```bash
bash scripts/install.sh
```

The script:
1. Checks for Homebrew (exits with instructions if missing).
2. Installs `libusb` via `brew install libusb`.
3. Checks for Cargo; if missing, prints the Rust install command and exits.
4. Runs `cargo install ch57x-keyboard-tool`.
5. Installs Python packages: `customtkinter`, `pyyaml`, `pillow`.
6. Calls `scripts/verify.sh` to confirm everything is working.

### Manual install

```bash
brew install libusb
cargo install ch57x-keyboard-tool
python3 -m pip install customtkinter pyyaml pillow
```

---

## 4. Using the GUI

Launch with:

```bash
python3 app/macropad_studio.py
```

### Launcher tab

- Displays all preset categories in the sidebar.
- Click a category to see the presets it contains.
- Click a preset name to load its bindings in a preview panel.
- Click **Upload** to write the preset to the device. A macOS password dialog (via `osascript`) will prompt for your administrator password — this replaces the need to type `sudo` in the terminal.

### Editor tab

- Loads a preset into editable fields: three key slots and three knob actions (CCW / press / CW).
- Each field accepts a token string in the format used by `ch57x-keyboard-tool` (e.g. `cmd-shift-p`, `volumeup`, `wheel(-3)`).
- Click **Save** to write changes back to the YAML file.
- Click **Upload** to push the edited preset to the device immediately.

### Key recorder

- Click the **Record** button next to any field.
- Press the key combination on your keyboard.
- The GUI captures the event and converts it to the correct token format.
- Press **Escape** or click **Stop** to exit recording mode.

---

## 5. Editing YAML presets by hand

### File structure

Every preset is a self-contained YAML file. The minimal schema for a 3-key + 1-knob device is:

```yaml
orientation: normal
rows: 1
columns: 3
knobs: 1

layers:
  - buttons:
      - ["<key1>", "<key2>", "<key3>"]
    knobs:
      - ccw:   "<action>"
        press: "<action>"
        cw:    "<action>"
```

- `orientation`: `normal` or `invert` (flips the button order).
- `rows` / `columns`: always `1` / `3` for this device.
- `knobs`: always `1`.
- `layers`: list with one entry (the device supports a single layer via this tool).

### Key token vocabulary

Tokens are strings that `ch57x-keyboard-tool` understands. Combine modifiers and a key with hyphens.

**Modifiers**

| Token | Key |
|---|---|
| `ctrl` | Left Control |
| `shift` | Left Shift |
| `alt` / `opt` | Left Option/Alt |
| `cmd` / `win` | Left Command |
| `rctrl`, `rshift`, `ralt`, `rcmd` | Right-hand equivalents |

**Common keys** — letters (`a`–`z`), digits (`0`–`9`), `enter`, `escape`, `backspace`, `tab`, `space`, `delete`, `home`, `end`, `pageup`, `pagedown`, arrow keys (`up`, `down`, `left`, `right`), function keys (`f1`–`f24`), punctuation (`minus`, `equal`, `leftbracket`, `rightbracket`, `backslash`, `semicolon`, `quote`, `grave`, `comma`, `dot`, `slash`).

**Media keys** — `play`, `next`, `previous`, `stop`, `mute`, `volumeup`, `volumedown`.

**macOS-specific** — `macbrightnessup`, `macbrightnessdown`.

**Mouse actions** (knob-friendly)

```yaml
ccw: "wheel(-3)"    # scroll up 3 ticks
cw:  "wheel(3)"     # scroll down 3 ticks
```

**Combination examples**

```yaml
"cmd-z"               # Undo
"cmd-shift-z"         # Redo
"cmd-shift-p"         # Command palette (VS Code)
"ctrl-shift-leftbracket"  # Previous tab
```

### Validation

Before uploading, validate a preset:

```bash
~/.cargo/bin/ch57x-keyboard-tool validate < presets/dev/vscode-edit.yaml
```

No output and exit code 0 means the preset is valid.

---

## 6. Knob behaviour

The rotary encoder on the macro pad generates three distinct events:

| Event | YAML key | Typical use |
|---|---|---|
| Rotate counter-clockwise | `ccw` | Scroll up / previous track / zoom out |
| Press (click) | `press` | Play/Pause / confirm / toggle |
| Rotate clockwise | `cw` | Scroll down / next track / zoom in |

Each rotation step sends one key event. Faster rotation sends more events in quick succession — useful for `volumeup`/`volumedown` or `wheel()` actions.

The `wheel(n)` action sends a mouse scroll event of `n` ticks. Use negative values for "up" and positive for "down" (matches macOS natural scrolling direction when reversed scrolling is off).

---

## 7. Restoring and backing up presets

### Backup

All presets are plain text YAML files in `presets/`. Back them up with any standard method:

```bash
cp -r presets ~/Documents/macropad-presets-backup
# or add the whole repository to git
```

### Restore

Upload any previously saved preset:

```bash
bash scripts/upload.sh path/to/your-preset.yaml
```

### Factory reset

The device firmware does not have a documented factory reset. To return to a neutral state, create a minimal preset that assigns no meaningful keys:

```yaml
orientation: normal
rows: 1
columns: 3
knobs: 1

layers:
  - buttons:
      - ["", "", ""]
    knobs:
      - ccw:   ""
        press: ""
        cw:    ""
```

Upload it with `scripts/upload.sh`.

### Multiple profiles

The device stores exactly one configuration at a time. To switch between profiles, upload the desired preset:

```bash
bash scripts/upload.sh photoshop-general   # switch to Photoshop layout
# ... work in Photoshop ...
bash scripts/upload.sh vscode-edit         # switch to VS Code layout
```

The GUI Launcher is designed to make this one-click switching fast.
