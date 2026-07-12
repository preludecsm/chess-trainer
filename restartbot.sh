#!/bin/bash
# Restart the bot cleanly. Needed ONLY for:
#   - code changes (after ./deploy.sh)
#   - challenge-policy changes (when switch.sh says so)
#
# NOT needed to change personality or depth — switch.sh does that live.
#
# Lichess rate-limits reconnections to the event stream. This script kills
# the process, waits for the limit to go cold, and starts once.
export PATH="/opt/homebrew/bin:$PATH"
BOTDIR="$HOME/Documents/Mick/Chess/lichess-bot"

echo "Stopping the bot..."
pkill -9 -f lichess-bot.py 2>/dev/null
tmux kill-session -t chessbot 2>/dev/null
sleep 2

if pgrep -f lichess-bot.py > /dev/null; then
  echo "WARNING: a lichess-bot process is still alive. Aborting."
  exit 1
fi

echo "Waiting 60s for Lichess's rate limit to go cold (nothing connecting)..."
sleep 60

echo "Starting..."
tmux new-session -d -s chessbot -c "$BOTDIR"
tmux send-keys -t chessbot \
  "source venv/bin/activate && caffeinate -i python3 lichess-bot.py" Enter
sleep 15

tmux capture-pane -pt chessbot | tail -3
echo ""
echo "If you see 'awaiting challenges', it's live."
echo "If you see RateLimitedError, wait - do NOT run this again."
