#!/bin/bash
# Local browser trainer: personality bots + live Stockfish eval, no Lichess.
# Run this, then open http://localhost:5001
cd "$(dirname "$0")"
source venv/bin/activate
python3 server.py
