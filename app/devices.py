"""
devices.py

Device profiles and detection for CH57x family macro pads.

This module describes every supported device geometry (rows, columns, knobs),
their USB product IDs, and whether they expose programmable LED backlight.
It also detects which device, if any, is currently connected so the rest of
the application can show a status indicator and warn on geometry mismatches.

The CH57x family shares vendor id 0x1189. The known product ids are:
    0x8890, 0x8840, 0x8842.
LED control is only available on the 0x8840 / 0x8842 variants.

Public API:
    DEVICE_PROFILES        list of profile dicts (see schema below)
    profile_by_id(pid)     lookup a profile by its string id
    profile_by_product(p)  lookup a profile by integer product id
    detect_connected()     return the connected profile, or None
    geometry_of(data)      return geometry of a parsed YAML preset dict

Profile schema (each entry of DEVICE_PROFILES):
    {
        "id":         str   stable identifier used in the UI dropdown
        "label":      str   human readable name
        "rows":       int
        "columns":    int
        "knobs":      int
        "product_id": int   USB product id (None for the custom entry)
        "led":        bool   True if LED backlight is programmable
        "layers":     int    number of switchable layers (always 3)
    }
"""

import re
import subprocess

VENDOR_ID = 0x1189

# Product ids that the backend recognises.
PRODUCT_8890 = 0x8890
PRODUCT_8840 = 0x8840
PRODUCT_8842 = 0x8842

LAYERS = 3

# ---------------------------------------------------------------------------
# Device profiles
# ---------------------------------------------------------------------------
#
# The same physical geometry can ship under different product ids. The
# 0x8840 / 0x8842 ids identify the LED-capable revisions. We expose both the
# classic non-LED variants and the LED-capable variants so the user can pick
# the one that matches the hardware in hand.

DEVICE_PROFILES = [
    {
        "id": "3x1-1knob",
        "label": "3 keys + 1 knob (3x1)",
        "rows": 1, "columns": 3, "knobs": 1,
        "product_id": PRODUCT_8890, "led": False, "layers": LAYERS,
    },
    {
        "id": "3x2-1knob",
        "label": "6 keys + 1 knob (3x2)",
        "rows": 2, "columns": 3, "knobs": 1,
        "product_id": PRODUCT_8890, "led": False, "layers": LAYERS,
    },
    {
        "id": "3x3-2knob",
        "label": "9 keys + 2 knobs (3x3)",
        "rows": 3, "columns": 3, "knobs": 2,
        "product_id": PRODUCT_8890, "led": False, "layers": LAYERS,
    },
    {
        "id": "4x1-0knob",
        "label": "4 keys, no knob (4x1)",
        "rows": 4, "columns": 1, "knobs": 0,
        "product_id": PRODUCT_8890, "led": False, "layers": LAYERS,
    },
    {
        "id": "4x3-3knob",
        "label": "12 keys + 3 knobs (4x3)",
        "rows": 4, "columns": 3, "knobs": 3,
        "product_id": PRODUCT_8890, "led": False, "layers": LAYERS,
    },
    {
        "id": "5x3-3knob",
        "label": "15 keys + 3 knobs (5x3)",
        "rows": 5, "columns": 3, "knobs": 3,
        "product_id": PRODUCT_8890, "led": False, "layers": LAYERS,
    },
    {
        "id": "12key-4x3-2knob",
        "label": "12 keys + 2 knobs (4x3)",
        "rows": 4, "columns": 3, "knobs": 2,
        "product_id": PRODUCT_8890, "led": False, "layers": LAYERS,
    },
    # LED-capable revisions (same geometries, 0x8840 / 0x8842 product ids).
    {
        "id": "3x3-2knob-led",
        "label": "9 keys + 2 knobs (3x3, LED)",
        "rows": 3, "columns": 3, "knobs": 2,
        "product_id": PRODUCT_8840, "led": True, "layers": LAYERS,
    },
    {
        "id": "4x3-3knob-led",
        "label": "12 keys + 3 knobs (4x3, LED)",
        "rows": 4, "columns": 3, "knobs": 3,
        "product_id": PRODUCT_8842, "led": True, "layers": LAYERS,
    },
    # Free-form geometry entry.
    {
        "id": "custom",
        "label": "Custom geometry…",
        "rows": 3, "columns": 3, "knobs": 1,
        "product_id": None, "led": False, "layers": LAYERS,
    },
]


def profile_by_id(profile_id):
    """Return the profile dict with the given id, or None."""
    for prof in DEVICE_PROFILES:
        if prof["id"] == profile_id:
            return prof
    return None


def profile_by_product(product_id):
    """
    Return the first profile matching a USB product id, or None.

    Several profiles share a product id (the device only reports vendor and
    product, not the exact geometry), so this returns the first match. The
    caller can refine the choice afterwards if needed.
    """
    for prof in DEVICE_PROFILES:
        if prof["product_id"] == product_id:
            return prof
    return None


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _hexint(text):
    """Parse a hex string like '0x1189' or '1189' into an int, or None."""
    if text is None:
        return None
    text = text.strip().lower()
    if not text:
        return None
    try:
        if text.startswith("0x"):
            return int(text, 16)
        return int(text, 16)
    except ValueError:
        return None


def _scan_system_profiler():
    """
    Parse 'system_profiler SPUSBDataType' output and return a list of
    (vendor_id, product_id) integer tuples for every USB device found.

    Robust to missing tool / no output: returns an empty list on any failure.
    """
    pairs = []
    try:
        proc = subprocess.run(
            ["system_profiler", "SPUSBDataType"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:  # noqa: BLE001
        return pairs

    text = proc.stdout or ""
    # system_profiler groups properties per device; vendor / product ids are
    # printed on their own lines such as:
    #   Product ID: 0x8890
    #   Vendor ID: 0x1189  (some-vendor-name)
    vid = None
    for line in text.splitlines():
        stripped = line.strip()
        m = re.match(r"Product ID:\s*([0-9a-fA-Fx]+)", stripped)
        if m:
            pid = _hexint(m.group(1))
            # vendor may appear before or after; keep latest known vid
            if pid is not None:
                pairs.append((vid, pid))
            continue
        m = re.match(r"Vendor ID:\s*([0-9a-fA-Fx]+)", stripped)
        if m:
            vid = _hexint(m.group(1))
            # backfill the most recently appended pair if its vid was unknown
            if pairs and pairs[-1][0] is None:
                last_pid = pairs[-1][1]
                pairs[-1] = (vid, last_pid)
            continue
    return pairs


def _scan_ioreg():
    """
    Fallback scan using ioreg. Returns a list of (vendor_id, product_id)
    integer tuples. Empty list on any failure.
    """
    pairs = []
    try:
        proc = subprocess.run(
            ["ioreg", "-p", "IOUSB", "-l", "-w", "0"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:  # noqa: BLE001
        return pairs

    text = proc.stdout or ""
    # ioreg prints decimal values like:  "idVendor" = 4489
    vids = re.findall(r'"idVendor"\s*=\s*(\d+)', text)
    pids = re.findall(r'"idProduct"\s*=\s*(\d+)', text)
    for v, p in zip(vids, pids):
        try:
            pairs.append((int(v), int(p)))
        except ValueError:
            continue
    return pairs


def detect_connected():
    """
    Detect a connected CH57x device and return its profile dict, or None.

    Strategy: scan system_profiler first, then ioreg as a fallback. For every
    (vendor, product) pair that matches VENDOR_ID, look up a matching profile.
    Returns the first matching profile, or None when no device is present.
    """
    for scanner in (_scan_system_profiler, _scan_ioreg):
        try:
            pairs = scanner()
        except Exception:  # noqa: BLE001
            pairs = []
        for vid, pid in pairs:
            if vid != VENDOR_ID:
                continue
            prof = profile_by_product(pid)
            if prof is not None:
                return prof
            # Vendor matches but product unknown: report a generic profile so
            # the UI can still say "connected".
            return {
                "id": "unknown",
                "label": "CH57x device",
                "rows": 0, "columns": 0, "knobs": 0,
                "product_id": pid, "led": False, "layers": LAYERS,
            }
    return None


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def geometry_of(data):
    """
    Given a parsed YAML preset dict, return its geometry:
        {"rows", "columns", "knobs", "layers_count"}

    Falls back to counting the grid of the first layer when explicit rows /
    columns are absent. Always returns integers (zero on failure).
    """
    result = {"rows": 0, "columns": 0, "knobs": 0, "layers_count": 0}
    if not isinstance(data, dict):
        return result

    layers = data.get("layers") or []
    if isinstance(layers, list):
        result["layers_count"] = len(layers)

    rows = data.get("rows")
    columns = data.get("columns")
    knobs = data.get("knobs")

    first = layers[0] if layers and isinstance(layers[0], dict) else {}
    buttons = first.get("buttons") if isinstance(first, dict) else None

    # rows
    if isinstance(rows, int):
        result["rows"] = rows
    elif isinstance(buttons, list):
        result["rows"] = len(buttons)

    # columns
    if isinstance(columns, int):
        result["columns"] = columns
    elif isinstance(buttons, list) and buttons:
        first_row = buttons[0]
        if isinstance(first_row, list):
            result["columns"] = len(first_row)
        else:
            result["columns"] = len(buttons)

    # knobs
    if isinstance(knobs, int):
        result["knobs"] = knobs
    elif isinstance(first, dict):
        klist = first.get("knobs") or []
        if isinstance(klist, list):
            result["knobs"] = len(klist)

    return result
