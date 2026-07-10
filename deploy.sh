#!/bin/bash
cd "$(dirname "$0")"
cp personality_bots.py homemade_personalities.py lichess-bot/
echo "Deployed. Restart with: switch.sh <Personality>"
