#!/usr/bin/env bash
# verify.sh — Check tool installation, device connection, and validate all presets
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

info()    { echo -e "${BOLD}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
fail()    { echo -e "${RED}[FAIL]${RESET}  $*"; }

OVERALL=0   # non-zero means at least one failure

# ── 1. ch57x-keyboard-tool ───────────────────────────────────────────────────
info "Checking ch57x-keyboard-tool..."
TOOL="$HOME/.cargo/bin/ch57x-keyboard-tool"
if [[ -x "$TOOL" ]]; then
    success "ch57x-keyboard-tool found at $TOOL"
else
    fail "ch57x-keyboard-tool not found at $TOOL"
    echo "       Run:  cargo install ch57x-keyboard-tool"
    OVERALL=1
fi

# ── 2. Device detection ──────────────────────────────────────────────────────
echo ""
info "Checking for device VID 0x1189 (CH57x macro pad)..."

DEVICE_FOUND=0

# Try system_profiler first (friendlier output)
if command -v system_profiler &>/dev/null; then
    if system_profiler SPUSBDataType 2>/dev/null | grep -qi "1189"; then
        DEVICE_FOUND=1
    fi
fi

# Fallback: ioreg
if [[ "$DEVICE_FOUND" -eq 0 ]]; then
    if ioreg -p IOUSB -l 2>/dev/null | grep -qi "0x1189"; then
        DEVICE_FOUND=1
    fi
fi

if [[ "$DEVICE_FOUND" -eq 1 ]]; then
    success "Macro pad detected (VID 0x1189 found)."
else
    warn "Macro pad NOT detected."
    echo "       - Make sure the device is plugged in."
    echo "       - Use a data-capable cable (charge-only cables won't work)."
    echo "       - Try a different USB port."
fi

# ── 3. Validate presets ──────────────────────────────────────────────────────
echo ""
info "Validating presets..."

# Locate the presets directory relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PRESETS_DIR="$REPO_ROOT/presets"

if [[ ! -d "$PRESETS_DIR" ]]; then
    fail "Presets directory not found: $PRESETS_DIR"
    exit 1
fi

PASS=0
FAIL=0

while IFS= read -r -d '' yaml_file; do
    rel="${yaml_file#"$REPO_ROOT/"}"
    if [[ -x "$TOOL" ]]; then
        if "$TOOL" validate < "$yaml_file" &>/dev/null; then
            success "$rel"
            PASS=$(( PASS + 1 ))
        else
            # Capture the error message for context
            err_msg=$("$TOOL" validate < "$yaml_file" 2>&1 || true)
            fail "$rel"
            echo "         $err_msg"
            FAIL=$(( FAIL + 1 ))
            OVERALL=1
        fi
    else
        # Tool not available — just check YAML is parseable with python3
        if python3 -c "import yaml, sys; yaml.safe_load(open(sys.argv[1]))" "$yaml_file" &>/dev/null; then
            warn "$rel  (tool missing — YAML syntax only)"
            PASS=$(( PASS + 1 ))
        else
            fail "$rel  (YAML parse error)"
            FAIL=$(( FAIL + 1 ))
            OVERALL=1
        fi
    fi
done < <(find "$PRESETS_DIR" -name "*.yaml" -print0 | sort -z)

echo ""
echo "================================================"
echo -e "  Presets validated: ${GREEN}${PASS} passed${RESET}  |  ${RED}${FAIL} failed${RESET}"
echo "================================================"
echo ""

if [[ "$OVERALL" -ne 0 ]]; then
    fail "Verification completed with errors."
    exit 1
fi

success "All checks passed."
