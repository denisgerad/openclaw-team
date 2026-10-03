#!/usr/bin/env bash
# openclaw-upload.sh
# Thin wrapper so developers can run: ./openclaw-upload.sh upload --file ...
# instead of: python3 openclaw-upload.py upload --file ...
#
# Place this file next to openclaw-upload.py and make it executable:
#   chmod +x openclaw-upload.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SCRIPT_DIR/openclaw-upload.py"

# Check Python is available
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.9 or later."
    exit 1
fi

# Check requests is installed
if ! python3 -c "import requests" &>/dev/null; then
    echo "Installing required dependency: requests"
    pip3 install requests --quiet
fi

exec python3 "$SCRIPT" "$@"
