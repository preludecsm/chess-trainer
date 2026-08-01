#!/bin/bash
# Local browser trainer: personality bots + live Stockfish eval.
# Run this, then open http://localhost:5001
#
# Prefers the PyPy venv (venv-pypy) when present: measured 3-5x faster
# per bot move than CPython on this engine (see MIGRATION.md benchmark).
#
# Defaults to also binding this Mac's Tailscale IP so the trainer is
# reachable from other tailnet devices (e.g. iPhone) -- see REMOTE.md.
# Override with TAILSCALE_BIND= (empty) to go back to 127.0.0.1 only.
cd "$(dirname "$0")"
export TAILSCALE_BIND="${TAILSCALE_BIND-100.112.209.13}"
if [ -x venv-pypy/bin/python ]; then
  echo "(using PyPy)"
  exec venv-pypy/bin/python server.py
fi
source venv/bin/activate
python3 server.py
