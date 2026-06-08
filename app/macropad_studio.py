#!/usr/bin/env python3
"""
Macro Pad Studio

A modern desktop manager for the CH57x family of macro pads. It supports every
device geometry (3x1 up to 5x3, with 0 to 3 knobs), three switchable layers,
key sequences with delays, mouse / media actions, and LED backlight control on
the LED-capable variants. It lets you browse ready-made presets, apply them to
the device with the native macOS admin dialog, and create or edit your own
presets with a built-in shortcut recorder.

Requirements: customtkinter, Pillow, pyyaml.
"""

import os
import sys
import shlex
import shutil
import subprocess
import tempfile

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(APP_DIR)
PRESETS_DIR = os.path.join(ROOT_DIR, "presets")
ASSET_IMAGE = os.path.join(ROOT_DIR, "assets", "macropad.jpg")
TOOL = os.path.expanduser("~/.cargo/bin/ch57x-keyboard-tool")

# ---------------------------------------------------------------------------
# Dependency guard: customtkinter must be present.
# ---------------------------------------------------------------------------

try:
    import customtkinter as ctk
    from tkinter import messagebox
except ImportError:
    # Fall back to a plain message so the user knows exactly what to do.
    msg = (
        "Macro Pad Studio needs the 'customtkinter' package.\n\n"
        "Install it with:\n\n    pip install customtkinter\n\n"
        "(Pillow and pyyaml are also required: "
        "pip install customtkinter pillow pyyaml)"
    )
    try:
        import tkinter as tk
        from tkinter import messagebox as mb
        root = tk.Tk()
        root.withdraw()
        mb.showerror("Missing dependency", msg)
        root.destroy()
    except Exception:
        print(msg, file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print(
        "Macro Pad Studio needs 'pyyaml'.\n\n    pip install pyyaml\n",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

# Local modules.
sys.path.insert(0, APP_DIR)
from keymap import (  # noqa: E402
    event_to_token,
    VALID_TOKEN_KEYS,
    MODIFIER_TOKENS,
    MOUSE_TOKENS,
    MEDIA_TOKENS,
    EXTENDED_VOCABULARY,
)
import devices  # noqa: E402

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"
SUCCESS = "#22c55e"
DANGER = "#ef4444"
DANGER_HOVER = "#dc2626"
CARD_BG = "#1e1f29"
PANEL_BG = "#16171f"
SIDEBAR_BG = "#101117"
MUTED = "#9aa0ac"

# A curated dropdown vocabulary: common shortcuts first, then the full list.
COMMON_TOKENS = [
    "cmd-c", "cmd-v", "cmd-x", "cmd-z", "cmd-shift-z", "cmd-s",
    "cmd-a", "cmd-f", "cmd-p", "cmd-n", "cmd-w", "cmd-t", "cmd-q",
    "cmd-tab", "cmd-space", "cmd-shift-4", "cmd-shift-3",
    "enter", "escape", "tab", "space", "backspace", "delete",
    "left", "right", "up", "down",
    "play", "mute", "volumeup", "volumedown", "next", "prev",
]


def build_token_choices():
    """Return an ordered, de-duplicated list of tokens for the dropdowns.

    Order: common shortcuts, then mouse / wheel actions, then media keys, then
    the full key vocabulary, then bare modifier prefixes and a delay example.
    """
    choices = []
    seen = set()
    for group in (COMMON_TOKENS, MOUSE_TOKENS, MEDIA_TOKENS,
                  EXTENDED_VOCABULARY, VALID_TOKEN_KEYS):
        for tok in group:
            if tok not in seen:
                seen.add(tok)
                choices.append(tok)
    # Show modifier names too, so users understand the building blocks.
    for mod in MODIFIER_TOKENS:
        label = mod + "-"
        if label not in seen:
            seen.add(label)
            choices.append(label)
    # A delay example so users discover the "<ms>" syntax from the dropdown.
    if "<100>" not in seen:
        choices.append("<100>")
    return choices


TOKEN_CHOICES = build_token_choices()

# Device dropdown labels, in profile order.
DEVICE_LABELS = [p["label"] for p in devices.DEVICE_PROFILES]


def _profile_for_label(label):
    """Return the device profile matching a dropdown label, or None."""
    for prof in devices.DEVICE_PROFILES:
        if prof["label"] == label:
            return prof
    return None


# ---------------------------------------------------------------------------
# Preset model helpers
# ---------------------------------------------------------------------------

def _search_blob(name, category, path):
    """
    Build a lowercase haystack for a preset: its name, category and every
    action token (button keys + knob ccw/press/cw across all layers). This
    lets the search box match by app/category AND by the actual shortcuts,
    e.g. "copy", "cmd-c" or "volumeup".
    """
    parts = [name.replace("-", " "), name, category]
    try:
        data = parse_preset(path)
        for layer in data.get("layers", []):
            for row in layer.get("buttons", []):
                parts.extend(str(t) for t in row)
            for kn in layer.get("knobs", []):
                if isinstance(kn, dict):
                    parts.extend(str(v) for v in kn.values())
    except Exception:
        pass
    return " ".join(parts).lower()


def list_presets():
    """
    Recurse the presets directory and return a list of dicts:
        { "name", "category", "path", "search" }
    sorted by category then name. "search" is a lowercase haystack used by
    the filter (name + category + every action token).
    """
    items = []
    if not os.path.isdir(PRESETS_DIR):
        return items
    for root, _dirs, files in os.walk(PRESETS_DIR):
        for fn in files:
            if not fn.lower().endswith((".yaml", ".yml")):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, PRESETS_DIR)
            parts = rel.split(os.sep)
            category = parts[0] if len(parts) > 1 else "uncategorized"
            name = os.path.splitext(fn)[0]
            items.append({
                "name": name, "category": category, "path": path,
                "search": _search_blob(name, category, path),
            })
    items.sort(key=lambda d: (d["category"], d["name"]))
    return items


def list_categories():
    """Return the sorted list of category subfolders under presets/."""
    if not os.path.isdir(PRESETS_DIR):
        return []
    cats = [
        d for d in os.listdir(PRESETS_DIR)
        if os.path.isdir(os.path.join(PRESETS_DIR, d)) and not d.startswith(".")
    ]
    return sorted(cats)


def parse_preset(path):
    """
    Read a preset YAML and return a generic device description:

        {
            "model":       str | None,
            "orientation": str,
            "rows":        int,
            "columns":     int,
            "knobs":       int,
            "layers": [
                {
                    "buttons": [[tok, tok, ...], ...],   # rows x columns grid
                    "knobs":   [{"ccw","press","cw"}, ...],
                },
                ...
            ],
            "raw":   original parsed dict,
            "error": str | None,
        }

    Backward compatible: an existing 3x1 single-layer preset (rows: 1,
    columns: 3, one layer) is read with rows=1, columns=3, knobs=1 and a
    single layer holding a 1x3 button grid plus one knob.

    Button entries are normalised to a rows x columns grid of strings.
    Sequences (commas) and delays ("<ms>") are kept verbatim as raw strings.
    """
    result = {
        "model": None,
        "orientation": "normal",
        "rows": 0, "columns": 0, "knobs": 0,
        "layers": [],
        "raw": None, "error": None,
    }
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        result["raw"] = data
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        return result

    if not isinstance(data, dict):
        result["error"] = "Unexpected YAML structure."
        return result

    geom = devices.geometry_of(data)
    result["model"] = data.get("model")
    result["orientation"] = str(data.get("orientation") or "normal")
    result["rows"] = geom["rows"]
    result["columns"] = geom["columns"]
    result["knobs"] = geom["knobs"]

    rows = result["rows"]
    cols = result["columns"]
    nknobs = result["knobs"]

    raw_layers = data.get("layers") or []
    for raw_layer in raw_layers:
        raw_layer = raw_layer or {}
        grid = _normalise_button_grid(
            raw_layer.get("buttons"), rows, cols)
        knob_list = _normalise_knobs(raw_layer.get("knobs"), nknobs)
        result["layers"].append({"buttons": grid, "knobs": knob_list})

    if not result["layers"]:
        # Empty preset: synthesise one blank layer so the editor has shape.
        result["layers"].append({
            "buttons": _blank_grid(rows, cols),
            "knobs": [{"ccw": "", "press": "", "cw": ""}
                      for _ in range(nknobs)],
        })

    return result


def _blank_grid(rows, cols):
    """Return an empty rows x columns grid of empty strings."""
    rows = max(rows, 0)
    cols = max(cols, 0)
    return [["" for _ in range(cols)] for _ in range(rows)]


def _normalise_button_grid(buttons, rows, cols):
    """
    Turn an arbitrary 'buttons' YAML value into a rows x columns grid of
    strings. Accepts either a list of row-lists, or a flat list (legacy 1x3
    presets that wrote a single inline list still flatten correctly).
    """
    grid = _blank_grid(rows, cols)
    if not isinstance(buttons, list):
        return grid

    # Detect whether this is already a grid (list of lists) or a flat list.
    nested = any(isinstance(r, list) for r in buttons)
    if nested:
        for r, row in enumerate(buttons):
            if r >= rows:
                break
            if not isinstance(row, list):
                row = [row]
            for c, val in enumerate(row):
                if c >= cols:
                    break
                grid[r][c] = "" if val is None else str(val)
    else:
        # Flat list: fill row-major.
        flat = ["" if v is None else str(v) for v in buttons]
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx < len(flat):
                    grid[r][c] = flat[idx]
                idx += 1
    return grid


def _normalise_knobs(knobs, nknobs):
    """Return a list of exactly nknobs {ccw,press,cw} dicts."""
    out = []
    src = knobs if isinstance(knobs, list) else []
    for i in range(max(nknobs, 0)):
        knob = src[i] if i < len(src) and isinstance(src[i], dict) else {}
        out.append({
            "ccw": str(knob.get("ccw", "") or ""),
            "press": str(knob.get("press", "") or ""),
            "cw": str(knob.get("cw", "") or ""),
        })
    return out


def _q(v):
    """Quote a token value for YAML, preserving commas / delays verbatim."""
    v = (v or "").strip()
    if not v:
        return '""'
    return '"%s"' % v.replace("\\", "\\\\").replace('"', '\\"')


def build_yaml(rows, columns, knobs, layers, orientation="normal",
               model="ch57x"):
    """
    Compose YAML text for an arbitrary geometry with N layers.

    Parameters:
        rows, columns, knobs : ints describing the geometry
        layers : list of dicts, each:
            {"buttons": rows x columns grid of token strings,
             "knobs":   list of {"ccw","press","cw"} dicts}
        orientation : one of normal|upsidedown|clockwise|counterclockwise
        model : device model string (default "ch57x")

    Sequences (comma-separated) and delays ("<ms>") inside the token strings
    are preserved verbatim. Quoting is kept safe for the YAML parser.
    """
    lines = []
    if model:
        lines.append("model: %s" % model)
    lines.append("orientation: %s" % (orientation or "normal"))
    lines.append("rows: %d" % rows)
    lines.append("columns: %d" % columns)
    lines.append("knobs: %d" % knobs)
    lines.append("")
    lines.append("layers:")

    for layer in layers:
        grid = layer.get("buttons") or _blank_grid(rows, columns)
        klist = layer.get("knobs") or []

        lines.append("  - buttons:")
        for r in range(rows):
            row = grid[r] if r < len(grid) else ["" for _ in range(columns)]
            cells = [_q(row[c] if c < len(row) else "")
                     for c in range(columns)]
            lines.append("      - [%s]" % ", ".join(cells))

        # The backend requires the 'knobs' field even when there are none.
        if knobs <= 0:
            lines.append("    knobs: []")
        else:
            lines.append("    knobs:")
            for i in range(knobs):
                knob = klist[i] if i < len(klist) else {}
                lines.append("      - ccw: %s" % _q(knob.get("ccw", "")))
                lines.append("        press: %s" % _q(knob.get("press", "")))
                lines.append("        cw: %s" % _q(knob.get("cw", "")))
    lines.append("")
    return "\n".join(lines)


def validate_yaml_text(text):
    """
    Validate YAML text by piping it to the ch57x validator.
    Returns (ok: bool, message: str).
    """
    if not os.path.exists(TOOL):
        return False, "ch57x-keyboard-tool not found at %s" % TOOL
    try:
        proc = subprocess.run(
            [TOOL, "validate"],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return False, "Validator error: %s" % exc
    out = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode == 0, out or "Validation finished."


def apply_preset(path):
    """
    Upload a preset to the device using the macOS admin password dialog.
    Returns (ok: bool, message: str).
    """
    if not os.path.exists(TOOL):
        return False, "ch57x-keyboard-tool not found at %s" % TOOL
    if not os.path.exists(path):
        return False, "Preset file not found."

    # Build the shell command safely, then escape it for AppleScript.
    shell_cmd = "%s upload < %s" % (shlex.quote(TOOL), shlex.quote(path))
    esc = shell_cmd.replace("\\", "\\\\").replace('"', '\\"')
    applescript = 'do shell script "%s" with administrator privileges' % esc

    try:
        proc = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:  # noqa: BLE001
        return False, "Upload error: %s" % exc

    if proc.returncode == 0:
        out = proc.stdout.strip()
        return True, out or "Uploaded to device successfully."

    err = (proc.stderr or proc.stdout or "").strip()
    if "User canceled" in err or "-128" in err:
        return False, "Upload canceled."
    return False, err or "Upload failed."


def apply_led(mode, color=None):
    """
    Set the LED backlight mode (and optional color) through the same macOS
    admin password dialog used by apply_preset. Returns (ok, message).

    mode  : off|backlight|shock|shock2|press
    color : red|orange|yellow|green|cyan|blue|purple|white (optional)
    """
    if not os.path.exists(TOOL):
        return False, "ch57x-keyboard-tool not found at %s" % TOOL

    args = [shlex.quote(TOOL), "led", shlex.quote(mode)]
    if color:
        args.append(shlex.quote(color))
    shell_cmd = " ".join(args)
    esc = shell_cmd.replace("\\", "\\\\").replace('"', '\\"')
    applescript = 'do shell script "%s" with administrator privileges' % esc

    try:
        proc = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        return False, "LED error: %s" % exc

    if proc.returncode == 0:
        out = proc.stdout.strip()
        return True, out or "LED updated."
    err = (proc.stderr or proc.stdout or "").strip()
    if "User canceled" in err or "-128" in err:
        return False, "LED change canceled."
    return False, err or "LED change failed."


# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------

class ActionRow(ctk.CTkFrame):
    """A read-only label + value pill used on the launcher card."""

    def __init__(self, master, label, value):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=label, width=120, anchor="w",
            text_color=MUTED, font=ctk.CTkFont(size=13),
        ).grid(row=0, column=0, padx=(0, 12), pady=6, sticky="w")

        shown = value if value else "—"
        pill = ctk.CTkLabel(
            self, text=shown, anchor="w",
            fg_color="#262838", corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            padx=14, pady=6,
        )
        pill.grid(row=0, column=1, pady=6, sticky="ew")


class EditorField(ctk.CTkFrame):
    """A labeled field with a token dropdown and a Record button."""

    def __init__(self, master, label, recorder):
        super().__init__(master, fg_color="transparent")
        self._recorder = recorder
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=label, width=110, anchor="w",
            text_color=MUTED, font=ctk.CTkFont(size=13),
        ).grid(row=0, column=0, padx=(0, 10), pady=6, sticky="w")

        self.var = ctk.StringVar(value="")
        self.combo = ctk.CTkComboBox(
            self, values=TOKEN_CHOICES, variable=self.var,
            height=34, corner_radius=8, border_width=1,
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
        )
        self.combo.grid(row=0, column=1, pady=6, sticky="ew")

        self.rec_btn = ctk.CTkButton(
            self, text="● Record", width=92, height=34, corner_radius=8,
            fg_color="#33364a", hover_color="#3e4258",
            command=self._start_record,
        )
        self.rec_btn.grid(row=0, column=2, padx=(10, 0), pady=6)

    def get(self):
        return self.var.get().strip()

    def set(self, value):
        self.var.set(value or "")

    def _start_record(self):
        self.rec_btn.configure(text="Press keys…", fg_color=ACCENT)
        self._recorder(self._on_recorded)

    def _on_recorded(self, token):
        if token:
            self.var.set(token)
        self.rec_btn.configure(text="● Record", fg_color="#33364a")


class MacroPadStudio(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Macro Pad Studio")
        self.geometry("1080x720")
        self.minsize(940, 620)
        self.configure(fg_color=PANEL_BG)

        self.presets = []
        self.selected = None
        self.mode = "launcher"  # or "editor"
        self._editing_path = None  # path being edited, None for new
        self._record_callback = None
        self._image_cache = {}

        # Editor model state.
        self._editor_rows = 1
        self._editor_cols = 3
        self._editor_knobs = 1
        self._editor_layer_count = 3
        self._editor_layers = []      # list of {"buttons":[[..]], "knobs":[..]}
        self._editor_active_layer = 0
        self._btn_field_widgets = []  # current layer button EditorFields
        self._knob_field_widgets = []  # current layer knob EditorFields
        self._detected_profile = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._build_statusbar()

        self.refresh_presets()
        self.refresh_device_status()
        self._show_launcher()

        # Global key listener used by the recorder.
        self.bind_all("<Key>", self._on_global_key, add="+")

    # -- image -------------------------------------------------------------

    def _load_image(self, size):
        if not _HAS_PIL or not os.path.exists(ASSET_IMAGE):
            return None
        key = size
        if key in self._image_cache:
            return self._image_cache[key]
        try:
            img = Image.open(ASSET_IMAGE)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
            self._image_cache[key] = ctk_img
            return ctk_img
        except Exception:  # noqa: BLE001
            return None

    # -- sidebar -----------------------------------------------------------

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, width=280, corner_radius=0, fg_color=SIDEBAR_BG,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(4, weight=1)

        # Header with product image.
        header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(18, 6))

        img = self._load_image((248, 150))
        if img is not None:
            ctk.CTkLabel(header, image=img, text="").pack()
        ctk.CTkLabel(
            header, text="Macro Pad Studio",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", pady=(10, 0))
        ctk.CTkLabel(
            header, text="CH57x macro pad manager",
            text_color=MUTED, font=ctk.CTkFont(size=12),
        ).pack(anchor="w")

        # Mode toggle.
        toggle = ctk.CTkSegmentedButton(
            self.sidebar, values=["Launcher", "Editor"],
            command=self._on_mode_change,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
        )
        toggle.set("Launcher")
        toggle.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 12))
        self.toggle = toggle

        # Search box.
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_list())
        search = ctk.CTkEntry(
            self.sidebar, placeholder_text="Search presets…",
            textvariable=self.search_var, height=36, corner_radius=10,
        )
        search.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))

        # Category filter.
        self.category_var = ctk.StringVar(value="All categories")
        self.category_menu = ctk.CTkOptionMenu(
            self.sidebar, variable=self.category_var,
            values=["All categories"], command=lambda _=None: self._render_list(),
            height=34, corner_radius=10,
            fg_color="#1c1d27", button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
        )
        self.category_menu.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))

        # Scrollable preset list.
        self.list_frame = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent", corner_radius=0,
        )
        self.list_frame.grid(row=4, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.list_frame.grid_columnconfigure(0, weight=1)

        # New preset button (visible in editor mode).
        self.new_btn = ctk.CTkButton(
            self.sidebar, text="＋  New preset", height=40, corner_radius=10,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._new_preset,
        )
        self.new_btn.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 16))

    # -- main area ---------------------------------------------------------

    def _build_main(self):
        self.main = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        # Launcher view.
        self.launcher_view = ctk.CTkScrollableFrame(
            self.main, fg_color="transparent",
        )
        self.launcher_view.grid_columnconfigure(0, weight=1)

        # Editor view.
        self.editor_view = ctk.CTkScrollableFrame(
            self.main, fg_color="transparent",
        )
        self.editor_view.grid_columnconfigure(0, weight=1)
        self._build_editor_view()

    def _build_editor_view(self):
        wrap = ctk.CTkFrame(self.editor_view, fg_color=CARD_BG, corner_radius=16)
        wrap.grid(row=0, column=0, sticky="ew", padx=30, pady=24)
        wrap.grid_columnconfigure(0, weight=1)
        self._editor_wrap = wrap

        ctk.CTkLabel(
            wrap, text="Edit preset",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 2))
        self.editor_subtitle = ctk.CTkLabel(
            wrap, text="Pick a token or record a shortcut for each control.",
            text_color=MUTED, font=ctk.CTkFont(size=13),
        )
        self.editor_subtitle.grid(row=1, column=0, sticky="w", padx=24, pady=(0, 4))

        ctk.CTkLabel(
            wrap,
            text="Tip: enter a sequence with commas and delays, "
                 "e.g.  a, b, <100>, cmd-c",
            text_color="#6b7280", font=ctk.CTkFont(size=12),
        ).grid(row=2, column=0, sticky="w", padx=24, pady=(0, 12))

        # Name + category + device profile + orientation.
        meta = ctk.CTkFrame(wrap, fg_color="transparent")
        meta.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 10))
        meta.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(meta, text="Name", width=110, anchor="w",
                     text_color=MUTED).grid(row=0, column=0, sticky="w", pady=6)
        self.name_var = ctk.StringVar()
        ctk.CTkEntry(
            meta, textvariable=self.name_var, height=34, corner_radius=8,
            placeholder_text="my-app",
        ).grid(row=0, column=1, sticky="ew", pady=6)

        ctk.CTkLabel(meta, text="Category", width=110, anchor="w",
                     text_color=MUTED).grid(row=1, column=0, sticky="w", pady=6)
        self.editor_category_var = ctk.StringVar(value="")
        self.editor_category_menu = ctk.CTkOptionMenu(
            meta, variable=self.editor_category_var, values=[""],
            height=34, corner_radius=8, fg_color="#1c1d27",
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
        )
        self.editor_category_menu.grid(row=1, column=1, sticky="ew", pady=6)

        ctk.CTkLabel(meta, text="Device", width=110, anchor="w",
                     text_color=MUTED).grid(row=2, column=0, sticky="w", pady=6)
        self.device_var = ctk.StringVar(value=DEVICE_LABELS[0])
        self.device_menu = ctk.CTkOptionMenu(
            meta, variable=self.device_var, values=DEVICE_LABELS,
            command=self._on_device_change,
            height=34, corner_radius=8, fg_color="#1c1d27",
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
        )
        self.device_menu.grid(row=2, column=1, sticky="ew", pady=6)

        ctk.CTkLabel(meta, text="Orientation", width=110, anchor="w",
                     text_color=MUTED).grid(row=3, column=0, sticky="w", pady=6)
        self.orientation_var = ctk.StringVar(value="normal")
        ctk.CTkOptionMenu(
            meta, variable=self.orientation_var,
            values=["normal", "upsidedown", "clockwise", "counterclockwise"],
            height=34, corner_radius=8, fg_color="#1c1d27",
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
        ).grid(row=3, column=1, sticky="ew", pady=6)

        # Custom geometry row (only shown for the "custom" profile).
        self.custom_geo = ctk.CTkFrame(wrap, fg_color="transparent")
        self.custom_geo.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 4))
        self.custom_geo.grid_columnconfigure((1, 3, 5), weight=1)
        ctk.CTkLabel(self.custom_geo, text="Rows", text_color=MUTED).grid(
            row=0, column=0, padx=(0, 6))
        self.custom_rows = ctk.CTkOptionMenu(
            self.custom_geo, values=[str(i) for i in range(1, 6)],
            command=lambda _=None: self._rebuild_grid(),
            width=70, height=30, fg_color="#1c1d27",
            button_color=ACCENT, button_hover_color=ACCENT_HOVER)
        self.custom_rows.set("3")
        self.custom_rows.grid(row=0, column=1, padx=(0, 14))
        ctk.CTkLabel(self.custom_geo, text="Columns", text_color=MUTED).grid(
            row=0, column=2, padx=(0, 6))
        self.custom_cols = ctk.CTkOptionMenu(
            self.custom_geo, values=[str(i) for i in range(1, 6)],
            command=lambda _=None: self._rebuild_grid(),
            width=70, height=30, fg_color="#1c1d27",
            button_color=ACCENT, button_hover_color=ACCENT_HOVER)
        self.custom_cols.set("3")
        self.custom_cols.grid(row=0, column=3, padx=(0, 14))
        ctk.CTkLabel(self.custom_geo, text="Knobs", text_color=MUTED).grid(
            row=0, column=4, padx=(0, 6))
        self.custom_knobs = ctk.CTkOptionMenu(
            self.custom_geo, values=[str(i) for i in range(0, 4)],
            command=lambda _=None: self._rebuild_grid(),
            width=70, height=30, fg_color="#1c1d27",
            button_color=ACCENT, button_hover_color=ACCENT_HOVER)
        self.custom_knobs.set("1")
        self.custom_knobs.grid(row=0, column=5)
        self.custom_geo.grid_remove()

        # Layer tabs.
        self.layer_tabs = ctk.CTkSegmentedButton(
            wrap, values=["Layer 1"], command=self._on_layer_change,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
        )
        self.layer_tabs.set("Layer 1")
        self.layer_tabs.grid(row=5, column=0, sticky="w", padx=24, pady=(8, 4))

        # Dynamic grid container (rebuilt on device / layer change).
        self.grid_container = ctk.CTkFrame(wrap, fg_color="transparent")
        self.grid_container.grid(row=6, column=0, sticky="ew", padx=24)
        self.grid_container.grid_columnconfigure(0, weight=1)

        # LED panel (shown only for LED-capable profiles).
        self.led_panel = ctk.CTkFrame(wrap, fg_color="#191b24",
                                      corner_radius=12)
        self.led_panel.grid(row=7, column=0, sticky="ew", padx=24, pady=(14, 4))
        self.led_panel.grid_columnconfigure((1, 3), weight=1)
        ctk.CTkLabel(
            self.led_panel, text="LED backlight",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(self.led_panel, text="Mode", text_color=MUTED).grid(
            row=1, column=0, sticky="w", padx=14, pady=8)
        self.led_mode_var = ctk.StringVar(value="backlight")
        ctk.CTkOptionMenu(
            self.led_panel, variable=self.led_mode_var,
            values=["off", "backlight", "shock", "shock2", "press"],
            height=32, fg_color="#1c1d27",
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
        ).grid(row=1, column=1, sticky="ew", padx=(0, 14), pady=8)
        ctk.CTkLabel(self.led_panel, text="Color", text_color=MUTED).grid(
            row=1, column=2, sticky="w", padx=14, pady=8)
        self.led_color_var = ctk.StringVar(value="blue")
        ctk.CTkOptionMenu(
            self.led_panel, variable=self.led_color_var,
            values=["red", "orange", "yellow", "green", "cyan", "blue",
                    "purple", "white"],
            height=32, fg_color="#1c1d27",
            button_color=ACCENT, button_hover_color=ACCENT_HOVER,
        ).grid(row=1, column=3, sticky="ew", padx=(0, 14), pady=8)
        ctk.CTkButton(
            self.led_panel, text="Apply LED", height=34, corner_radius=8,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._apply_led,
        ).grid(row=2, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 12))
        self.led_panel.grid_remove()

        # Action buttons.
        actions = ctk.CTkFrame(wrap, fg_color="transparent")
        actions.grid(row=8, column=0, sticky="ew", padx=24, pady=(20, 22))
        actions.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(
            actions, text="Save preset", height=42, width=150, corner_radius=10,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._save_preset,
        ).grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(
            actions, text="Duplicate", height=42, width=120, corner_radius=10,
            fg_color="#33364a", hover_color="#3e4258",
            command=self._duplicate_current,
        ).grid(row=0, column=1, padx=(0, 10))

        ctk.CTkButton(
            actions, text="Delete", height=42, width=110, corner_radius=10,
            fg_color=DANGER, hover_color=DANGER_HOVER,
            command=self._delete_current,
        ).grid(row=0, column=2)

    # -- statusbar ---------------------------------------------------------

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, fg_color="#0c0d12", corner_radius=0, height=30)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self.status = ctk.CTkLabel(
            bar, text="Ready.", anchor="w", height=30,
            fg_color="transparent", text_color=MUTED,
            font=ctk.CTkFont(size=12), padx=16,
        )
        self.status.grid(row=0, column=0, sticky="ew")

        self.device_status = ctk.CTkLabel(
            bar, text="No device", anchor="e", height=30,
            fg_color="transparent", text_color=MUTED,
            font=ctk.CTkFont(size=12), padx=16,
        )
        self.device_status.grid(row=0, column=1, sticky="e")

    def set_status(self, text, kind="info"):
        color = {
            "info": MUTED, "ok": SUCCESS, "error": DANGER,
            "warn": "#f59e0b",
        }.get(kind, MUTED)
        self.status.configure(text=text, text_color=color)

    def refresh_device_status(self):
        """Detect a connected device and update the status indicator."""
        try:
            prof = devices.detect_connected()
        except Exception:  # noqa: BLE001
            prof = None
        self._detected_profile = prof
        if prof is None:
            self.device_status.configure(text="No device", text_color=MUTED)
        else:
            pid = prof.get("product_id")
            pid_text = ("0x%04X" % pid) if isinstance(pid, int) else "—"
            self.device_status.configure(
                text="Connected: %s (%s)" % (prof["label"], pid_text),
                text_color=SUCCESS,
            )

    # -- data --------------------------------------------------------------

    def refresh_presets(self):
        self.presets = list_presets()
        cats = ["All categories"] + list_categories()
        self.category_menu.configure(values=cats)
        if self.category_var.get() not in cats:
            self.category_var.set("All categories")
        ed_cats = list_categories() or ["misc"]
        self.editor_category_menu.configure(values=ed_cats)
        if self.editor_category_var.get() not in ed_cats:
            self.editor_category_var.set(ed_cats[0])
        self._render_list()

    def _filtered_presets(self):
        q = self.search_var.get().strip().lower()
        cat = self.category_var.get()
        out = []
        for p in self.presets:
            if cat != "All categories" and p["category"] != cat:
                continue
            if q and q not in p.get("search", (p["name"] + " " + p["category"]).lower()):
                continue
            out.append(p)
        return out

    def _render_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()

        items = self._filtered_presets()
        if not items:
            ctk.CTkLabel(
                self.list_frame, text="No presets found.",
                text_color=MUTED,
            ).grid(row=0, column=0, padx=8, pady=12, sticky="w")
            return

        row = 0
        current_cat = None
        for p in items:
            if p["category"] != current_cat:
                current_cat = p["category"]
                ctk.CTkLabel(
                    self.list_frame, text=current_cat.upper(),
                    text_color="#5d6473",
                    font=ctk.CTkFont(size=11, weight="bold"),
                ).grid(row=row, column=0, sticky="w", padx=12, pady=(10, 2))
                row += 1

            is_sel = self.selected and self.selected["path"] == p["path"]
            btn = ctk.CTkButton(
                self.list_frame, text="  " + p["name"], anchor="w",
                height=34, corner_radius=8,
                fg_color=ACCENT if is_sel else "transparent",
                hover_color="#23252f" if not is_sel else ACCENT_HOVER,
                text_color="white" if is_sel else "#d4d7df",
                command=lambda pr=p: self._select_preset(pr),
            )
            btn.grid(row=row, column=0, sticky="ew", padx=6, pady=1)
            row += 1

    def _select_preset(self, preset):
        self.selected = preset
        self._render_list()
        if self.mode == "launcher":
            self._render_launcher_card()
        else:
            self._load_into_editor(preset)

    # -- mode switching ----------------------------------------------------

    def _on_mode_change(self, value):
        if value == "Launcher":
            self._show_launcher()
        else:
            self._show_editor()

    def _show_launcher(self):
        self.mode = "launcher"
        self.toggle.set("Launcher")
        self.editor_view.grid_forget()
        self.new_btn.grid_remove()
        self.launcher_view.grid(row=0, column=0, sticky="nsew")
        self._render_launcher_card()

    def _show_editor(self):
        self.mode = "editor"
        self.toggle.set("Editor")
        self.launcher_view.grid_forget()
        self.new_btn.grid()
        self.editor_view.grid(row=0, column=0, sticky="nsew")
        if self.selected:
            self._load_into_editor(self.selected)
        else:
            self._new_preset()

    # -- launcher card -----------------------------------------------------

    def _render_launcher_card(self):
        for child in self.launcher_view.winfo_children():
            child.destroy()

        if not self.selected:
            empty = ctk.CTkFrame(self.launcher_view, fg_color="transparent")
            empty.grid(row=0, column=0, pady=80)
            img = self._load_image((360, 218))
            if img is not None:
                ctk.CTkLabel(empty, image=img, text="").pack(pady=(0, 20))
            ctk.CTkLabel(
                empty, text="Select a preset to get started",
                font=ctk.CTkFont(size=18, weight="bold"),
            ).pack()
            ctk.CTkLabel(
                empty, text="Choose one from the list on the left, "
                "then apply it to your macro pad.",
                text_color=MUTED,
            ).pack(pady=(6, 0))
            return

        info = parse_preset(self.selected["path"])

        card = ctk.CTkFrame(self.launcher_view, fg_color=CARD_BG, corner_radius=16)
        card.grid(row=0, column=0, sticky="ew", padx=30, pady=24)
        card.grid_columnconfigure(0, weight=1)

        # Title row.
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=26, pady=(22, 4))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head, text=self.selected["name"],
            font=ctk.CTkFont(size=24, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            head, text=self.selected["category"].upper(),
            fg_color="#262838", corner_radius=8, text_color=ACCENT,
            font=ctk.CTkFont(size=11, weight="bold"), padx=10, pady=4,
        ).grid(row=0, column=1, sticky="e")

        if info["error"]:
            ctk.CTkLabel(
                card, text="Could not read preset: %s" % info["error"],
                text_color=DANGER,
            ).grid(row=1, column=0, sticky="w", padx=26, pady=(8, 18))
            return

        rows = info["rows"]
        cols = info["columns"]
        nknobs = info["knobs"]
        nlayers = len(info["layers"]) or 1

        # Geometry summary line.
        ctk.CTkLabel(
            card,
            text="%dx%d grid · %d knob%s · %d layer%s"
                 % (rows, cols, nknobs, "" if nknobs == 1 else "s",
                    nlayers, "" if nlayers == 1 else "s"),
            text_color=MUTED, font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, sticky="w", padx=26, pady=(2, 6))

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=2, column=0, sticky="ew", padx=26)
        body.grid_columnconfigure(0, weight=1)
        next_row = 0

        # Render each layer.
        for li, layer in enumerate(info["layers"]):
            if nlayers > 1:
                ctk.CTkLabel(
                    body, text="LAYER %d" % (li + 1), text_color=ACCENT,
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(row=next_row, column=0, sticky="w", pady=(10, 4))
                next_row += 1

            grid = layer.get("buttons") or []
            if rows and cols:
                ctk.CTkLabel(
                    body, text="BUTTONS", text_color="#5d6473",
                    font=ctk.CTkFont(size=11, weight="bold"),
                ).grid(row=next_row, column=0, sticky="w", pady=(6, 2))
                next_row += 1
                for r in range(rows):
                    for c in range(cols):
                        val = grid[r][c] if (r < len(grid)
                                             and c < len(grid[r])) else ""
                        label = ("Button R%dC%d" % (r + 1, c + 1)
                                 if cols > 1 else "Button %d" % (r + 1))
                        ActionRow(body, label, val).grid(
                            row=next_row, column=0, sticky="ew")
                        next_row += 1

            knob_list = layer.get("knobs") or []
            for ki in range(nknobs):
                knob = knob_list[ki] if ki < len(knob_list) else {}
                ctk.CTkLabel(
                    body,
                    text="KNOB %d" % (ki + 1) if nknobs > 1 else "KNOB",
                    text_color="#5d6473",
                    font=ctk.CTkFont(size=11, weight="bold"),
                ).grid(row=next_row, column=0, sticky="w", pady=(12, 2))
                next_row += 1
                ActionRow(body, "Rotate CCW", knob.get("ccw", "")).grid(
                    row=next_row, column=0, sticky="ew")
                next_row += 1
                ActionRow(body, "Press", knob.get("press", "")).grid(
                    row=next_row, column=0, sticky="ew")
                next_row += 1
                ActionRow(body, "Rotate CW", knob.get("cw", "")).grid(
                    row=next_row, column=0, sticky="ew")
                next_row += 1

        # Apply button.
        apply_bar = ctk.CTkFrame(card, fg_color="transparent")
        apply_bar.grid(row=3, column=0, sticky="ew", padx=26, pady=(22, 24))
        apply_bar.grid_columnconfigure(1, weight=1)

        self.apply_btn = ctk.CTkButton(
            apply_bar, text="⬆  Apply to device",
            height=48, width=220, corner_radius=12,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._apply_selected,
        )
        self.apply_btn.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            apply_bar, text="Edit", height=48, width=100, corner_radius=12,
            fg_color="#33364a", hover_color="#3e4258",
            command=lambda: (self._show_editor()),
        ).grid(row=0, column=2, sticky="e")

    def _apply_selected(self):
        if not self.selected:
            return
        # Non-blocking geometry mismatch warning.
        self.refresh_device_status()
        prof = self._detected_profile
        if prof is not None and prof.get("rows"):
            info = parse_preset(self.selected["path"])
            if (info["rows"] != prof["rows"]
                    or info["columns"] != prof["columns"]
                    or info["knobs"] != prof["knobs"]):
                self.set_status(
                    "⚠ Preset geometry (%dx%d, %d knobs) differs from device "
                    "%s — applying anyway…"
                    % (info["rows"], info["columns"], info["knobs"],
                       prof["label"]),
                    "warn")
                self.update_idletasks()
        self.set_status("Requesting admin password and uploading…", "info")
        self.apply_btn.configure(state="disabled", text="Uploading…")
        self.update_idletasks()
        ok, msg = apply_preset(self.selected["path"])
        self.apply_btn.configure(state="normal", text="⬆  Apply to device")
        if ok:
            self.set_status("✓ %s" % msg, "ok")
        else:
            self.set_status("✗ %s" % msg, "error")

    def _apply_led(self):
        mode = self.led_mode_var.get()
        color = self.led_color_var.get()
        # 'off' takes no color; 'white' is only valid with backlight.
        use_color = None if mode == "off" else color
        self.set_status("Setting LED mode…", "info")
        self.update_idletasks()
        ok, msg = apply_led(mode, use_color)
        if ok:
            self.set_status("✓ LED: %s" % (msg or mode), "ok")
        else:
            self.set_status("✗ %s" % msg, "error")

    # -- editor ------------------------------------------------------------

    def _set_geometry(self, rows, cols, knobs, layer_count):
        """Resize the in-memory editor model to a new geometry, keeping data."""
        self._editor_rows = rows
        self._editor_cols = cols
        self._editor_knobs = knobs
        self._editor_layer_count = layer_count
        new_layers = []
        for li in range(layer_count):
            old = (self._editor_layers[li]
                   if li < len(self._editor_layers) else {})
            old_grid = old.get("buttons") or []
            grid = _blank_grid(rows, cols)
            for r in range(rows):
                for c in range(cols):
                    if r < len(old_grid) and c < len(old_grid[r]):
                        grid[r][c] = old_grid[r][c]
            old_knobs = old.get("knobs") or []
            klist = []
            for ki in range(knobs):
                k = old_knobs[ki] if ki < len(old_knobs) else {}
                klist.append({
                    "ccw": k.get("ccw", ""),
                    "press": k.get("press", ""),
                    "cw": k.get("cw", ""),
                })
            new_layers.append({"buttons": grid, "knobs": klist})
        self._editor_layers = new_layers
        if self._editor_active_layer >= layer_count:
            self._editor_active_layer = 0

    def _apply_profile_to_editor(self, profile):
        """Set the device dropdown + geometry from a profile dict."""
        self.device_var.set(profile["label"])
        if profile["id"] == "custom":
            self.custom_geo.grid()
            rows = int(self.custom_rows.get())
            cols = int(self.custom_cols.get())
            knobs = int(self.custom_knobs.get())
        else:
            self.custom_geo.grid_remove()
            rows = profile["rows"]
            cols = profile["columns"]
            knobs = profile["knobs"]
            self.custom_rows.set(str(rows))
            self.custom_cols.set(str(cols))
            self.custom_knobs.set(str(knobs))
        self._set_geometry(rows, cols, knobs, profile.get("layers", 3))
        # LED panel visibility.
        if profile.get("led"):
            self.led_panel.grid()
        else:
            self.led_panel.grid_remove()

    def _on_device_change(self, label):
        prof = _profile_for_label(label) or devices.DEVICE_PROFILES[0]
        self._apply_profile_to_editor(prof)
        self._refresh_layer_tabs()
        self._rebuild_grid()

    def _refresh_layer_tabs(self):
        labels = ["Layer %d" % (i + 1)
                  for i in range(self._editor_layer_count)]
        self.layer_tabs.configure(values=labels)
        self.layer_tabs.set(labels[self._editor_active_layer])

    def _on_layer_change(self, label):
        self._save_current_layer_from_fields()
        try:
            idx = int(label.split()[-1]) - 1
        except (ValueError, IndexError):
            idx = 0
        self._editor_active_layer = idx
        self._rebuild_grid()

    def _rebuild_grid(self):
        """Rebuild the dynamic button + knob fields for the active layer."""
        # If the custom geometry changed, resize the model first.
        if self.custom_geo.winfo_manager():  # custom row visible
            rows = int(self.custom_rows.get())
            cols = int(self.custom_cols.get())
            knobs = int(self.custom_knobs.get())
            if (rows, cols, knobs) != (self._editor_rows, self._editor_cols,
                                       self._editor_knobs):
                self._set_geometry(rows, cols, knobs,
                                   self._editor_layer_count)

        for child in self.grid_container.winfo_children():
            child.destroy()
        self._btn_field_widgets = []
        self._knob_field_widgets = []

        rows = self._editor_rows
        cols = self._editor_cols
        knobs = self._editor_knobs
        li = self._editor_active_layer
        layer = (self._editor_layers[li]
                 if li < len(self._editor_layers) else {})
        grid = layer.get("buttons") or _blank_grid(rows, cols)
        klist = layer.get("knobs") or []

        next_row = 0
        if rows and cols:
            ctk.CTkLabel(
                self.grid_container, text="Buttons",
                font=ctk.CTkFont(size=15, weight="bold"),
            ).grid(row=next_row, column=0, sticky="w", pady=(8, 2))
            next_row += 1
            for r in range(rows):
                row_widgets = []
                for c in range(cols):
                    label = ("R%dC%d" % (r + 1, c + 1)
                             if cols > 1 else "Button %d" % (r + 1))
                    f = EditorField(self.grid_container, label,
                                    self._begin_record)
                    f.grid(row=next_row, column=0, sticky="ew")
                    val = grid[r][c] if (r < len(grid)
                                         and c < len(grid[r])) else ""
                    f.set(val)
                    row_widgets.append(f)
                    next_row += 1
                self._btn_field_widgets.append(row_widgets)

        for ki in range(knobs):
            knob = klist[ki] if ki < len(klist) else {}
            ctk.CTkLabel(
                self.grid_container,
                text="Knob %d" % (ki + 1) if knobs > 1 else "Knob",
                font=ctk.CTkFont(size=15, weight="bold"),
            ).grid(row=next_row, column=0, sticky="w", pady=(14, 2))
            next_row += 1
            ccw = EditorField(self.grid_container, "Rotate CCW",
                              self._begin_record)
            ccw.grid(row=next_row, column=0, sticky="ew")
            ccw.set(knob.get("ccw", ""))
            next_row += 1
            press = EditorField(self.grid_container, "Press",
                                self._begin_record)
            press.grid(row=next_row, column=0, sticky="ew")
            press.set(knob.get("press", ""))
            next_row += 1
            cw = EditorField(self.grid_container, "Rotate CW",
                             self._begin_record)
            cw.grid(row=next_row, column=0, sticky="ew")
            cw.set(knob.get("cw", ""))
            next_row += 1
            self._knob_field_widgets.append(
                {"ccw": ccw, "press": press, "cw": cw})

    def _save_current_layer_from_fields(self):
        """Copy the visible fields back into the in-memory layer model."""
        li = self._editor_active_layer
        if li >= len(self._editor_layers):
            return
        grid = _blank_grid(self._editor_rows, self._editor_cols)
        for r, row_widgets in enumerate(self._btn_field_widgets):
            for c, widget in enumerate(row_widgets):
                if r < len(grid) and c < len(grid[r]):
                    grid[r][c] = widget.get()
        klist = []
        for kw in self._knob_field_widgets:
            klist.append({
                "ccw": kw["ccw"].get(),
                "press": kw["press"].get(),
                "cw": kw["cw"].get(),
            })
        self._editor_layers[li] = {"buttons": grid, "knobs": klist}

    def _new_preset(self):
        self._editing_path = None
        self.selected = None
        self.name_var.set("")
        self.orientation_var.set("normal")
        self._editor_active_layer = 0
        self._editor_layers = []
        self._apply_profile_to_editor(devices.DEVICE_PROFILES[0])
        self._refresh_layer_tabs()
        self._rebuild_grid()
        self.editor_subtitle.configure(
            text="Creating a new preset. Pick tokens or record shortcuts.")
        cats = list_categories() or ["misc"]
        if self.editor_category_var.get() not in cats:
            self.editor_category_var.set(cats[0])
        self._render_list()
        self.set_status("New preset.", "info")

    def _load_into_editor(self, preset):
        info = parse_preset(preset["path"])
        self._editing_path = preset["path"]
        self.name_var.set(preset["name"])
        self.editor_category_var.set(preset["category"])
        self.orientation_var.set(info.get("orientation") or "normal")

        rows = info["rows"]
        cols = info["columns"]
        knobs = info["knobs"]
        layer_count = len(info["layers"]) or 1

        # Pick the matching profile, falling back to custom geometry.
        prof = None
        for p in devices.DEVICE_PROFILES:
            if p["id"] == "custom":
                continue
            if (p["rows"] == rows and p["columns"] == cols
                    and p["knobs"] == knobs):
                prof = p
                break
        if prof is None:
            prof = devices.profile_by_id("custom")
            self.device_var.set(prof["label"])
            self.custom_geo.grid()
            self.custom_rows.set(str(rows))
            self.custom_cols.set(str(cols))
            self.custom_knobs.set(str(knobs))
            if prof.get("led"):
                self.led_panel.grid()
            else:
                self.led_panel.grid_remove()
        else:
            self._apply_profile_to_editor(prof)

        # Load the actual layer data into the model.
        self._editor_active_layer = 0
        self._set_geometry(rows, cols, knobs, max(layer_count, 1))
        for li, layer in enumerate(info["layers"]):
            if li >= len(self._editor_layers):
                break
            self._editor_layers[li] = {
                "buttons": layer.get("buttons") or _blank_grid(rows, cols),
                "knobs": layer.get("knobs") or [],
            }
        self._refresh_layer_tabs()
        self._rebuild_grid()
        self.editor_subtitle.configure(
            text="Editing “%s”." % preset["name"])

    def _save_preset(self):
        name = self.name_var.get().strip()
        if not name:
            self.set_status("Please enter a preset name.", "error")
            return
        # Sanitize file name.
        safe = "".join(
            c if (c.isalnum() or c in "-_") else "-" for c in name.lower()
        ).strip("-") or "preset"

        category = self.editor_category_var.get().strip() or "misc"

        # Persist the visible layer, then build YAML from the whole model.
        self._save_current_layer_from_fields()
        text = build_yaml(
            self._editor_rows, self._editor_cols, self._editor_knobs,
            self._editor_layers,
            orientation=self.orientation_var.get() or "normal",
        )

        # Validate before writing anything to the presets tree.
        ok, msg = validate_yaml_text(text)
        if not ok:
            self.set_status("✗ Validation failed: %s" % msg, "error")
            messagebox.showerror("Validation failed", msg)
            return

        cat_dir = os.path.join(PRESETS_DIR, category)
        os.makedirs(cat_dir, exist_ok=True)
        dest = os.path.join(cat_dir, safe + ".yaml")

        # If renaming/moving, remove the old file afterwards.
        old = self._editing_path

        try:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(text)
        except Exception as exc:  # noqa: BLE001
            self.set_status("✗ Could not write file: %s" % exc, "error")
            return

        if old and os.path.abspath(old) != os.path.abspath(dest) \
                and os.path.exists(old):
            try:
                os.remove(old)
            except Exception:  # noqa: BLE001
                pass

        self._editing_path = dest
        self.refresh_presets()
        # Reselect the saved preset.
        for p in self.presets:
            if os.path.abspath(p["path"]) == os.path.abspath(dest):
                self.selected = p
                break
        self._render_list()
        self.set_status("✓ Saved and validated: %s" % dest, "ok")

    def _duplicate_current(self):
        if not self._editing_path and not self.selected:
            self.set_status("Nothing to duplicate.", "error")
            return
        base = self.name_var.get().strip() or "preset"
        self.name_var.set(base + "-copy")
        self._editing_path = None
        self.set_status(
            "Duplicated. Adjust the name and click Save.", "info")

    def _delete_current(self):
        path = self._editing_path
        if not path or not os.path.exists(path):
            self.set_status("No saved preset to delete.", "error")
            return
        if not messagebox.askyesno(
                "Delete preset",
                "Delete this preset permanently?\n\n%s" % os.path.basename(path)):
            return
        try:
            os.remove(path)
        except Exception as exc:  # noqa: BLE001
            self.set_status("✗ Could not delete: %s" % exc, "error")
            return
        self._editing_path = None
        self.selected = None
        self.refresh_presets()
        self._new_preset()
        self.set_status("✓ Preset deleted.", "ok")

    # -- recorder ----------------------------------------------------------

    def _begin_record(self, callback):
        """Arm the recorder; the next key event will be captured."""
        self._record_callback = callback
        self.set_status("Recording… press a key combination.", "info")

    def _on_global_key(self, event):
        if self._record_callback is None:
            return
        token = event_to_token(event)
        if token is None:
            # Only modifiers so far; keep waiting for the main key.
            return
        cb = self._record_callback
        self._record_callback = None
        cb(token)
        self.set_status("Recorded: %s" % token, "ok")
        return "break"


def main():
    # A friendly notice if the device tool is missing (non-fatal).
    if not os.path.exists(TOOL):
        print("Note: ch57x-keyboard-tool not found at %s. "
              "Apply/validate will not work until it is installed."
              % TOOL, file=sys.stderr)
    app = MacroPadStudio()
    app.mainloop()


if __name__ == "__main__":
    main()
