# MickTrainerBot — Personality Chess Trainer

A configurable chess sparring partner that runs on a Mac mini, plays on
Lichess as **MickTrainerBot**, and is controlled from an iPhone or iPad
over Tailscale/SSH. Playing *style* (personality) and playing *strength*
(search depth) are independent controls, switchable with one command or
one tap.

Built on [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot)
with custom Python engines (this repository) plugged in as "homemade"
engines.

> **Working on this project?** Read [NOTES.md](NOTES.md) first — it has the
> design rationale, the experiments that were tried and measured and
> rejected (transposition table, mobility eval, delta pruning), the bug
> signatures worth recognising, and the workflow traps. The code does not
> explain *why*, and several plausible "improvements" have already been
> disproven with numbers.

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
├── switch.sh               <- change personality/depth LIVE (no restart)
├── startbot.sh             <- check/start the bot if it's down
├── restartbot.sh           <- full restart (only for code/policy changes)
├── deploy.sh               <- copy the two .py files into lichess-bot/
└── lichess-bot/            <- upstream clone: NOT tracked here (.gitignore)
    ├── config.yml          <- SENSITIVE: contains the API token
    ├── engine_personality.txt  <- current personality (read per game)
    ├── engine_depth.txt        <- current search depth (read per game)
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

- **personality_bots.py** — all personalities share one engine core:
  negamax with alpha-beta, MVV-LVA move ordering, and a quiescence search
  that resolves captures before evaluating (this is what stops it
  blundering material mid-exchange). The evaluation knows material,
  piece-square tables, pawn structure (doubled / isolated / passed), king
  safety, and the bishop pair, with the king's table tapered between
  middlegame and endgame. Each personality then adds a *small* bias to
  that evaluation — so style emerges from search, not from a book, and it
  will happily pursue its style into positions where that's a bad idea.
  That is the point: the weakness is legible and punishable.
- **homemade_personalities.py** — a single `Personality` engine class
  registered with lichess-bot. It reads `engine_personality.txt` and
  `engine_depth.txt` **at the start of every game**, so the personality
  can change while the bot stays connected. Add a class to the
  `PERSONALITIES` dict and it becomes a valid `switch.sh` argument.
- **switch.sh** — writes the two files. Takes effect on your next game;
  **no restart, no reconnect**, so it can be run as often as you like.
  The valid personality list is hardcoded in the script (an earlier
  version grepped it out of the deployed adapter, which silently broke
  whenever the deployed copy was stale — add new personalities to the
  `VALID` line).
- **restartbot.sh** — a genuine restart, with a cold-down wait. Needed
  only after code changes (`./deploy.sh`) or when switch.sh says the
  accepted time controls changed.
- **startbot.sh** — idempotent check-and-start; also run at boot by
  `~/Library/LaunchAgents/com.mick.chessbot.plist`.

### The chat greeting

`config.yml`'s `hello:` is read **once at startup**, so it cannot track a
personality that now changes without a restart. It is therefore generic:

    Welcome to MickTrainerBot. Possible personalities are Beginner,
    SafeRandom, WanderingQueen, PawnStorm, Fianchetto. Good luck!

Which one you are *actually* facing is deliberately not announced — read
the board. To check from the terminal:

```bash
cat lichess-bot/engine_personality.txt          # what's configured
tmux capture-pane -pt chessbot | grep personality   # what the bot loaded
```

The second is authoritative: the adapter logs
`[personality] now playing as X at depth N` when it builds the engine.

### Why switching doesn't restart the bot

Lichess **rate-limits reconnections** to its event stream, per token. The
original design restarted lichess-bot on every personality change, which
made a handful of quick switches lock the bot out for many minutes. Now
the process stays connected permanently and only the two text files
change. Restarts are rare, and `restartbot.sh` waits 60 s with nothing
connected before reconnecting — which is what actually clears the limit.

## Personalities

| Name | Style | Margin | Trains you on |
|---|---|---|---|
| **Beginner** | No stylistic bias — plain positional search | 0.25 | Clean baseline opponent at any depth |
| **SafeRandom** | Random among all moves within ¾ pawn of best: never blunders within its horizon, never has a plan | 0.75 | Punishing planlessness; converting small edges |
| **WanderingQueen** | Brings the queen out early and keeps her roaming — rewards distance from home *and* centralization | 0.25 | Punishing early queen sorties with tempo |
| **PawnStorm** | Values pawns advanced toward your king (summed across all pawns, so it accumulates fast) | 0.25 | Defending pawn storms; counterplay in the centre while it commits on the wing |
| **Fianchetto** | Wants a bishop nested on g2/b2 (g7/b7) behind its pawn, and clings to it | 0.25 | Trade off the fianchetto bishop, then occupy the dark squares it was guarding |

### Tuning the style weights

Two lessons from getting these to actually show up in games:

**The horizon problem.** Fianchetto originally only scored the bishop
*once it reached* g7. But getting there takes g6, then Bg7 — and at
depth 3 the engine cannot see that payoff from far enough away to start
the journey. It fianchettoed in only 3 of 6 games. The fix was to reward
the **preparatory pawn move** on its own (g6/b6 earns a bonus even before
the bishop arrives). Now it commits in 5 of 6 games and will sometimes
open 1...b6. If a personality isn't expressing itself, ask whether the
reward is beyond its search horizon before assuming the weight is too low.

**Bad proxies.** WanderingQueen originally rewarded raw distance from
d1/d8, which meant a queen on a8 scored well while doing nothing. Adding
a centralization term made the bias unmistakable — it now plays 2...Qd6
and keeps her roaming, which costs it about two pawns a game. That is the
punishable price the trainer needs.

Sanity check when tuning: play the personality against Beginner for 20
moves and check material. **Within ±2 pawns of even means biased, not
broken** — it should pay a small price for its obsession, not collapse.
PawnStorm needed no bump; its bonus sums across all eight pawns and
accumulates on its own.

### Randomness (`RANDOM_MARGIN`)

Among root moves scoring within this many pawns of the best, one is
picked at random. This keeps repeated games from following the same
script without making the bot play badly — at 0.25 it varies between
d5 / e5 / Nf6 / Nc6 against 1.e4 (all real openings) while self-play
material stays dead even. Tune it in personality_bots.py:

- `0.0` — fully deterministic, and therefore memorizable
- `0.15` — slight variety, near-best every move
- `0.25` — real opening variety, no blunders *(current default)*
- `0.40+` — starts conceding real ground for variety's sake

Deliberately **no opening book.** A book would make the bot play a
memorized line correctly for 12 moves and teach nothing about why. The
personality bias produces the same *kind* of setup (Fianchetto keeps
reaching for g6/Bg7) from its own search, including in positions where
it shouldn't — which is exactly the exploitable, over-the-board weakness
a trainer wants.

## Strength and accepted time controls

Depth 1–8, shared by all personalities. Think time grows steeply — this
is Python, and there is no transposition table (one was tried; see
"What didn't work"). Measured on a Mac mini, middlegame positions:

| Depth | Think/move (middlegame) | Min base time | Practical use |
|---|---|---|---|
| 2 | ~1 s | 3 min | blitz; weak but instant |
| 3 (recommended) | ~15–20 s | 5 min | rapid and up; the sweet spot |
| 4 | ~80–135 s | 10 min | classical only (30+ min games) |
| 5+ | many minutes | 25–60 min | impractical |

**Depth 3 is the recommendation.** With the current evaluation it likely
plays better than depth 4 did with the old one, and it moves ~8x faster.
Depth 4 is viable only in the long classical games (e.g. 180+0) that the
config accepts.

`switch.sh` sets a *minimum base time* per depth so the clock always
allows the bot to calculate; `max_base` stays at the 3-hour ceiling, so
anything from the floor up through classical is accepted.

Challenge from the app as e.g. **Rapid 15+10** at depth 3 — live games
open straight to the board, no game-finding needed. (`min_base` checks
base time only; a 3+2 game clears the depth-1/2 floor even though
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
switch.sh PawnStorm                # change personality  (takes effect next game)
switch.sh depth 3                  # change depth        (takes effect next game)
switch.sh WanderingQueen depth 3   # change both
startbot.sh                        # is it running? start it if not
restartbot.sh                      # full restart - only after ./deploy.sh
tmux capture-pane -pt chessbot | tail -20   # peek at the log
tmux attach -t chessbot            # live log (Ctrl-b, release, d to leave)
```

### Three kinds of change, three procedures

| Change | What to do |
|---|---|
| **Personality or depth** | `switch.sh Fianchetto depth 3` — writes two text files, read at the start of your next game. **No restart.** Free to run as often as you like. |
| **Engine code** (`personality_bots.py`, `homemade_personalities.py`) | `./deploy.sh` **and then `restartbot.sh`** |
| **config.yml** (greeting, time controls, allow_list) | Edit directly, then `restartbot.sh` |

**The trap:** `./deploy.sh` alone is *not enough* for code changes. It
copies the file into `lichess-bot/`, but the running Python process has
already imported the old module into memory and will keep executing it.
Only a restart forces a fresh import. This bit us twice — every grep said
the new engine was in place, and the bot kept playing the old one.

**Restarts are expensive.** Lichess rate-limits reconnections to its
event stream, per token. Several restarts in quick succession lock the
bot out for many minutes, and the retry loop can re-arm the limit so it
does not clear on its own. `restartbot.sh` waits 60 s with nothing
connected — which is what actually clears it. **Batch changes, restart
once.** If it gets wedged: `pkill -9 -f lichess-bot.py; tmux kill-server`,
then wait 5+ minutes with *nothing* running before starting again.

The decisive check after any engine change: **does Fianchetto open with
1...b6 or 1...g6?** If not, the deployed engine is stale regardless of
what the greps say.

Challenge **MickTrainerBot** from the main account
(https://lichess.org/@/MickTrainerBot — green dot = bot online). Set the
challenge to **Casual** and a live time control the current depth accepts
(e.g. Rapid 15+10 at depth 3). The board opens as soon as the bot
accepts; the game chat greets with e.g. *"PawnStorm (depth 3) reporting
for duty"*
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
#    name "Personality"   <- constant; the personality itself lives in
#                            engine_personality.txt and is read per game
echo "Beginner" > engine_personality.txt
echo "3" > engine_depth.txt

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
ln -s ~/Documents/Mick/Chess/switch.sh     /opt/homebrew/bin/switch.sh
ln -s ~/Documents/Mick/Chess/startbot.sh   /opt/homebrew/bin/startbot.sh
ln -s ~/Documents/Mick/Chess/restartbot.sh /opt/homebrew/bin/restartbot.sh
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
positional score for how well the position suits the personality. Keep
bonuses in *tenths* of a pawn, or the search will sacrifice real material
for style points. Set `RANDOM_MARGIN` (0.25 is the house default). Add a
three-line adapter class
in homemade_personalities.py; its class name becomes a switch.sh argument
automatically. Then `./deploy.sh && switch.sh NewName`, and commit:

```bash
git add -A && git commit -m "Add Fianchetto personality"
```

Ideas: Simplifier (trades when ahead), Hypermodern (central control from
a distance), opening-specific personalities.

## What didn't work (and why)

Recorded so they aren't retried blindly:

- **Transposition table.** Added, measured, removed. Hit rate was only
  9.2% — the TT key includes depth, so entries from a depth-2 search
  don't serve a depth-3 probe, and it cost more to hash and store 14k
  positions than it saved. A TT only pays off alongside **iterative
  deepening** (search depth 1, 2, 3… reusing the table and the previous
  iteration's best move for ordering). That is the correct next
  performance project, and it would make depth 4–5 practical.
- **Mobility term in the evaluation** (bonus per legal move). Profiling
  showed it consumed ~65% of total evaluation time — generating legal
  moves at every leaf is too expensive in Python — for less strength than
  the search depth it cost.
- **Delta pruning in quiescence.** Skipped captures that mattered, so the
  engine evaluated positions as quiet when material was still hanging.
  Removed; it was a genuine source of blunders.
- **Opening book.** Deliberately rejected — see Randomness above.

### The bug that mattered

For most of the build, the bot played nonsense — hanging queens, moving
in 1 second when it should take 15. The cause was in the *root search*:
`select()` narrowed alpha across root moves, so every move after the
first returned a fail-low **bound** rather than its true score. Those
bogus values tied with the best and were picked at random — meaning the
bot was effectively choosing a random move from a pool of garbage scores.
Every root move must be searched with a **full window**. Fixed; the
symptom (fast moves + random blunders) is worth recognising if it ever
returns.

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
| Bot plays weakly / low accuracy | Raise depth (`switch.sh depth 4`, classical only). If it moves in ~1s AND blunders, that is the root-window bug — see "The bug that mattered" |
| Bot moves suspiciously fast | Depth 3 should take ~15s in a middlegame. Instant moves mean the search is not running — check the engine file actually deployed (`./deploy.sh`) |
| `RateLimitedError` in the log | Too many restarts. The retry loop itself re-triggers the limit, so it may not clear on its own: `pkill -9 -f lichess-bot.py; tmux kill-server`, wait 5 min with NOTHING running, then `startbot.sh`. Note switch.sh no longer restarts, so this should now be rare |
| Personality change didn't take | It applies to the NEXT game, not the current one. Check `cat lichess-bot/engine_personality.txt` |
| Bot plays the same moves every game | `RANDOM_MARGIN` is 0 for that personality — set it to 0.25 |

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
