#!/usr/bin/env python3
"""
Macro Pad Studio

A modern desktop manager for the CH57x 3-key + 1-knob macro pad. It lets you
browse ready-made presets, apply them to the device with the native macOS
admin dialog, and create or edit your own presets with a built-in shortcut
recorder.

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

# Local module that converts key events into ch57x tokens.
sys.path.insert(0, APP_DIR)
from keymap import event_to_token, VALID_TOKEN_KEYS, MODIFIER_TOKENS  # noqa: E402

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
    """Return an ordered, de-duplicated list of tokens for the dropdowns."""
    choices = []
    seen = set()
    for group in (COMMON_TOKENS, VALID_TOKEN_KEYS):
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
    return choices


TOKEN_CHOICES = build_token_choices()


# ---------------------------------------------------------------------------
# Preset model helpers
# ---------------------------------------------------------------------------

def list_presets():
    """
    Recurse the presets directory and return a list of dicts:
        { "name", "category", "path" }
    sorted by category then name.
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
            items.append({"name": name, "category": category, "path": path})
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
    Read a preset YAML and extract the three button tokens and the knob
    ccw/press/cw tokens from the first layer. Returns a dict; missing values
    fall back to an empty string.
    """
    result = {
        "buttons": ["", "", ""],
        "ccw": "", "press": "", "cw": "",
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

    layers = data.get("layers") or []
    if not layers:
        return result
    layer = layers[0] or {}

    buttons = layer.get("buttons") or []
    flat = []
    for entry in buttons:
        if isinstance(entry, list):
            flat.extend(entry)
        else:
            flat.append(entry)
    for i in range(3):
        result["buttons"][i] = str(flat[i]) if i < len(flat) and flat[i] else ""

    knobs = layer.get("knobs") or []
    if knobs:
        knob = knobs[0] or {}
        if isinstance(knob, dict):
            result["ccw"] = str(knob.get("ccw", "") or "")
            result["press"] = str(knob.get("press", "") or "")
            result["cw"] = str(knob.get("cw", "") or "")
    return result


def build_yaml(buttons, ccw, press, cw):
    """Compose the YAML text for a 3-key + 1-knob single-layer preset."""
    def q(v):
        v = (v or "").strip()
        return '""' if not v else '"%s"' % v.replace('"', '\\"')

    lines = [
        "orientation: normal",
        "rows: 1",
        "columns: 3",
        "knobs: 1",
        "",
        "layers:",
        "  - buttons:",
        "      - [%s, %s, %s]" % (q(buttons[0]), q(buttons[1]), q(buttons[2])),
        "    knobs:",
        "      - ccw: %s" % q(ccw),
        "        press: %s" % q(press),
        "        cw: %s" % q(cw),
        "",
    ]
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

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._build_statusbar()

        self.refresh_presets()
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
            header, text="CH57x · 3 keys + 1 knob",
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

        ctk.CTkLabel(
            wrap, text="Edit preset",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 2))
        self.editor_subtitle = ctk.CTkLabel(
            wrap, text="Pick a token or record a shortcut for each control.",
            text_color=MUTED, font=ctk.CTkFont(size=13),
        )
        self.editor_subtitle.grid(row=1, column=0, sticky="w", padx=24, pady=(0, 12))

        # Name + category.
        meta = ctk.CTkFrame(wrap, fg_color="transparent")
        meta.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 10))
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

        # Buttons section.
        ctk.CTkLabel(
            wrap, text="Buttons", font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=3, column=0, sticky="w", padx=24, pady=(12, 2))

        self.btn_fields = []
        for i in range(3):
            f = EditorField(wrap, "Button %d" % (i + 1), self._begin_record)
            f.grid(row=4 + i, column=0, sticky="ew", padx=24)
            self.btn_fields.append(f)

        # Knob section.
        ctk.CTkLabel(
            wrap, text="Knob", font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=7, column=0, sticky="w", padx=24, pady=(14, 2))

        self.knob_ccw = EditorField(wrap, "Rotate CCW", self._begin_record)
        self.knob_ccw.grid(row=8, column=0, sticky="ew", padx=24)
        self.knob_press = EditorField(wrap, "Press", self._begin_record)
        self.knob_press.grid(row=9, column=0, sticky="ew", padx=24)
        self.knob_cw = EditorField(wrap, "Rotate CW", self._begin_record)
        self.knob_cw.grid(row=10, column=0, sticky="ew", padx=24)

        # Action buttons.
        actions = ctk.CTkFrame(wrap, fg_color="transparent")
        actions.grid(row=11, column=0, sticky="ew", padx=24, pady=(20, 22))
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
        self.status = ctk.CTkLabel(
            self, text="Ready.", anchor="w", height=30,
            fg_color="#0c0d12", text_color=MUTED,
            font=ctk.CTkFont(size=12), padx=16,
        )
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew")

    def set_status(self, text, kind="info"):
        color = {
            "info": MUTED, "ok": SUCCESS, "error": DANGER,
        }.get(kind, MUTED)
        self.status.configure(text=text, text_color=color)

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
            if q and q not in p["name"].lower() and q not in p["category"].lower():
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

        # Buttons section.
        ctk.CTkLabel(
            card, text="BUTTONS", text_color="#5d6473",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=1, column=0, sticky="w", padx=26, pady=(14, 2))
        for i in range(3):
            ActionRow(card, "Button %d" % (i + 1), info["buttons"][i]).grid(
                row=2 + i, column=0, sticky="ew", padx=26,
            )

        # Knob section.
        ctk.CTkLabel(
            card, text="KNOB", text_color="#5d6473",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=5, column=0, sticky="w", padx=26, pady=(16, 2))
        ActionRow(card, "Rotate CCW", info["ccw"]).grid(
            row=6, column=0, sticky="ew", padx=26)
        ActionRow(card, "Press", info["press"]).grid(
            row=7, column=0, sticky="ew", padx=26)
        ActionRow(card, "Rotate CW", info["cw"]).grid(
            row=8, column=0, sticky="ew", padx=26)

        # Apply button.
        apply_bar = ctk.CTkFrame(card, fg_color="transparent")
        apply_bar.grid(row=9, column=0, sticky="ew", padx=26, pady=(22, 24))
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
        self.set_status("Requesting admin password and uploading…", "info")
        self.apply_btn.configure(state="disabled", text="Uploading…")
        self.update_idletasks()
        ok, msg = apply_preset(self.selected["path"])
        self.apply_btn.configure(state="normal", text="⬆  Apply to device")
        if ok:
            self.set_status("✓ %s" % msg, "ok")
        else:
            self.set_status("✗ %s" % msg, "error")

    # -- editor ------------------------------------------------------------

    def _new_preset(self):
        self._editing_path = None
        self.selected = None
        self.name_var.set("")
        for f in self.btn_fields:
            f.set("")
        self.knob_ccw.set("")
        self.knob_press.set("")
        self.knob_cw.set("")
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
        for i, f in enumerate(self.btn_fields):
            f.set(info["buttons"][i])
        self.knob_ccw.set(info["ccw"])
        self.knob_press.set(info["press"])
        self.knob_cw.set(info["cw"])
        self.editor_subtitle.configure(
            text="Editing “%s”." % preset["name"])

    def _collect_editor(self):
        buttons = [f.get() for f in self.btn_fields]
        return buttons, self.knob_ccw.get(), self.knob_press.get(), \
            self.knob_cw.get()

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
        buttons, ccw, press, cw = self._collect_editor()
        text = build_yaml(buttons, ccw, press, cw)

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
