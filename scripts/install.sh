#!/usr/bin/env bash
# install.sh — Set up all dependencies for ch57x-macropad-manager on macOS
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

info()    { echo -e "${BOLD}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

echo ""
echo -e "${BOLD}ch57x-macropad-manager — installer${RESET}"
echo "================================================"
echo ""

# ── 1. Homebrew ──────────────────────────────────────────────────────────────
info "Checking for Homebrew..."
if ! command -v brew &>/dev/null; then
    error "Homebrew not found."
    echo ""
    echo "  Install Homebrew by following the official instructions at:"
    echo "    https://brew.sh"
    echo ""
    echo "  The recommended one-liner from that page is:"
    echo "    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo ""
    echo "  After Homebrew is installed, re-run this script."
    echo ""
    exit 1
fi
success "Homebrew is available."

# ── 2. libusb ────────────────────────────────────────────────────────────────
info "Checking for libusb..."
if brew list libusb &>/dev/null; then
    success "libusb is already installed."
else
    info "Installing libusb via Homebrew..."
    brew install libusb
    success "libusb installed."
fi

# ── 3. Rust / Cargo ──────────────────────────────────────────────────────────
info "Checking for Rust/Cargo..."
if ! command -v cargo &>/dev/null; then
    # Try the standard cargo location even if it is not in PATH yet
    if [[ -x "$HOME/.cargo/bin/cargo" ]]; then
        export PATH="$HOME/.cargo/bin:$PATH"
        success "Cargo found at ~/.cargo/bin (not in PATH — added for this session)."
    else
        error "Cargo not found."
        echo ""
        echo "  Install Rust with:"
        echo "    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
        echo "  Then open a new terminal (or run: source \"\$HOME/.cargo/env\")"
        echo "  and re-run this script."
        echo ""
        exit 1
    fi
else
    success "Cargo is available ($(cargo --version))."
fi

# ── 4. ch57x-keyboard-tool ───────────────────────────────────────────────────
info "Checking for ch57x-keyboard-tool..."
TOOL="$HOME/.cargo/bin/ch57x-keyboard-tool"
if [[ -x "$TOOL" ]]; then
    success "ch57x-keyboard-tool is already installed."
else
    info "Installing ch57x-keyboard-tool via cargo (this may take a few minutes)..."
    cargo install ch57x-keyboard-tool
    success "ch57x-keyboard-tool installed."
fi

# ── 5. Python packages ───────────────────────────────────────────────────────
info "Installing Python packages (customtkinter, pyyaml, pillow)..."
python3 -m pip install --quiet --upgrade customtkinter pyyaml pillow
success "Python packages installed."

echo ""
echo "================================================"
info "Running self-check (scripts/verify.sh)..."
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/verify.sh"
