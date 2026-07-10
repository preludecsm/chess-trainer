#!/bin/bash
# Idempotent: reports if the bot is running, starts it if not.
export PATH="/opt/homebrew/bin:$PATH"
BOTDIR="$HOME/Documents/Mick/Chess/lichess-bot"

if tmux has-session -t chessbot 2>/dev/null && pgrep -f lichess-bot.py >/dev/null; then
  echo "Bot is running."
  tmux capture-pane -pt chessbot | tail -3
  exit 0
fi

tmux kill-session -t chessbot 2>/dev/null   # clear any dead session
tmux new-session -d -s chessbot -c "$BOTDIR"
tmux send-keys -t chessbot "source venv/bin/activate && caffeinate -i python3 lichess-bot.py" Enter
echo "Bot was down - started in tmux session 'chessbot'."
