# Changelog

All notable changes to this project are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0] — 2026

### Added

- **Multi-device geometry support** — presets and the GUI now handle 3×1, 3×2, 3×3, 4×1, 4×3, 5×3, and 12-key pad variants (VID `0x1189`; PID `0x8890` / `0x8840` / `0x8842`). The `rows`, `columns`, and `knobs` fields in YAML control the layout.
- **3-layer presets** — the `layers` list now supports up to 3 independent layers per preset; the GUI adds Layer 1 / Layer 2 / Layer 3 tabs in the Editor.
- **Key sequences with delays** — any key slot now accepts a comma-separated sequence of actions, with optional millisecond delays using the `<N>` syntax (e.g. `cmd-shift-n,<200>,enter`).
- **Mouse actions** — `wheel(N)` / `wheel(-N)` and `wheelup` / `wheeldown` aliases are supported in all key and knob slots.
- **LED control** — per-key RGB colour, global brightness slider, and effect mode selection (Static / Breathing / Reactive) via a dedicated LED panel in the GUI. LED settings can also be embedded in YAML under the `led:` key.
- **Device auto-detection** — the GUI scans connected USB devices on launch and pre-selects the matching pad profile. A device selector drop-down allows manual override.
- **Multi-key example presets** — 12 new presets in `presets/examples-multikey/` demonstrating 6-key (3×2 + 1 knob), 9-key (3×3 + 2 knobs), and 12-key (4×3 + 3 knobs) layouts for popular apps including VS Code, OBS Studio, Logic Pro, DaVinci Resolve, Ableton Live, Premiere Pro, and Photoshop.
- **Massively expanded preset library** — many context-specific presets per important app (e.g. Photoshop: layers, masking, retouch, painting, selection, transform, pen, camera-raw…; DaVinci, Lightroom, Logic, Ableton, Premiere, and more), bringing the library to **394 validated presets**.
- **Action-aware search** — the Launcher search box now matches by app name, category, and the actual shortcut tokens (e.g. `copy`, `cmd-c`, `volumeup`, `wheelup`).
- **GUI screenshot** in the README.

### Changed

- GUI window now opens with a device selector at the top.
- **Shortcut accuracy pass** — verified and corrected the default macOS shortcuts across DaVinci Resolve, Logic Pro, Photoshop, Lightroom Classic, Premiere Pro, After Effects, Ableton Live, and Final Cut Pro presets.
- `docs/GUIDE.md` expanded with sections on device profiles, layers, sequences, mouse actions, LED control, and larger pads.
- `docs/PRESETS.md` regenerated from all 394 YAML files; multi-key presets listed in a dedicated section.
- `README.md` updated with supported-devices table, advanced features summary, and a GUI screenshot.

---

## [1.0.0] — 2026

### Added

- Initial release targeting the classic **3-key + 1-knob** CH57x pad (PID `0x8890`).
- **181 YAML presets** across 14 categories: 3D/CAD, Audio/DAW, Browsers, Communication, Design, Development, Music Notation, Office, Photo, Reading/PDF, Streaming, macOS System, Utility, and Video.
- **CustomTkinter GUI** (`app/macropad_studio.py`) with Launcher, Editor, and Key Recorder.
- Shell scripts: `scripts/install.sh`, `scripts/upload.sh`, `scripts/verify.sh`.
- Documentation: `docs/GUIDE.md` (install walkthrough, YAML reference, knob behaviour, troubleshooting) and `docs/PRESETS.md` (full binding tables).
- MIT licence.
