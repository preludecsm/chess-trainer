# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personality-based chess engine that plays as **MickTrainerBot** on Lichess, built as a "homemade" engine plugged into [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot). Instead of one engine at variable strength, it offers several personalities, each a deliberate, exploitable evaluation bias (a queen that wanders, pawns that storm, a bot that always fianchettoes) at an independently adjustable search depth. Runs on a Mac mini, controlled remotely over SSH/Tailscale.

Built for Mick (~900 Lichess rapid). Depth 3 is currently at the frontier of his ability — that's the target, not a limitation to fix. His identified weakness from game review: he plays quiet developing/retreating moves in sharp positions instead of calculating forcing lines (skips "what are my opponent's checks, captures, threats?"). Personalities exist to create exploitable, legible positions that punish exactly that habit.

[NOTES.md](NOTES.md) is the full design log this file summarizes — read it for anything not covered below (tuning history, performance tables, drafted future work).

## Repository layout

Only two Python files and the shell scripts are tracked here; `lichess-bot/` is an untracked upstream clone (`.gitignore`d) that the bot actually runs from.

- `personality_bots.py` — canonical copy of the engine core and all personalities.
- `homemade_personalities.py` — canonical copy of the lichess-bot adapter.
- `deploy.sh` — copies both files into `lichess-bot/`. Does **not** restart the bot.
- `switch.sh` — writes `engine_personality.txt` / `engine_depth.txt` inside `lichess-bot/`, read at the start of the bot's next game. No restart needed.
- `startbot.sh` — idempotent: starts the bot in a tmux session (`chessbot`) if it isn't already running.
- `restartbot.sh` — full stop/wait/start cycle, needed only after deploying code changes or editing `config.yml`.
- `lichess-bot/` — untracked upstream clone. `config.yml` (has the API token), `engine_personality.txt`, `engine_depth.txt`, and `venv/` all live here and are not versioned by this repo.

## Commands

```bash
./switch.sh Fianchetto depth 3   # change personality/depth — live, no restart
./switch.sh                       # print usage + current personality/depth
./deploy.sh                       # copy personality_bots.py + homemade_personalities.py into lichess-bot/
./restartbot.sh                   # full restart — required after ./deploy.sh or editing lichess-bot/config.yml
./startbot.sh                     # start the bot only if it isn't already running
```

Tests live under `lichess-bot/test_bot/` (upstream lichess-bot's own suite, e.g. `test_bot.py`, `test_homemade.py` equivalents) and run with the project's `venv`:

```bash
cd lichess-bot && source venv/bin/activate && pytest test_bot/
```

There is no test suite for `personality_bots.py` itself — verification is behavioral (see "Verifying an engine change" below).

## Critical workflow rule: which script for which change

| Change | Procedure |
|---|---|
| Personality or depth only | `./switch.sh <Personality> depth <N>` — takes effect next game, **no restart** |
| Engine code (`personality_bots.py`, `homemade_personalities.py`) | `./deploy.sh` **then** `./restartbot.sh` — Python has already imported the old module into the running process, so deploy alone does nothing observable |
| `lichess-bot/config.yml` (greeting, time controls, allow_list) | edit directly, then `./restartbot.sh` — only read at startup |

**`deploy.sh` alone is not enough for code changes** — this has silently shipped stale engines twice in this project's history. Always follow a code deploy with a restart.

**Restarts are expensive**: Lichess rate-limits reconnects to the event stream. `restartbot.sh` deliberately waits 60s with nothing connected before starting, which is what clears the limit — batch changes and restart once rather than iterating live. If the bot gets stuck in a rate-limit loop: `pkill -9 -f lichess-bot.py; tmux kill-server`, then wait 5+ minutes before starting anything.

**Verification discipline**: this project has a real commit named "Actually deploy quiescence engine" — from a multi-command paste where step 1 (deploy) failed silently and steps 2+ (restart, play) ran anyway against the stale binary. Run a check, read its output, *then* run the action that depends on it — don't chain deploy→restart→test as one unverified block. The decisive check that the deployed engine is actually live is behavioral, not textual: e.g. does Fianchetto actually open 1...b6 or 1...g6? A `grep` on the source file only proves the file on disk changed, not what the running process is executing.

**Re-applying the upstream patch**: `lichess-bot/lib/lichess_bot.py` has an upstream bug (`KeyError: 'game'` in `check_in_on_correspondence_games`) patched locally. Because `lichess-bot/` is untracked, any `git pull` inside it wipes the patch — reapply after every upstream pull:
```bash
sed -i '' 's/opponent_name = event\["game"\]/opponent_name = event.get("game", {})/' lib/lichess_bot.py
```
Currently low-stakes (correspondence games are declined in config), but will bite silently if that config ever changes.

## Architecture

- **Engine core** (`personality_bots.py`): negamax with alpha-beta pruning, MVV-LVA move ordering, and quiescence search that resolves captures before evaluating a leaf (this is what stops material-hanging blunders). Evaluation covers material, piece-square tables, pawn structure (doubled/isolated/passed), king safety (tapered middlegame→endgame), and the bishop pair.
- **Personality layer**: each personality subclasses the shared search (`SearchingPersonality` → `FourPlyBot` → `PersonalityBot`) and adds a *small* bias term to the shared evaluation, so style emerges from search rather than an opening book — the bot will pursue its style into positions where that's objectively bad, which is what makes it punishable. `RANDOM_MARGIN` on each personality picks randomly among root moves within that many pawns of the best, so games don't follow a repeatable script.
- **Adapter** (`homemade_personalities.py`): a single `Personality(MinimalEngine)` class registered with lichess-bot. Its `search()` re-reads `engine_personality.txt`/`engine_depth.txt` at the start of every game (`board.fullmove_number <= 1`) and lazily rebuilds the underlying bot from the `PERSONALITIES` dict — this is what lets `switch.sh` change behavior without a process restart. Mid-game changes are deliberately ignored.
- **Adding a personality**: add a subclass in `personality_bots.py`, register it in the `PERSONALITIES` dict in `homemade_personalities.py`, and add its name to the `VALID` list in `switch.sh`. `switch.sh`'s valid-name list is hardcoded rather than derived from the deployed adapter — an earlier version grepped it out and silently broke whenever the deployed copy went stale.

## Design constraints

- **No opening book, ever** — considered and rejected. A book would make the bot play a memorized line correctly for 12 moves and teach nothing about *why*; an evaluation bias makes the bot pursue its style into positions where that's a bad idea, which is what makes it punishable over the board.
- **Bias weights should be caricatures, not subtleties.** Fianchetto's weight started at 0.25 and only fianchettoed about half the time — unreliable, teaches nothing. At 1.00 it plays 1...b6 or 1...g6 *every* game for about half a pawn of cost. That's correct: the weakness has to be visible to be punishable.
- **The horizon problem**: if a personality isn't expressing its style, check whether the reward is beyond the search horizon at the configured depth *before* assuming the weight is too low. Fianchetto originally only scored the bishop once it reached g7, but reaching g7 takes two moves (g6, then Bg7) that a depth-3 search can't see the payoff for from further away — the fix was to reward the preparatory pawn move itself, separately.
- **Bad proxies produce dead weights**: WanderingQueen originally rewarded raw distance from d1/d8, so a queen sitting inert on a8 scored well. Fixed by adding a centralization term so drifting the queen out is actually what gets rewarded.
- **RANDOM_MARGIN** (0.25 for the four "serious" personalities, 0.75 for SafeRandom) makes the bot pick randomly among root moves within that many pawns of the best score. This is deliberate — a fully deterministic opponent can be memorized, and that's explicitly not wanted here.

## Failed experiments — do not re-attempt without new evidence

These looked like reasonable engine improvements and were tried, measured, and rejected. Re-litigating them from first principles wastes a cycle; the measurements already exist.

- **Transposition table**: 9.2% hit rate, net *slower*. The TT key includes depth, so a depth-2 entry can't serve a depth-3 probe — hashing/storing ~14k positions cost more than it saved. A TT only pays off alongside **iterative deepening** (depth 1, 2, 3… reusing the table and prior best-move for ordering); that's the correct next performance project, and only worth it if depth 4+ becomes necessary.
- **Mobility term in evaluation** (bonus per legal move): profiling showed it consumed **65% of total evaluation time**. Generating legal moves at every leaf is too expensive in Python for what it buys in strength.
- **Delta pruning in quiescence search**: skipped captures that actually mattered, so the engine evaluated positions as quiet while material was still hanging — a genuine, confirmed source of blunders. Removed.

## The root-search bug (recognize this signature)

For most of this project's early build, the bot played nonsense: hanging queens, moving in ~1 second when it should have taken 15+. Root cause: `select()` narrowed alpha across root moves during the loop, so every root move *after the first* returned a fail-low **bound** rather than its true score. Those bogus bound values tied with the real best score and got chosen at random — the bot was effectively selecting a random move from a pool of garbage scores, and doing it fast because bounds short-circuit search.

**Every root move must be searched with a full window** (this is what the `# FULL window` comment in `personality_bots.py` marks). If the bot ever starts moving suspiciously fast *and* blundering at the same time, check the root search loop for this exact pattern first — it's a narrow-search-window bug, not an evaluation bug.

## Verifying an engine change

There's no automated test for personality behavior; verification is a real game plus targeted greps (checks, not proof — see "Verification discipline" above):

```bash
grep -c 'class Personality' homemade_personalities.py   # 1 = live-switch adapter present
grep -c 'FULL window' personality_bots.py                # 1 = root-search fix still present
grep -c 'Delta pruning' personality_bots.py               # 0 = correctly stays removed
```

Then play the personality against `Beginner` for ~20 moves and check material: within ±2 pawns of even means the bias is working as intended (biased, not broken); a larger swing means the bias is too strong or there's a bug. The decisive check is always behavioral, per the verification-discipline note above — a grep only proves the file changed, not what the running process is executing.
