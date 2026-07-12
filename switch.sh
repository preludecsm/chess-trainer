#!/bin/bash
# Usage: switch.sh [Personality] [depth N]   — either, or both
#
# Changes the bot's personality and/or search depth, rewrites the
# challenge policy to match the depth (so the bot never accepts a clock
# it cannot think on), and restarts it inside the tmux session.
set -e
export PATH="/opt/homebrew/bin:$PATH"
BOTDIR=~/Documents/Mick/Chess/lichess-bot
CONFIG="$BOTDIR/config.yml"
DEPTHFILE="$BOTDIR/engine_depth.txt"

VALID=$(grep -oE '^class [A-Za-z0-9_]+' "$BOTDIR/homemade_personalities.py" \
        | awk '{print $2}' | grep -v '^_')
CURRENT=$(grep '^  name:' "$CONFIG" | sed 's/.*"\(.*\)".*/\1/')
DEPTH=$(cat "$DEPTHFILE" 2>/dev/null || echo 3)

usage() {
  echo "Usage: switch.sh [Personality] [depth N]"
  echo "Current: ${CURRENT:-unset}, depth $DEPTH"
  echo "Available personalities:"
  echo "$VALID" | sed 's/^/  /'
  exit 1
}

[ $# -eq 0 ] && usage
PERSONALITY="$CURRENT"
while [ $# -gt 0 ]; do
  case "$1" in
    depth)
      shift
      case "$1" in ''|*[!0-9]*) echo "depth needs a number"; usage;; esac
      DEPTH="$1";;
    *)
      if echo "$VALID" | grep -qx "$1"; then PERSONALITY="$1"
      else echo "Unknown personality: $1"; usage; fi;;
  esac
  shift
done

# Depth -> minimum base time. Measured think times (middlegame, Mac mini):
#   depth 2 ~1s | depth 3 ~15-20s | depth 4 ~80-135s | depth 5+ minutes
# max_base stays at the 3-hour ceiling; only the floor moves.
case "$DEPTH" in
  1|2) MINBASE=180;   HUMAN="3+ min (blitz and up)";;
  3)   MINBASE=300;   HUMAN="5+ min (rapid and up) - RECOMMENDED";;
  4)   MINBASE=1800;  HUMAN="30+ min (classical only)";;
  *)   MINBASE=3600;  HUMAN="60+ min (long classical; slow)";;
esac

[ "$DEPTH" -ge 5 ] && \
  echo "Warning: depth $DEPTH takes many minutes per move in Python."

echo "$DEPTH" > "$DEPTHFILE"
sed -i '' "s/^  name: \".*\"/  name: \"$PERSONALITY\"/" "$CONFIG"
sed -i '' "s/^  hello: .*/  hello: \"$PERSONALITY (depth $DEPTH) reporting for duty. Good luck, {opponent}\"/" "$CONFIG"
sed -i '' "s/^  min_base: .*/  min_base: $MINBASE/" "$CONFIG"
sed -i '' "s/^  max_base: .*/  max_base: 10800/" "$CONFIG"

tmux send-keys -t chessbot C-c
sleep 2
tmux send-keys -t chessbot "caffeinate -i python3 lichess-bot.py" Enter
echo "Bot restarted as: $PERSONALITY, depth $DEPTH (unrated, live games only)"
echo "Accepting: $HUMAN"
echo ""
echo "Note: Lichess rate-limits rapid reconnects. If the log shows"
echo "RateLimitedError, wait a minute - do not restart again."
