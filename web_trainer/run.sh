#!/bin/bash
# Local browser trainer: personality bots + live Stockfish eval.
# Run this, then open http://localhost:5001
#
# Prefers the PyPy venv (venv-pypy) when present: measured 3-5x faster
# per bot move than CPython on this engine (see MIGRATION.md benchmark).
cd "$(dirname "$0")"
if [ -x venv-pypy/bin/python ]; then
  echo "(using PyPy)"
  exec venv-pypy/bin/python server.py
fi
source venv/bin/activate
python3 server.py
