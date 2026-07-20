# MickTrainerBot — Personality Chess Trainer

A chess sparring partner with *deliberate, exploitable biases* — a queen
that wanders, pawns that storm, a player who never blunders but has no
plan — at adjustable calculation depth. Played in the browser against a
local server, with live Stockfish feedback after every move.

> **Status (2026-07-19):** the original Lichess deployment is
> **decommissioned** — the bot process, its LaunchAgent, and its PATH
> symlinks are disabled. The browser trainer (`web_trainer/`) is now the
> primary interface. See [Legacy: Lichess deployment](#legacy-lichess-deployment-decommissioned)
> for what remains and how to reactivate it. A public multi-user AWS
> deployment is planned — see [MIGRATION.md](MIGRATION.md).

> **Working on this project?** Read [NOTES.md](NOTES.md) first — it has the
> design rationale, the experiments that were tried and measured and
> rejected (transposition table, mobility eval, delta pruning), the bug
> signatures worth recognising, and the workflow traps. The code does not
> explain *why*, and several plausible "improvements" have already been
> disproven with numbers.

> **Personal project.** Paths and hardware (a Mac mini under
> `~/Documents/Mick/Chess`) are mine. Adaptable, but expect to substitute
> your own paths. Shared as-is; no support implied.

## Repository layout

```
Chess/                      <- this repo
├── README.md               <- this file
├── NOTES.md                <- design rationale + failed experiments: read first
├── personality_bots.py     <- the engine & personalities (single source of truth)
├── web_trainer/            <- THE ACTIVE INTERFACE: local browser trainer
│   ├── server.py            <- Flask app: bot moves + Stockfish eval
│   ├── static/index.html    <- board UI + eval sidebar
│   ├── run.sh                <- start it: http://localhost:5001
│   └── venv/                 <- python environment (not tracked)
├── homemade_personalities.py  <- LEGACY: lichess-bot adapter (dormant)
├── switch.sh / startbot.sh / restartbot.sh / deploy.sh  <- LEGACY: Lichess controls
└── lichess-bot/            <- LEGACY: upstream clone, not tracked (.gitignore)
    └── config.yml          <- SENSITIVE: still contains the API token
```

## Purpose

Commercial engines are either too strong or artificially weakened in
unsatisfying ways. This trainer offers opponents whose weaknesses are
*designed in and legible*: each personality pursues its obsession into
positions where that is a bad idea, which is exactly what makes it
punishable — and instructive — over the board.

## The trainer (`web_trainer/`)

Run `./web_trainer/run.sh` and open `http://localhost:5001`. A plain
Flask server plus one static HTML page — no build step, no Node, no
account, no network dependency on any chess site. Start it when you want
to play; `Ctrl-C` when done.

- **Board**: click-to-move (click a piece, then a destination; legal
  moves are dotted) or drag-and-drop.
- **Live feedback**: a Stockfish eval bar and top-2 engine moves, via a
  native Stockfish binary (`brew install stockfish`) driven over UCI by
  `python-chess`. After each of your moves, a line shows how many pawns
  it cost relative to the engine's top choice.
- **Take Back** undoes your last full exchange. **⏮ ◀ ▶ ⏭** step
  through the game history (board is read-only while reviewing).
- Personality and depth are per-game dropdowns in the UI.
- **No deploy step, but restarts matter**: `server.py` imports
  `personality_bots.py` at startup. `index.html` changes are live on
  refresh; **engine changes need the server restarted** — Python caches
  imported modules (see NOTES.md, this has bitten twice).

## Engine architecture (`personality_bots.py`)

All personalities share one engine core: negamax with alpha-beta,
MVV-LVA move ordering, and a quiescence search that resolves captures
before evaluating (this is what stops it blundering material
mid-exchange). The evaluation knows material, piece-square tables, pawn
structure (doubled / isolated / passed), king safety, and the bishop
pair, with the king's table tapered between middlegame and endgame.

Each personality then adds a *small* bias to that evaluation — so style
emerges from search, not from a book, and the bot will happily pursue
its style into positions where that's a bad idea. That is the point: the
weakness is legible and punishable.

## Personalities

| Name | Style | Margin | Trains you on |
|---|---|---|---|
| **Beginner** | No stylistic bias — plain positional search | 0.25 | Clean baseline opponent at any depth |
| **SafeRandom** | Random among all moves within ¾ pawn of best: never blunders within its horizon, never has a plan | 0.75 | Punishing planlessness; converting small edges |
| **WanderingQueen** | Brings the queen out early and keeps her roaming — rewards distance from home *and* centralization | 0.25 | Punishing early queen sorties with tempo |
| **PawnStorm** | Values pawns advanced toward your king, summed across all pawns | 0.25 | Defending pawn storms; counterplay in the centre while it commits on the wing |
| **Fianchetto** | Wants a bishop nested on g2/b2 (g7/b7) behind its pawn, and clings to it | 0.25 | Trade off the fianchetto bishop, then occupy the dark squares it was guarding |

### Tuning the style weights

Lessons from getting these to actually show up in games:

**The horizon problem.** Fianchetto originally only scored the bishop
*once it reached* g7. But getting there takes g6, then Bg7 — and at
depth 3 the engine cannot see that payoff from far enough away to start
the journey. It fianchettoed in only 3 of 6 games. The fix was to reward
the **preparatory pawn move** on its own (g6/b6 earns a bonus even before
the bishop arrives). Now it commits in 5 of 6 games and will sometimes
open 1...b6. If a personality isn't expressing itself, ask whether the
reward is beyond its search horizon before assuming the weight is too low.

The same horizon problem resurfaced when depth 4 became practical
(iterative deepening + TT, below): the deeper search sees more of
central play's real value, which shrank Fianchetto's g6/b6-vs-d5 margin
from a safe 0.55 pawns to 0.15 — inside the random margin. Doubling the
preparatory/nest bonuses restored a 0.50 gap at depth 4 without
disturbing depth 3. Full numbers and the pruning-sensitivity surprise
(the fix needed 2×, not the ~1.4× the arithmetic suggested) are in
NOTES.md. **Lesson: a personality tuned at one depth isn't verified at
another — check root scores again before trusting a new depth cap.**

**Bad proxies.** WanderingQueen originally rewarded raw distance from
d1/d8, which meant a queen on a8 scored well while doing nothing. Adding
a centralization term made the bias unmistakable — it now plays 2...Qd6
and keeps her roaming, which costs it about two pawns a game. That is the
punishable price the trainer needs.

**Weak weights hide in plain sight.** PawnStorm's per-pawn coefficient
had sat at 0.05 since it was written, on the assumption that summing
across all eight pawns would make it accumulate fast enough on its own.
A real game showed otherwise — no storming, just book opening theory,
because a two-square opening push only nets ~0.20 pawns of bonus at that
weight. Bumped to 0.2 (same 4x ratio as the Fianchetto fix above), which
brings an early push's bonus to ~0.8 pawns. Lesson: a formula that *looks*
like it should compound into a visible bias still needs checking against
a real game, not just the math.

**The weight bump wasn't the whole bug.** Even at 0.2, PawnStorm as Black
kept opening 1...d5 (Scandinavian). The formula measured file-distance
from the enemy king's *current* square, which before castling is still
e1/e8 — central. That rewarded central pushes (d5/e5) over real flank
storms (f5/g5/h5), exactly backwards. Fixed by assuming kingside
castling (the common case) as the target file until the enemy king
actually moves off its home square. Confirmed: it now plays g5/h5-type
pushes instead of d5, with material still in the normal ±2 pawn range.
A proximity-to-a-square bias needs to ask which square is actually
meaningful yet — pointing at a square nobody's committed to can send the
incentive the wrong way, not just weaken it.

Sanity check when tuning: play the personality against Beginner for 20
moves and check material. **Within ±2 pawns of even means biased, not
broken** — it should pay a small price for its obsession, not collapse.

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

## Strength (depth)

Depth 1–8, shared by all personalities. Think time grows steeply — this
is Python, and there is no transposition table (one was tried; see
"What didn't work"). Measured on a Mac mini, middlegame positions:

| Depth | Think/move (middlegame) | Practical use |
|---|---|---|
| 2 | ~1 s | weak but instant |
| 3 (recommended) | ~15–20 s | the sweet spot |
| 4 | ~80–135 s | patience required |
| 5+ | many minutes | impractical |

**Depth 3 is the recommendation** — currently at the frontier of the
target player's ability, which is the point.

## Extending

Add a personality: subclass `SearchingPersonality` in
`personality_bots.py` and override `style_for(board, color)` — a small
positional score for how well the position suits the personality. Keep
bonuses in *tenths* of a pawn (then expect to crank them — see the
tuning lessons), set `RANDOM_MARGIN` (0.25 is the house default), add it
to the `PERSONALITIES` dict in `web_trainer/server.py` and the dropdown
in `static/index.html`, and restart the server.

Ideas: Simplifier (trades when ahead), Hypermodern (central control from
a distance).

## What didn't work (and why)

Recorded so they aren't retried blindly:

- **Bare transposition table** (no iterative deepening). Added, measured,
  removed. Hit rate was only 9.2% — the TT key includes depth, so entries
  from a depth-2 search don't serve a depth-3 probe, and it cost more to
  hash and store 14k positions than it saved. *The full ID+TT combination
  landed 2026-07-20 and does pay: depth 4 is 1.6× faster (~13s/move
  locally under PyPy), depth 3 unchanged. Details in NOTES.md.*
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

## Troubleshooting (web trainer)

| Symptom | Cause / fix |
|---|---|
| Blank page on localhost:5000 | Wrong port — the trainer is on **5001** (macOS AirPlay squats on 5000) |
| Board area empty, sidebar renders | JS error — check the browser console; the page needs its vendored scripts |
| Engine change didn't take | Server started before the edit — Python caches modules; restart `server.py` |
| "Address already in use" on start | A previous server instance is still running. Note the venv process shows as `Python server.py`, so `pkill -f "python3 server.py"` silently misses it — use `pkill -f "server.py"` |
| Every eval fails after one bad request | The shared Stockfish process died — restart the server |
| Bot plays the same moves every game | `RANDOM_MARGIN` is 0 for that personality — set it to 0.25 |
| Moves instant AND bad | Root-window bug signature — see "The bug that mattered" |

## Legacy: Lichess deployment (decommissioned)

From 2026-07-06 to 2026-07-19 this project ran as a Lichess bot
(**MickTrainerBot**) via [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot),
controlled from an iPhone over Tailscale/SSH. It worked, but Lichess's
event-stream rate limiting repeatedly locked the bot out (one network
hiccup could cascade into a multi-minute lockout — root cause and fix in
NOTES.md), and the browser trainer made the whole pipeline unnecessary
for its actual purpose. Full runbook, install script, challenge policy,
and troubleshooting are in git history (README.md prior to 2026-07-19).

**What was disabled** (all reversible):

- The bot process and its `chessbot` tmux session — killed.
- `~/Library/LaunchAgents/com.mick.chessbot.plist` — unloaded and
  renamed to `.plist.disabled` (it restarted the bot at boot).
- `/opt/homebrew/bin` symlinks for `switch.sh`, `startbot.sh`,
  `restartbot.sh` — removed.
- The API token in `lichess-bot/config.yml` is **still live on disk** —
  revoke it at https://lichess.org/account/oauth/token if not returning.

**To reactivate**: rename the plist back and `launchctl load` it (or
just run `./startbot.sh`), re-create the symlinks if wanted, and re-check
the two upstream patches in NOTES.md against `lichess-bot/lib/` — a
`git pull` in `lichess-bot/` wipes them. The dormant pieces
(`homemade_personalities.py`, the four shell scripts) are still tracked
and functional. Remember the workflow trap: engine code changes need
`./deploy.sh` **and** a restart; `switch.sh` changes need neither.

## Security notes

- `lichess-bot/config.yml` contains the (still-valid) Lichess API token —
  the directory is .gitignored; never commit it, and revoke the token if
  the Lichess path stays dead.
- `web_trainer/server.py` binds to `127.0.0.1` only. Do not rebind to
  `0.0.0.0` without the hardening and rate limiting described in
  [MIGRATION.md](MIGRATION.md).

## Acknowledgments and license

Built on [python-chess](https://github.com/niklasf/python-chess) (move
generation and board logic) and [Stockfish](https://stockfishchess.org)
(analysis sidebar). The decommissioned Lichess deployment used
[lichess-bot](https://github.com/lichess-bot-devs/lichess-bot)
(AGPL-3.0, cloned separately, never bundled). Thanks to
[Lichess](https://lichess.org) for a free, open platform.

The code in this repository is released under the MIT License — see
[LICENSE](LICENSE).
