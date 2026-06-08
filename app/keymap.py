"""
keymap.py

Translate Tkinter key events into ch57x-keyboard-tool tokens.

The ch57x tool expects shortcuts written as modifier-modifier-key, for
example: "cmd-shift-z" or "cmd-s". This module captures a single key event
from Tkinter and converts the active modifiers plus the main key into a
valid ch57x token string.

Public API:
    event_to_token(event) -> str | None
        Convert a Tkinter key event into a ch57x token. Returns None if the
        event only carried modifier keys (so the caller can keep waiting for
        the real key to land).

    VALID_TOKEN_KEYS, MODIFIER_TOKENS
        The full vocabulary lists, useful for building dropdowns.
"""

# Modifier order used when assembling a token. macOS-friendly ordering:
# cmd first, then ctrl, then alt/opt, then shift. The ch57x validator does
# not require a specific order, but a stable order keeps output tidy.
_MODIFIER_ORDER = ["cmd", "ctrl", "alt", "shift"]

MODIFIER_TOKENS = [
    "ctrl", "shift", "alt", "opt", "cmd", "win",
    "rctrl", "rshift", "ralt", "ropt", "rcmd", "rwin",
]

# Full single-key vocabulary accepted by the validator (no modifiers here).
VALID_TOKEN_KEYS = (
    list("abcdefghijklmnopqrstuvwxyz")
    + [str(d) for d in range(10)]
    + [
        "enter", "escape", "backspace", "tab", "space",
        "minus", "equal", "leftbracket", "rightbracket", "backslash",
        "nonushash", "semicolon", "quote", "grave", "comma", "dot",
        "slash", "capslock",
    ]
    + [f"f{i}" for i in range(1, 25)]
    + [
        "printscreen", "macbrightnessdown", "macbrightnessup",
        "insert", "home", "pageup", "delete", "end", "pagedown",
        "right", "left", "down", "up",
        "numlock", "numpadslash", "numpadasterisk", "numpadminus",
        "numpadplus", "numpadenter",
    ]
    + [f"numpad{i}" for i in range(10)]
    + ["numpaddot", "numpadequal", "nonusbackslash", "application", "power"]
    + [
        "next", "previous", "prev", "stop", "play", "mute",
        "volumeup", "volumedown", "favorites", "calculator", "screenlock",
    ]
)

# Map Tkinter keysym names onto ch57x key tokens for keys whose names differ.
_KEYSYM_MAP = {
    "Return": "enter",
    "KP_Enter": "numpadenter",
    "Escape": "escape",
    "BackSpace": "backspace",
    "Tab": "tab",
    "ISO_Left_Tab": "tab",
    "space": "space",
    "minus": "minus",
    "underscore": "minus",
    "plus": "equal",
    "equal": "equal",
    "bracketleft": "leftbracket",
    "braceleft": "leftbracket",
    "bracketright": "rightbracket",
    "braceright": "rightbracket",
    "backslash": "backslash",
    "bar": "backslash",
    "semicolon": "semicolon",
    "colon": "semicolon",
    "apostrophe": "quote",
    "quotedbl": "quote",
    "quoteright": "quote",
    "grave": "grave",
    "quoteleft": "grave",
    "asciitilde": "grave",
    "comma": "comma",
    "less": "comma",
    "period": "dot",
    "greater": "dot",
    "slash": "slash",
    "question": "slash",
    "Caps_Lock": "capslock",
    "Insert": "insert",
    "Home": "home",
    "Prior": "pageup",      # Page Up
    "Delete": "delete",
    "End": "end",
    "Next": "pagedown",     # Page Down
    "Right": "right",
    "Left": "left",
    "Down": "down",
    "Up": "up",
    "Num_Lock": "numlock",
    "KP_Divide": "numpadslash",
    "KP_Multiply": "numpadasterisk",
    "KP_Subtract": "numpadminus",
    "KP_Add": "numpadplus",
    "KP_Decimal": "numpaddot",
    "KP_Delete": "numpaddot",
    "KP_Equal": "numpadequal",
    "Print": "printscreen",
}

# Numeric digits from the punctuation symbols typed with Shift.
_SHIFTED_DIGITS = {
    "exclam": "1", "at": "2", "numbersign": "3", "dollar": "4",
    "percent": "5", "asciicircum": "6", "ampersand": "7",
    "asterisk": "8", "parenleft": "9", "parenright": "0",
}

# Keysyms that are purely modifier presses; ignore them on their own.
_MODIFIER_KEYSYMS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R",
    "Alt_L", "Alt_R", "Meta_L", "Meta_R",
    "Super_L", "Super_R", "Hyper_L", "Hyper_R",
    "Caps_Lock", "Mode_switch", "ISO_Level3_Shift",
}

# Tkinter event.state bit masks.
_STATE_SHIFT = 0x0001
_STATE_CONTROL = 0x0004
# On macOS Tk: Command -> Mod1 (0x0008 / 0x0010 depending on build),
# Option/Alt -> Mod2 area. We check several bits to be robust across builds.
_STATE_COMMAND_BITS = (0x0008, 0x0010, 0x0040)  # Command / Cmd
_STATE_OPTION_BITS = (0x0080, 0x2000, 0x0010)   # Option / Alt


def _keypad_digit(keysym):
    """Return numpad token for KP_0..KP_9 keysyms, else None."""
    if keysym.startswith("KP_") and keysym[3:].isdigit():
        return "numpad" + keysym[3:]
    return None


def normalize_keysym(keysym):
    """
    Convert a single Tkinter keysym into its ch57x base-key token.

    Returns the token string, or None if the keysym is a bare modifier or
    cannot be mapped to a valid token.
    """
    if keysym in _MODIFIER_KEYSYMS:
        return None

    # Letters: Tk reports "a" or "A" depending on Shift; ch57x wants lowercase.
    if len(keysym) == 1 and keysym.isalpha():
        return keysym.lower()

    # Plain digits.
    if len(keysym) == 1 and keysym.isdigit():
        return keysym

    # Shifted number-row symbols map back to their digit.
    if keysym in _SHIFTED_DIGITS:
        return _SHIFTED_DIGITS[keysym]

    # Function keys F1..F24.
    if keysym.startswith("F") and keysym[1:].isdigit():
        n = int(keysym[1:])
        if 1 <= n <= 24:
            return f"f{n}"

    # Numeric keypad digits.
    kp = _keypad_digit(keysym)
    if kp:
        return kp

    # Named-key lookup table.
    if keysym in _KEYSYM_MAP:
        return _KEYSYM_MAP[keysym]

    # Last resort: a lowercase keysym that already matches the vocabulary.
    low = keysym.lower()
    if low in VALID_TOKEN_KEYS:
        return low

    return None


def _active_modifiers(event):
    """Return the ordered list of modifier tokens active for this event."""
    state = getattr(event, "state", 0) or 0
    mods = set()

    if state & _STATE_CONTROL:
        mods.add("ctrl")
    if state & _STATE_SHIFT:
        mods.add("shift")
    if any(state & bit for bit in _STATE_COMMAND_BITS):
        mods.add("cmd")
    if any(state & bit for bit in _STATE_OPTION_BITS):
        mods.add("alt")

    # Keep a deterministic, readable order.
    return [m for m in _MODIFIER_ORDER if m in mods]


def event_to_token(event):
    """
    Convert a Tkinter key-press event into a ch57x token string.

    Examples:
        Cmd+S            -> "cmd-s"
        Cmd+Shift+Z      -> "cmd-shift-z"
        F5               -> "f5"
        Left arrow       -> "left"

    Returns None when the event carried only modifier keys, so the caller
    can keep listening for the actual key.
    """
    keysym = getattr(event, "keysym", "")
    base = normalize_keysym(keysym)
    if base is None:
        return None

    mods = _active_modifiers(event)

    # If Shift is the only modifier and the base key already encodes the
    # shifted character (a symbol or a shifted digit), drop the redundant
    # Shift so we emit, e.g. "2" rather than "shift-2" for the "@" key.
    if mods == ["shift"] and (
        keysym in _SHIFTED_DIGITS or keysym in _KEYSYM_MAP
    ):
        mods = []

    if mods:
        return "-".join(mods + [base])
    return base
