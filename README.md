# MacroPad Studio

**macOS configuration manager for CH57x USB macro pads — 3-key up to 12-key with rotary knobs**

<img src="assets/macropad.jpg" alt="CH57x macro pad with rotary knob" width="400">

> **The hardware:** these are the popular, inexpensive **mechanical macro keypads with rotary knobs** widely sold on **AliExpress, Amazon, eBay, Temu and Banggood** (often listed as *"3 Key Custom Keyboard RGB Macro Pad"*, *"Mini Programmable Knob Keyboard"*, *"OSU! Macro Pad"* or *"DIY Hot-swap Keypad"*). They use a **CH57x** chip and the bundled software is **Windows-only** — this project lets you configure them natively on **macOS**.

---

## What it does

This project gives macOS users full control over compact USB macro pads based on the CH57x chip. The devices ship with a Windows-only configuration utility. This repository provides:

- A library of **394 ready-to-use YAML presets** covering apps from video editors to DAWs, browsers, coding tools, photo editors, and more — including dedicated multi-key presets for larger pad geometries.
- A **CustomTkinter GUI** (`app/macropad_studio.py`) that lets you browse, edit, record key bindings, and upload presets — no terminal required. Features a **device selector**, **layer tabs**, and an **LED control panel**.
- Shell **helper scripts** for installation, verification, and one-command uploads.

---

## Supported devices

All variants share VID `0x1189`. The tool auto-detects the connected device and selects the matching profile.

| Geometry | Buttons | Knobs | Product ID (PID) | LED |
|---|---|---|---|---|
| 3×1 | 3 | 1 | `0x8890` | RGB per-key |
| 3×2 | 6 | 1 | `0x8890` | RGB per-key |
| 3×3 | 9 | 2 | `0x8890` | RGB per-key |
| 4×1 | 4 | 1 | `0x8840` | RGB per-key |
| 4×3 | 12 | 3 | `0x8840` | RGB per-key |
| 5×3 | 15 | 3 | `0x8842` | RGB per-key |
| 12-key (alt) | 12 | 3 | `0x8842` | RGB per-key |

> **Not a QMK/VIA device.** Do not attempt to flash VIA firmware. The CH57x chip uses a proprietary HID protocol implemented by `ch57x-keyboard-tool`.

### Advanced features (v2)

| Feature | Details |
|---|---|
| **3 layers** | Each preset can define up to 3 independent layers, switchable from the pad or GUI |
| **Key sequences** | Chain actions with commas: `cmd-shift-n,<200>,enter` (the `<N>` syntax inserts a millisecond delay) |
| **Mouse actions** | `wheel(3)` / `wheel(-3)` for scroll; `wheelup` / `wheeldown` aliases |
| **LED control** | Set per-key colour, brightness, and effect mode (static, breathing, reactive) via the GUI LED panel |
| **Device auto-detection** | The GUI scans USB on launch and pre-selects the detected PID/geometry |

---

## How the tool integration works

Presets are plain **YAML files** that describe what each button and knob (counter-clockwise / press / clockwise) should send.

```
presets/
  video/
    final-cut-pro.yaml       ← one preset per app / workflow
  dev/
    vscode-edit.yaml
  examples-multikey/
    9key-3x3-2knob/
      vscode.yaml            ← multi-layer preset for 9-key pad
    12key-4x3-3knob/
      photoshop.yaml
  ...
```

Uploading a preset is a one-liner that pipes the YAML into `ch57x-keyboard-tool`, an open-source Rust CLI that speaks the device's USB HID protocol and writes the key mappings directly into the firmware:

```bash
sudo ~/.cargo/bin/ch57x-keyboard-tool upload < presets/video/final-cut-pro.yaml
```

`sudo` is required because macOS restricts raw USB HID access to root.

The GUI wraps that same command behind a native macOS administrator-password dialog (via `osascript`), so you never have to open a terminal. It also provides a live **key recorder** — press any key combination on your keyboard and the GUI captures it in the correct token format.

---

## Quickstart

### 1. Install dependencies

```bash
bash scripts/install.sh
```

This installs `libusb` via Homebrew, `ch57x-keyboard-tool` via Cargo, and the Python packages needed by the GUI. It also runs a self-check at the end.

> **Rust required.** If Cargo is not found, the script will print the one-liner to install Rust via `rustup`. Re-run `install.sh` after Rust is set up.

### 2. Plug in the macro pad

Use a **data-capable USB cable** (charge-only cables are the most common cause of "device not detected" — see [docs/GUIDE.md](docs/GUIDE.md)).

### 3. Open the GUI

```bash
python3 app/macropad_studio.py
```

---

## GUI features

| Feature | Description |
|---|---|
| **Device selector** | Drop-down on launch — pick your pad geometry (3×1, 3×3, 4×3, etc.) or let auto-detection fill it in |
| **Launcher** | Browse all preset categories and upload with one click |
| **Editor** | Edit button and knob bindings for any preset in a visual form |
| **Layer tabs** | Switch between Layer 1, 2, and 3 to edit multi-layer presets |
| **Key recorder** | Press any shortcut on your keyboard — it is captured and normalised automatically |
| **LED panel** | Set per-key colour, global brightness, and effect mode without touching a YAML file |

---

## CLI usage

Upload a preset directly from the terminal:

```bash
# By path
sudo ~/.cargo/bin/ch57x-keyboard-tool upload < presets/dev/vscode-edit.yaml

# Using the helper script (finds the file by name, handles sudo)
bash scripts/upload.sh vscode-edit
```

Validate all presets (dry-run, no device needed):

```bash
bash scripts/verify.sh
```

---

## Preset categories

| Category | Presets | Example apps |
|---|---|---|
| `3d-cad` | 20 | Blender, AutoCAD, Fusion 360, Maya, ZBrush |
| `audio-daw` | 56 | Logic Pro, Ableton, Pro Tools, Reaper, GarageBand |
| `browser` | 21 | Chrome, Safari, Firefox, Arc, Brave |
| `communication` | 20 | Zoom, Slack, Teams, Discord, FaceTime |
| `design` | 27 | Figma, Photoshop, Illustrator, Sketch, Canva |
| `dev` | 38 | VS Code (7 modes), Xcode, Neovim, Cursor, iTerm |
| `examples-multikey` | 12 | Multi-layout examples for 6-, 9-, and 12-key pads |
| `music-notation` | 5 | Dorico, Sibelius, Finale, MuseScore |
| `office` | 30 | Word, Excel, Keynote, Notion, Obsidian, Pages |
| `photo` | 55 | Lightroom, Capture One, Darktable, GIMP, Affinity Photo |
| `reading-pdf` | 6 | Preview, Skim, Adobe Acrobat, Apple Books |
| `streaming` | 7 | OBS Studio, Ecamm Live, Streamlabs, Twitch |
| `system-macos` | 30 | Screenshots, Mission Control, Media, Finder, Spotlight |
| `utility` | 10 | Clipboard, Emoji, Window snapping, 1Password |
| `video` | 57 | Final Cut Pro, DaVinci Resolve (6 modes), Premiere Pro, After Effects |

Full binding details for every preset: [docs/PRESETS.md](docs/PRESETS.md)

---

## Documentation

- [docs/GUIDE.md](docs/GUIDE.md) — hardware identification, install walkthrough, YAML editing reference, layers, key sequences, mouse actions, LED control, knob behaviour, troubleshooting
- [docs/PRESETS.md](docs/PRESETS.md) — complete binding tables for all presets, generated from the YAML files
- [CHANGELOG.md](CHANGELOG.md) — version history

---

## Credits

- **[ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool)** by kriomant — the open-source Rust CLI that makes USB communication possible on macOS and Linux.
- **[libusb](https://libusb.info/)** — low-level USB library, installed via Homebrew.

---

## License

MIT — see [LICENSE](LICENSE).  
Author: Fabio Dal Ez
