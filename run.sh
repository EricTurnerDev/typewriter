#!/usr/bin/env bash
# run.sh — Launch the Typewriter application.
#
# Activates the virtual environment and passes all arguments to main.py.
#
#   ./run.sh                    # full-screen
#   ./run.sh --windowed         # resizable window
#   ./run.sh --no-sound         # silent
#   ./run.sh --load sessions/session_20240101_120000
#   ./run.sh --new              # blank page, ignore autosave

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -d venv ]]; then
    echo "Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

# shellcheck source=/dev/null
source venv/bin/activate
exec python main.py "$@"
