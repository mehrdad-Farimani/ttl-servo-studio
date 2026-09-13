#!/bin/sh
set -eu
cd "$(dirname "$0")"
trap 'result=$?; if [ "$result" -ne 0 ]; then echo "Setup failed. Check the README for Python and Tkinter requirements."; printf "Press Enter to close: "; read answer; fi' EXIT
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import ttl_servo_studio, serial' 2>/dev/null; then
    .venv/bin/python -m pip install .
fi
.venv/bin/python -m ttl_servo_studio
