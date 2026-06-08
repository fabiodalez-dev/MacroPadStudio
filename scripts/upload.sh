#!/usr/bin/env bash
# upload.sh — Upload a preset to the CH57x macro pad
#
# Usage:
#   bash scripts/upload.sh <preset-name>          # e.g. vscode-edit
#   bash scripts/upload.sh <path/to/preset.yaml>  # explicit path
#
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

TOOL="$HOME/.cargo/bin/ch57x-keyboard-tool"

usage() {
    echo ""
    echo -e "${BOLD}Usage:${RESET}"
    echo "  bash scripts/upload.sh <preset-name>"
    echo "  bash scripts/upload.sh <path/to/preset.yaml>"
    echo ""
    echo "Examples:"
    echo "  bash scripts/upload.sh vscode-edit"
    echo "  bash scripts/upload.sh final-cut-pro"
    echo "  bash scripts/upload.sh presets/dev/vscode-edit.yaml"
    echo ""
    echo "Available presets (sample):"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    find "$(dirname "$SCRIPT_DIR")/presets" -name "*.yaml" \
        | sed "s|.*/presets/||;s|\.yaml$||" | sort | head -20
    echo "  ... (run: find presets -name '*.yaml' | sed 's|.*/||;s|\.yaml||' | sort)"
    echo ""
    exit 1
}

# ── Argument check ────────────────────────────────────────────────────────────
if [[ $# -eq 0 ]]; then
    usage
fi

ARG="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PRESETS_DIR="$REPO_ROOT/presets"

# ── Locate the YAML file ──────────────────────────────────────────────────────
YAML_FILE=""

# Case 1: argument is an existing file path (absolute or relative)
if [[ -f "$ARG" ]]; then
    YAML_FILE="$ARG"
# Case 2: argument is a relative path from repo root
elif [[ -f "$REPO_ROOT/$ARG" ]]; then
    YAML_FILE="$REPO_ROOT/$ARG"
else
    # Case 3: search by name (with or without .yaml extension)
    SEARCH_NAME="${ARG%.yaml}.yaml"
    MATCH=$(find "$PRESETS_DIR" -name "$SEARCH_NAME" | head -1)
    if [[ -n "$MATCH" ]]; then
        YAML_FILE="$MATCH"
    fi
fi

if [[ -z "$YAML_FILE" ]]; then
    echo -e "${RED}[ERROR]${RESET} Preset not found: '$ARG'"
    echo ""
    echo "  Searched in: $PRESETS_DIR"
    echo "  Use the preset file name without the .yaml extension,"
    echo "  or provide a full path."
    echo ""
    usage
fi

# ── Tool check ────────────────────────────────────────────────────────────────
if [[ ! -x "$TOOL" ]]; then
    echo -e "${RED}[ERROR]${RESET} ch57x-keyboard-tool not found at $TOOL"
    echo "  Run: cargo install ch57x-keyboard-tool"
    exit 1
fi

# ── Upload ────────────────────────────────────────────────────────────────────
REL="${YAML_FILE#"$REPO_ROOT/"}"
echo ""
echo -e "${BOLD}Uploading preset:${RESET} $REL"
echo "  sudo $TOOL upload < $YAML_FILE"
echo ""

sudo "$TOOL" upload < "$YAML_FILE"

echo ""
echo -e "${GREEN}[OK]${RESET}  Preset '$REL' uploaded successfully."
echo ""
