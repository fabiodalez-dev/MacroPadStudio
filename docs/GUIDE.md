# MacroPad Studio — User Guide

## Table of contents

1. [Hardware identification](#1-hardware-identification)
2. [Choosing your device profile](#2-choosing-your-device-profile)
3. [Troubleshooting "device not detected"](#3-troubleshooting-device-not-detected)
4. [Installation](#4-installation)
5. [Using the GUI](#5-using-the-gui)
6. [Editing YAML presets by hand](#6-editing-yaml-presets-by-hand)
7. [Using layers](#7-using-layers)
8. [Building key sequences with delays](#8-building-key-sequences-with-delays)
9. [Mouse actions](#9-mouse-actions)
10. [LED control](#10-led-control)
11. [Using the larger pads (6-, 9-, 12-key)](#11-using-the-larger-pads-6--9--12-key)
12. [Knob behaviour](#12-knob-behaviour)
13. [Restoring and backing up presets](#13-restoring-and-backing-up-presets)

---

## 1. Hardware identification

CH57x macro pads share VID `0x1189` and vary by geometry. Confirm your pad's PID with:

```bash
system_profiler SPUSBDataType | grep -A5 -i "1189"
```

| Geometry | Buttons | Knobs | PID |
|---|---|---|---|
| 3×1 | 3 | 1 | `0x8890` |
| 3×2 | 6 | 1 | `0x8890` |
| 3×3 | 9 | 2 | `0x8890` |
| 4×1 | 4 | 1 | `0x8840` |
| 4×3 | 12 | 3 | `0x8840` |
| 5×3 | 15 | 3 | `0x8842` |
| 12-key (alt) | 12 | 3 | `0x8842` |

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

## 2. Choosing your device profile

MacroPad Studio supports multiple pad geometries. When you open the GUI, a **device selector** drop-down appears at the top. You can:

- Let **auto-detection** fill it in — the GUI scans connected USB devices on launch and pre-selects the matching profile based on the detected PID.
- Select manually if you have multiple pads connected or want to prepare a preset for a different device.

The profile controls how many button slots and knob slots the editor shows, and which rows the YAML `buttons` array must provide.

When writing YAML by hand, set `rows`, `columns`, and `knobs` to match your hardware:

```yaml
rows: 3
columns: 3
knobs: 2
```

Uploading a preset to a device with a mismatched geometry will be rejected by `ch57x-keyboard-tool` with a validation error.

---

## 3. Troubleshooting "device not detected"

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

## 4. Installation

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

## 5. Using the GUI

Launch with:

```bash
python3 app/macropad_studio.py
```

### Device selector

A drop-down at the top of the window lists detected devices. Auto-detection runs on launch. If your device is not detected, select the correct geometry manually and plug/replug the pad.

### Launcher tab

- Displays all preset categories in the sidebar.
- Click a category to see the presets it contains.
- Click a preset name to load its bindings in a preview panel.
- Click **Upload** to write the preset to the device. A macOS password dialog (via `osascript`) will prompt for your administrator password — this replaces the need to type `sudo` in the terminal.

### Editor tab

- Loads a preset into editable fields: button slots and knob actions (CCW / press / CW).
- Use the **layer tabs** (Layer 1 / Layer 2 / Layer 3) to switch between layers and edit each one independently.
- Each field accepts a token string in the format used by `ch57x-keyboard-tool` (e.g. `cmd-shift-p`, `volumeup`, `wheel(-3)`).
- Click **Save** to write changes back to the YAML file.
- Click **Upload** to push the edited preset to the device immediately.

### Key recorder

- Click the **Record** button next to any field.
- Press the key combination on your keyboard.
- The GUI captures the event and converts it to the correct token format.
- Press **Escape** or click **Stop** to exit recording mode.

### LED panel

- Located in the **LED** tab.
- Set per-key colour by clicking a key slot and choosing a colour from the colour picker.
- Adjust global **brightness** with the slider.
- Choose an **effect mode**: Static, Breathing, or Reactive.
- Click **Apply** to send the LED configuration to the device.

---

## 6. Editing YAML presets by hand

### File structure

Every preset is a self-contained YAML file. The schema for a 3×3 device with 2 knobs and 2 layers is:

```yaml
model: ch57x
orientation: normal
rows: 3
columns: 3
knobs: 2

layers:
  - buttons:
      - ["<r1c1>", "<r1c2>", "<r1c3>"]
      - ["<r2c1>", "<r2c2>", "<r2c3>"]
      - ["<r3c1>", "<r3c2>", "<r3c3>"]
    knobs:
      - ccw:   "<action>"
        press: "<action>"
        cw:    "<action>"
      - ccw:   "<action>"
        press: "<action>"
        cw:    "<action>"
  - buttons:
      # ... second layer bindings
    knobs:
      # ... second layer knobs
```

- `orientation`: `normal` or `invert` (flips the button order).
- `rows` / `columns`: match your physical hardware.
- `knobs`: number of rotary encoders on the pad.
- `layers`: list of up to 3 layer definitions.

For the classic 3×1 + 1 knob variant, `rows: 1`, `columns: 3`, `knobs: 1`.

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

## 7. Using layers

The device supports up to 3 independent layers. Each layer stores a complete set of button and knob bindings.

### Defining layers in YAML

Add multiple entries under the `layers` key:

```yaml
layers:
  - buttons:
      - ["cmd-z", "cmd-shift-z", "cmd-s"]   # Layer 1: everyday editing
    knobs:
      - ccw: "wheelup"
        press: "cmd-a"
        cw: "wheeldown"
  - buttons:
      - ["cmd-shift-3", "cmd-shift-4", "cmd-space"]  # Layer 2: screenshots + Spotlight
    knobs:
      - ccw: "left"
        press: "enter"
        cw: "right"
  - buttons:
      - ["cmd-c", "cmd-v", "cmd-x"]   # Layer 3: clipboard shortcuts
    knobs:
      - ccw: "volumedown"
        press: "mute"
        cw: "volumeup"
```

### Switching layers

- **On the device:** hold the dedicated layer button (if your pad has one) or use the layer-switch key binding defined in your preset.
- **In the GUI:** click the **Layer 1 / Layer 2 / Layer 3** tab in the Editor to view and edit each layer's bindings. Upload writes all layers at once.

---

## 8. Building key sequences with delays

A key sequence lets a single key slot send multiple actions in order. Actions are separated by commas. Delays are inserted with `<N>` where `N` is milliseconds.

### Syntax

```
action1,action2,<delay_ms>,action3
```

### Examples

```yaml
# Open DevTools then focus the Console panel
"cmd-alt-i,cmd-shift-j"

# Create a new layer in Photoshop, pause 200 ms, then confirm the name dialog
"cmd-shift-n,<200>,enter"

# Ripple trim then close the gap in Premiere Pro
"q,ctrl-shift-delete"

# Rename symbol in VS Code, then select all occurrences
"f2,cmd-shift-l"
```

### When to use delays

Insert a `<N>` delay when the application needs time to open a dialog or complete an animation before the next key event arrives. Typical values are 100–300 ms. Very fast sequences (no delay) work for chord-like actions.

---

## 9. Mouse actions

Mouse scroll events can be assigned to any key slot or knob action.

| Token | Action |
|---|---|
| `wheel(N)` | Scroll down N ticks (positive = down) |
| `wheel(-N)` | Scroll up N ticks |
| `wheelup` | Scroll up 1 tick (alias) |
| `wheeldown` | Scroll down 1 tick (alias) |

### Usage examples

```yaml
# Knob as smooth scroll wheel
ccw: "wheel(-3)"   # three ticks up per step
cw:  "wheel(3)"    # three ticks down per step

# Knob as volume control
ccw: "volumedown"
cw:  "volumeup"

# Button that scrolls a fixed amount
"wheel(-5)"        # jump five ticks up with one press
```

Mouse scroll events work in any application that responds to the standard macOS scroll wheel, including browsers, editors, image viewers, and DAWs.

---

## 10. LED control

The CH57x pads support per-key RGB lighting. MacroPad Studio provides two ways to configure LEDs.

### Via the GUI

1. Open the **LED** tab in the main window.
2. Click any key button in the visual layout to select it.
3. Use the **colour picker** to assign an RGB colour.
4. Use the **Brightness** slider to set global brightness (0–100).
5. Choose an **Effect mode** from the drop-down:
   - **Static** — fixed colour, no animation
   - **Breathing** — slow pulse between the assigned colour and off
   - **Reactive** — key lights up on press, fades back
6. Click **Apply** to upload the LED configuration to the device.

### Via YAML

LED settings can also be embedded in a preset file:

```yaml
led:
  brightness: 80          # 0–100
  effect: static          # static | breathing | reactive
  keys:
    - [red,   green, blue]     # row 1 colours in hex or named
    - [white, white, white]
    - [off,   off,   off]
```

> LED YAML support requires firmware version 2.x or later. Older pads may ignore the `led` block.

---

## 11. Using the larger pads (6-, 9-, 12-key)

Pads with more keys use the same YAML schema, extended with additional rows and knobs.

### 6-key (3×2 + 1 knob) example

```yaml
model: ch57x
orientation: normal
rows: 3
columns: 2
knobs: 1

layers:
  - buttons:
      - ["cmd-t",          "cmd-w"]
      - ["cmd-leftbracket","cmd-rightbracket"]
      - ["cmd-r",          "cmd-alt-i,cmd-shift-j"]
    knobs:
      - ccw: "wheelup"
        press: "cmd-l"
        cw: "wheeldown"
```

### 9-key (3×3 + 2 knobs) example

```yaml
rows: 3
columns: 3
knobs: 2

layers:
  - buttons:
      - ["cmd-shift-p", "cmd-p",    "cmd-z"]
      - ["cmd-shift-k", "alt-shift-f", "cmd-slash"]
      - ["f5",          "shift-f5", "f2,cmd-shift-l"]
    knobs:
      - ccw: "cmd-shift-leftbracket"
        press: "cmd-b"
        cw: "cmd-shift-rightbracket"
      - ccw: "wheelup"
        press: "cmd-k,cmd-0"
        cw: "wheeldown"
```

### 12-key (4×3 + 3 knobs) example

```yaml
rows: 4
columns: 3
knobs: 3

layers:
  - buttons:
      - ["space",       "cmd-z",    "cmd-shift-z"]
      - ["b",           "e",        "s"]
      - ["cmd-j",       "cmd-shift-n,<200>,enter", "cmd-e"]
      - ["cmd-s",       "cmd-shift-alt-s",  "cmd-shift-alt-e"]
    knobs:
      - ccw: "leftbracket"
        press: "f"
        cw: "rightbracket"
      - ccw: "cmd-minus"
        press: "cmd-0"
        cw: "cmd-equal"
      - ccw: "wheelup"
        press: "cmd-shift-alt-e"
        cw: "wheeldown"
```

Ready-to-use multi-key presets are in `presets/examples-multikey/`. See [docs/PRESETS.md](PRESETS.md) for the full listing.

---

## 12. Knob behaviour

The rotary encoder on the macro pad generates three distinct events:

| Event | YAML key | Typical use |
|---|---|---|
| Rotate counter-clockwise | `ccw` | Scroll up / previous track / zoom out |
| Press (click) | `press` | Play/Pause / confirm / toggle |
| Rotate clockwise | `cw` | Scroll down / next track / zoom in |

Each rotation step sends one key event. Faster rotation sends more events in quick succession — useful for `volumeup`/`volumedown` or `wheel()` actions.

The `wheel(n)` action sends a mouse scroll event of `n` ticks. Use negative values for "up" and positive for "down" (matches macOS natural scrolling direction when reversed scrolling is off).

Pads with multiple knobs list each knob as a separate entry in the `knobs` array, in physical order from left to right (or top to bottom, depending on orientation).

---

## 13. Restoring and backing up presets

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
