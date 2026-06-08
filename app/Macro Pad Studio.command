#!/bin/bash
# Launcher for Macro Pad Studio.
# Double-click in Finder to start the app.

# Resolve the directory this script lives in (the app/ folder).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1

exec python3 macropad_studio.py
