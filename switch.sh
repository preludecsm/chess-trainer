#!/bin/bash
# Usage: switch.sh [Personality] [depth N]   — either, or both
set -e
export PATH="/opt/homebrew/bin:$PATH"
BOTDIR=~/Documents/Mick/Chess/lichess-bot
CONFIG="$BOTDIR/config.yml"
DEPTHFILE="$BOTDIR/engine_depth.txt"

VALID=$(grep -oE '^class [A-Za-z0-9_]+' "$BOTDIR/homemade_personalities.py" \
        | awk '{print $2}' | grep -v '^_')
CURRENT=$(grep '^  name:' "$CONFIG" | sed 's/.*"\(.*\)".*/\1/')
DEPTH=$(cat "$DEPTHFILE" 2>/dev/null || echo 4)

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

# Depth -> time controls (policy: blitz, rapid, unlimited; no bullet,
# no days-based correspondence — min_days:15 blocks those while
# "correspondence" here admits unlimited games)
case "$DEPTH" in
  1|2|3) TCS="blitz rapid correspondence"; HUMAN="blitz, rapid, unlimited";;
  4)     TCS="rapid correspondence";       HUMAN="rapid, unlimited";;
  *)     TCS="correspondence";             HUMAN="unlimited only";;
esac

echo "$DEPTH" > "$DEPTHFILE"
sed -i '' "s/^  name: \".*\"/  name: \"$PERSONALITY\"/" "$CONFIG"
sed -i '' "s/^  hello: .*/  hello: \"$PERSONALITY (depth $DEPTH) reporting for duty. Good luck, {opponent}\"/" "$CONFIG"

awk -v tcs="$TCS" '
  /^  time_controls:/ {print; n=split(tcs,a," "); for(i=1;i<=n;i++) print "    - " a[i]; skip=1; next}
  skip && /^    - / {next}
  {skip=0; print}
' "$CONFIG" > "$CONFIG.tmp" && mv "$CONFIG.tmp" "$CONFIG"

tmux send-keys -t chessbot C-c
sleep 2
tmux send-keys -t chessbot "caffeinate -i python3 lichess-bot.py" Enter
echo "Bot restarted as: $PERSONALITY, depth $DEPTH (unrated only)"
echo "Accepting: $HUMAN"
