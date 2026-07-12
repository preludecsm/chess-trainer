#!/bin/bash
# Usage: switch.sh [Personality] [depth N]
# Writes the two control files. The running bot reads them at the start
# of your next game. No restart.
set -e
BOTDIR=~/Documents/Mick/Chess/lichess-bot
PERSFILE="$BOTDIR/engine_personality.txt"
DEPTHFILE="$BOTDIR/engine_depth.txt"

VALID="Beginner SafeRandom WanderingQueen PawnStorm Fianchetto"
CURRENT=$(cat "$PERSFILE" 2>/dev/null || echo Beginner)
DEPTH=$(cat "$DEPTHFILE" 2>/dev/null || echo 3)

usage() {
  echo "Usage: switch.sh [Personality] [depth N]"
  echo "Current: $CURRENT, depth $DEPTH"
  echo "Available: $VALID"
  exit 1
}

[ $# -eq 0 ] && usage
PERSONALITY="$CURRENT"
while [ $# -gt 0 ]; do
  case "$1" in
    depth) shift
      case "$1" in ''|*[!0-9]*) echo "depth needs a number"; usage;; esac
      DEPTH="$1";;
    *) if echo " $VALID " | grep -q " $1 "; then PERSONALITY="$1"
       else echo "Unknown personality: $1"; usage; fi;;
  esac
  shift
done

echo "$PERSONALITY" > "$PERSFILE"
echo "$DEPTH" > "$DEPTHFILE"
echo "Personality: $PERSONALITY, depth $DEPTH  (applies to your NEXT game)"
