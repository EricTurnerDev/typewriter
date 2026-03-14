#!/usr/bin/env bash
# setup.sh — One-time setup for the Typewriter application.
#
# Usage:
#   chmod +x setup.sh && ./setup.sh
#
# What this does:
#   1. Checks for Python 3.9+
#   2. Installs system-level SDL2 libraries (needed by pygame)
#   3. Creates a Python virtual environment
#   4. Installs Python dependencies
#   5. Generates placeholder typewriter sound effects
#
# After setup, use run.sh to launch the application.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC}  $*"; }
fail() { echo -e "${RED}  ✗${NC} $*" >&2; exit 1; }

echo ""
echo "  ══════════════════════════════════════"
echo "   TYPEWRITER  —  Setup"
echo "  ══════════════════════════════════════"
echo ""

# ── Python version check ──────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PY=$(python3 --version 2>&1 | awk '{print $2}')
    MAJOR=$(echo "$PY" | cut -d. -f1)
    MINOR=$(echo "$PY" | cut -d. -f2)
    if [[ "$MAJOR" -lt 3 || ( "$MAJOR" -eq 3 && "$MINOR" -lt 9 ) ]]; then
        fail "Python 3.9+ is required (found $PY)"
    fi
    ok "Python $PY"
else
    fail "python3 not found. Install Python 3.9+ and try again."
fi

# ── System SDL2 libraries ─────────────────────────────────────────────────────
echo ""
echo "  Installing system dependencies (requires sudo)…"
echo ""

if command -v apt-get &>/dev/null; then
    # Update ignoring errors from third-party repos (e.g. broken GPG keys
    # for unrelated apps like Cursor, Chrome, etc. that live on this machine).
    echo "  Updating package lists (third-party repo errors are non-fatal)…"
    sudo apt-get update -qq 2>&1 \
        | grep -v "^W:" | grep -v "^N:" || true

    sudo apt-get install -y \
        libsdl2-dev libsdl2-mixer-dev libsdl2-image-dev libsdl2-ttf-dev \
        python3-dev python3-venv python3-pip \
        fonts-liberation fonts-freefont-ttf
    ok "apt packages installed"

elif command -v dnf &>/dev/null; then
    sudo dnf install -y -q \
        SDL2-devel SDL2_mixer-devel SDL2_image-devel SDL2_ttf-devel \
        python3-devel python3-pip \
        liberation-fonts-common google-noto-mono-fonts
    ok "dnf packages installed"

elif command -v pacman &>/dev/null; then
    sudo pacman -Sy --noconfirm --needed \
        sdl2 sdl2_mixer sdl2_image sdl2_ttf \
        python python-pip \
        ttf-liberation ttf-freefont
    ok "pacman packages installed"

elif command -v zypper &>/dev/null; then
    sudo zypper install -y -q \
        libSDL2-devel libSDL2_mixer-devel libSDL2_image-devel libSDL2_ttf-devel \
        python3-devel python3-pip
    ok "zypper packages installed"

else
    warn "Package manager not recognised. Please ensure SDL2 and SDL2_mixer are installed."
fi

# ── Python virtual environment ────────────────────────────────────────────────
echo ""
echo "  Creating Python virtual environment…"

if [[ -d venv ]]; then
    warn "venv/ already exists — skipping creation"
else
    python3 -m venv venv
    ok "Created venv/"
fi

# Activate for the remainder of this script
# shellcheck source=/dev/null
source venv/bin/activate

echo ""
echo "  Installing Python packages…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Python packages installed"

# ── Generate sound assets ─────────────────────────────────────────────────────
echo ""
echo "  Generating typewriter sound effects…"
python generate_sounds.py
ok "Sounds ready in assets/sounds/"

# ── Create output directories ─────────────────────────────────────────────────
mkdir -p sessions exports
ok "Output directories ready"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "  ══════════════════════════════════════"
echo "   Setup complete!"
echo "  ══════════════════════════════════════"
echo ""
echo "  Launch with:"
echo "    ./run.sh               full-screen"
echo "    ./run.sh --windowed    windowed mode"
echo "    ./run.sh --no-sound    silent mode"
echo "    ./run.sh --help        all options"
echo ""
