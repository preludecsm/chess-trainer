# MickTrainerBot — Personality Chess Trainer

A configurable chess sparring partner that runs on a Mac mini, plays on
Lichess as **MickTrainerBot**, and is controlled from an iPhone or iPad
over Tailscale/SSH. Playing *style* (personality) and playing *strength*
(search depth) are independent controls, switchable with one command or
one tap.

Built on [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot)
with custom Python engines (this repository) plugged in as "homemade"
engines.

> **Personal project.** This is the working runbook for my own setup —
> account names, paths, and hardware (a Mac mini under
> `~/Documents/Mick/Chess`) are mine. Everything here is adaptable, but
> expect to substitute your own bot account, usernames, and paths
> throughout. Shared as-is in case it's useful; no support implied.

## Repository layout

```
Chess/                      <- this repo
├── README.md               <- this file
├── personality_bots.py     <- engines & personalities (canonical copy)
├── homemade_personalities.py  <- lichess-bot adapters (canonical copy)
├── switch.sh               <- change personality/depth (in PATH via symlink)
├── startbot.sh             <- check/start the bot (in PATH via symlink)
├── deploy.sh               <- copy the two .py files into lichess-bot/
└── lichess-bot/            <- upstream clone: NOT tracked here (.gitignore)
    ├── config.yml          <- SENSITIVE: contains the API token
    ├── engine_depth.txt    <- current search depth
    └── venv/               <- python environment
```

The live engine files run from inside `lichess-bot/`; the copies here are
the versioned originals. After editing here, run `./deploy.sh` and then
`switch.sh <Personality>` to restart.

## Purpose

Commercial engines are either too strong or artificially weakened in
unsatisfying ways. This trainer offers opponents with *deliberate,
exploitable biases* — a queen that wanders, pawns that storm, a player
who never blunders but has no plan — at adjustable calculation depth.
Losses are instructive because each personality fails (and punishes) in a
characteristic way, and every game lands in Lichess history for analysis.

## Architecture

```
iPhone / iPad                     Mac mini                        Lichess
─────────────                     ────────                        ───────
Prompt 3 clip or    ── SSH ──▶    switch.sh / startbot.sh          game
Apple Shortcut     (Tailscale)      │ edit config.yml + depth       ▲
                                    │ (re)start bot in tmux         │
                                    ▼                               │
                                  lichess-bot ── personality engine─┘
                                  (tmux session "chessbot",
                                   caffeinate holds off sleep,
                                   LaunchAgent starts it at boot)
```

- **personality_bots.py** — all personalities are alpha-beta searchers
  sharing one engine core (negamax + alpha-beta, MVV-LVA move ordering,
  and a quiescence search that resolves captures before evaluating —
  the last is what keeps it from blundering material mid-exchange). Each
  personality adds a small bias to the evaluation function, so style
  survives calculation instead of replacing it.
- **homemade_personalities.py** — thin adapters exposing each bot to
  lichess-bot as a named homemade engine. Reads depth from
  `engine_depth.txt` (default 4). Adding a class here automatically makes
  it a valid `switch.sh` argument.
- **switch.sh** — rewrites config.yml (engine name, greeting, accepted
  time controls per depth), writes the depth file, restarts the bot.
- **startbot.sh** — idempotent check-and-start; also run at boot by
  `~/Library/LaunchAgents/com.mick.chessbot.plist`.

## Personalities

| Name | Style | Trains you on |
|---|---|---|
| **Beginner** | No bias — material + centralization search | Clean baseline opponent at any depth |
| **SafeRandom** | Random among moves within ¾ pawn of best; never blunders within its horizon, never has a plan | Punishing planlessness; converting small edges |
| **WanderingQueen** | Values an active, far-flung queen | Exploiting queen sorties; tempo play |
| **PawnStorm** | Values pawns advanced toward your king | Defending pawn storms; counterplay timing |
| **Fianchetto** | Values bishops nested on b2/g2 (b7/g7) behind their pawns; resists trading them | Prying open the long diagonal: trade the fianchetto bishop, then occupy the holes it guarded |

## Strength and accepted time controls

Depth 1–8, shared by all personalities. Quiescence search adds nodes but
MVV-LVA ordering pays for them; net think time is roughly 5x per ply.
**Live games only** — correspondence and unlimited are declined (they're
hard to find in the Lichess app). Depth sets a *minimum base time* so the
clock always allows the bot to calculate; `max_base` stays at the 3-hour
ceiling, so anything from the floor up through classical is accepted:

| Depth | Approx. think/move | Min base time | Accepts |
|---|---|---|---|
| 1–2 | instant–2 s | 3 min | blitz and up |
| 3 | ~1–2 s | 5 min | blitz and up |
| 4 (default) | ~5–6 s | 10 min | rapid and up |
| 5 | ~30 s | 25 min | classical |
| 6+ | minutes | 60 min | long classical |

Challenge from the app as e.g. **Rapid 10+0 or 15+10** at depth 4 — live
games open straight to the board, no game-finding needed. (`min_base`
checks base time only; a 3+2 game clears the depth-1/2 floor even though
increment isn't counted.)

## Challenge policy (as configured)

- **Unrated (casual) games only** — rated challenges auto-declined.
- **Allow-list**: only the main account (`mnoordewier`) may challenge.
- **Concurrency 5**: up to five games at once.
- **Live games only, no bullet.** `correspondence` is removed from
  `time_controls`, so unlimited and days-based correspondence are both
  declined. Accepted speeds are gated by `min_base` (the depth floor,
  above) through `max_base: 10800`.
- All five game slots share the single configured personality/depth;
  switching mid-game restarts the bot (games survive, but subsequent
  moves come from the new brain).
- `abort_time: 300` — a game with no moves is aborted after 5 minutes.
  Largely moot now that games are live (the app puts you straight on the
  board), but harmless; make your first move promptly regardless.

## Daily use

```bash
switch.sh                          # show current personality/depth + menu
switch.sh PawnStorm                # change personality, keep depth
switch.sh depth 3                  # change depth, keep personality
switch.sh WanderingQueen depth 4   # change both
startbot.sh                        # is it running? start it if not
tmux attach -t chessbot            # live log (Ctrl-b, release, d to leave)
tmux capture-pane -pt chessbot | tail -20   # peek without attaching
```

Challenge **MickTrainerBot** from the main account
(https://lichess.org/@/MickTrainerBot — green dot = bot online). Set the
challenge to **Casual** and a live time control the current depth accepts
(e.g. Rapid 10+0 at depth 4). The board opens as soon as the bot accepts;
the game chat greets with e.g. *"PawnStorm (depth 4) reporting for duty"*
— confirmation of which trainer you're facing.

To confirm the bot's live games directly from the token:

```bash
TOKEN=$(grep '^token:' ~/Documents/Mick/Chess/lichess-bot/config.yml | sed 's/token: *"\(.*\)"/\1/')
curl -s -H "Authorization: Bearer $TOKEN" https://lichess.org/api/account/playing | python3 -m json.tool
```

Unlimited-game note: the bot polls correspondence-family games on a
relaxed cycle, so replies can lag a few minutes beyond think time.

## Install on macOS (from scratch)

Assumes Homebrew, Tailscale, and Remote Login are set up, and this repo
is cloned/copied to `~/Documents/Mick/Chess`.

```bash
# 0. Tools
brew install python git tmux

# 1. lichess-bot
cd ~/Documents/Mick/Chess
git clone https://github.com/lichess-bot-devs/lichess-bot.git
cd lichess-bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Engines: deploy this repo's files and wire them in
cd .. && ./deploy.sh && cd lichess-bot
echo '' >> homemade.py
echo 'from homemade_personalities import *  # noqa: F401,F403' >> homemade.py
# (line must start at column 0)
python3 -c "import homemade; print('OK:', homemade.Beginner.__name__)"

# 3. Upstream patch (KeyError 'game' on correspondence ping;
#    re-check after any git pull of lichess-bot)
sed -i '' 's/opponent_name = event\["game"\]/opponent_name = event.get("game", {})/' lib/lichess_bot.py

# 4. Lichess account: create a NEW account (bot upgrade requires zero
#    games played), then a token with bot:play scope:
#    https://lichess.org/account/oauth/token/create?scopes[]=bot:play
cp config.yml.default config.yml
#    edit config.yml: set token; engine: dir ".", protocol "homemade",
#    name "Beginner"

# 5. Challenge policy (one-time config edits)
sed -i '' '/^    - rated/d' config.yml                       # casual only
# Live games only: remove correspondence/unlimited from accepted speeds
awk '!(/^    - correspondence[ \t]*$/)' config.yml > config.tmp && mv config.tmp config.yml
sed -i '' '/^#   - correspondence/d' config.yml
sed -i '' 's/^  min_days: .*/  min_days: 1/' config.yml       # (days settings unused now)
sed -i '' 's/^  max_days: .*/  max_days: 14/' config.yml
sed -i '' 's/^  concurrency: .*/  concurrency: 5/' config.yml
sed -i '' 's/^  abort_time: .*/  abort_time: 300/' config.yml
# min_base/max_base are set per-depth by switch.sh; defaults are fine here
printf '  allow_list:\n    - mnoordewier\n' > tmp_allow.yml
sed -i '' '/^challenge:/r tmp_allow.yml' config.yml && rm tmp_allow.yml

# 6. Upgrade account to BOT (first run only), verify, then Ctrl-C
python3 lichess-bot.py -u

# 7. Persistent run + control scripts in PATH
chmod +x ../switch.sh ../startbot.sh ../deploy.sh
ln -s ~/Documents/Mick/Chess/switch.sh   /opt/homebrew/bin/switch.sh
ln -s ~/Documents/Mick/Chess/startbot.sh /opt/homebrew/bin/startbot.sh
startbot.sh          # creates tmux session "chessbot" and starts the bot

# 8. Start at boot (auto-login makes login ≈ boot)
#    install ~/Library/LaunchAgents/com.mick.chessbot.plist running
#    startbot.sh with RunAtLoad, then:
launchctl load ~/Library/LaunchAgents/com.mick.chessbot.plist
```

Phone/iPad control: Prompt 3 host over Tailscale with clips for the
common `switch.sh` invocations, and/or Apple Shortcuts using "Run Script
Over SSH" (use full script paths there — non-interactive SSH may lack
Homebrew's PATH; both scripts also export it defensively).

## Extending

Add a personality: subclass `SearchingPersonality` in
personality_bots.py and override `style_for(board, color)` — a small
positional score. Keep bonuses in *tenths* of a pawn or the search will
sacrifice real material for style points. Add a three-line adapter class
in homemade_personalities.py; its class name becomes a switch.sh argument
automatically. Then `./deploy.sh && switch.sh NewName`, and commit:

```bash
git add -A && git commit -m "Add Fianchetto personality"
```

Ideas: Simplifier (trades when ahead), Hypermodern (central control from
a distance), per-personality opening books. Engine-strength upgrades that
apply to every personality: piece-square tables and king-safety terms
(more chess knowledge), or a transposition table with iterative deepening
(more effective depth — would likely bring depth 5 into rapid range).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `module 'homemade' has no attribute 'X'` at startup | Typo'd/stale engine name in config.yml — run `switch.sh <ValidName>` |
| `SyntaxError: import * only allowed at module level` | Import line in homemade.py got indented — must start at column 0 |
| `KeyError: 'game'` crash in check_in_on_correspondence_games | Upstream bug; re-apply the step-3 patch (lost after `git pull` in lichess-bot/) |
| `tmux: command not found` over SSH | Non-interactive shells miss Homebrew's PATH — scripts export it; use full paths in Shortcuts |
| Challenge stuck at "You will be notified…" | Bot crashed or declining: `tmux capture-pane -pt chessbot \| tail -30` names the reason; `startbot.sh` revives |
| Bot ignores challenge | Rated, wrong account, bullet, or base time below the depth floor — check the last `switch.sh` output for the accepted range |
| Bot offline after reboot | LaunchAgent should handle it; otherwise `startbot.sh` |
| Depth change didn't take | Depth is read per game; the restart switch.sh performs picks it up |
| Behavior differs from repo code | Edited here but not deployed — `./deploy.sh` then restart |
| Bot plays weakly / low accuracy | Raise depth (`switch.sh depth 5` → classical time controls). Depth 4 with quiescence already plays solid tactical chess |

## Security notes

`lichess-bot/config.yml` contains the Lichess API token — it is
deliberately outside this repository (the whole `lichess-bot/` directory
is .gitignored). Never commit it; keep the directory out of anything
synced or shared.

## Acknowledgments and license

This project stands on two excellent open-source foundations:
[lichess-bot](https://github.com/lichess-bot-devs/lichess-bot) (the
bridge between engines and Lichess, AGPL-3.0) and
[python-chess](https://github.com/niklasf/python-chess) (move generation
and board logic). Neither is bundled here — the install steps clone
lichess-bot separately, and it retains its own license. Thanks also to
[Lichess](https://lichess.org) itself for a free, open platform with a
first-class bot API.

The code in this repository is released under the MIT License — see
[LICENSE](LICENSE).
