# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personality-based chess trainer: one Python engine core (`personality_bots.py`) with five personalities, each a deliberate, exploitable evaluation bias, played through a **local browser UI** (`web_trainer/`) with a live Stockfish eval sidebar. Built for Mick (~900 Lichess rapid); depth 3 is calibrated to the frontier of his ability — that's the target, not a limitation to fix.

**As of 2026-07-19 the original Lichess deployment is decommissioned.** The lichess-bot process, LaunchAgent, and PATH symlinks are disabled (reversible — see README's Legacy section). `homemade_personalities.py`, the four shell scripts, and the untracked `lichess-bot/` clone are dormant but kept. A public AWS deployment is planned — see MIGRATION.md.

**Read [NOTES.md](NOTES.md) before changing the engine.** It documents experiments already tried, measured, and rejected (transposition table, mobility eval, delta pruning), the root-search bug signature, and tuning lessons (horizon problem, bad proxies, weak weights) that are not recoverable from the code.

## Commands

```bash
./web_trainer/run.sh                 # start the trainer → http://localhost:5001
pkill -f "python3 server.py"         # stop it (needed before restarting)
```

There is no test suite; verification is behavioral (see below). The web trainer's venv lives at `web_trainer/venv/` (flask + chess); Stockfish is the Homebrew binary at `/opt/homebrew/bin/stockfish`.

## The one critical workflow rule

**Python caches imported modules.** A running `server.py` keeps executing the old engine no matter what's on disk. After any `personality_bots.py` edit: kill and restart the server, then verify behaviorally. `static/index.html` edits need only a browser hard-refresh. This trap has bitten this project three times across two interfaces — assume any "my change didn't take effect" symptom is this first.

## Architecture

- **`personality_bots.py`** — single source of truth for the engine. `FourPlyBot` is the core: negamax + alpha-beta, MVV-LVA ordering, quiescence search (resolves captures before evaluating — this is what prevents material blunders). Evaluation: material, PSTs, pawn structure, tapered king safety, bishop pair. `SearchingPersonality` adds a per-personality `style_for(board, color)` evaluation bias; `RANDOM_MARGIN` picks randomly among root moves within that many pawns of best (deliberate — a deterministic opponent can be memorized).
- **`web_trainer/server.py`** — Flask, binds 127.0.0.1:5001. Stateless API: the client sends FEN with every request (`/api/eval` → Stockfish MultiPV-2 analysis; `/api/bot-move` → personality engine move; `/api/config` → deployment limits, so the UI reflects them instead of clamping silently; `/api/speak` → TTS audio for move announcements, see below). One shared Stockfish process, started at server startup. `FIXED_DEPTH` env var (set on the hosted deploy) forces every move to search to exactly that depth, ignoring the client's requested depth entirely — no cap-with-fallback. A time-budget-based fallback was tried and reverted 2026-07-20; see NOTES.md.
- **`web_trainer/static/index.html`** — the whole UI in one file: chessboard.js board (click-to-move + drag), eval bar, top-2 moves, post-move cost feedback, takeback, move-history navigation, and a per-game move-quality histogram (centipawn loss vs. Stockfish's top line, bucketed, human moves vs. bot moves). Note: chessboard.js has no click hook — clicks on own pieces arrive via `onDrop` with `source === target`; clicks on empty/enemy squares via a delegated jQuery listener. `onDrop` must return synchronously (`'snapback'`), so move side-effects run in a fire-and-forget `afterMove()`. The histogram reuses eval fetches `afterMove`/`maybeBotMove` already make (no extra Stockfish calls) via a generalized `moveCost()`; its `moveCosts` array is truncated wherever `game.history()` itself is truncated (takeback, branching) but is deliberately untouched by `jumpToPly` (browsing history shouldn't change a whole-game summary).
- **Adding a personality**: subclass `SearchingPersonality`, override `style_for`, register in `server.py`'s `PERSONALITIES` dict, add to the dropdown in `index.html`, restart the server.
- **Move-announcement TTS (2026-10-06)**: `index.html`'s `sanToSpeech()` converts a SAN move to plain English, then `speakMove()` tries the server first (`POST /api/speak`, which shells out to macOS's `say -v "Ava (Premium)"` and returns an `.m4a` clip) before falling back to the browser's own `speechSynthesis` + voice picker. Reason it has to work this way: iOS Safari's Web Speech API never exposes a downloaded Enhanced/Premium system voice to web pages at all — a known WebKit limitation, confirmed independent of browser (Safari/Chrome/Firefox on iOS all share it) — so the only way to get a good voice onto an iPad from a web page is to synthesize it somewhere `say` can actually reach a real voice (this Mac) and just ship audio. `/api/speak` is macOS-only (`SAY_PATH` is `None` on the Linux-hosted deploy) and 501s cleanly when absent; the client caches that and stops asking for the rest of the session. A manual `speechQueue` promise chain on the client keeps announcements in play order (human move, then bot's reply) since `fetch`+`Audio` doesn't queue the way `speechSynthesis.speak()` does on its own.

## Design constraints (rationale in NOTES.md)

- **No opening book, ever** — considered and rejected; bias-in-evaluation is the point.
- **Bias weights are caricatures, not subtleties** — a style that shows up half the time teaches nothing. Fianchetto's weight went 0.25 → 1.00 before it committed every game; PawnStorm's went 0.05 → 0.2.
- **Tuning check**: play the personality vs Beginner ~20 moves; within ±2 pawns of even = biased, not broken.
- **Tuning traps**: if a style isn't expressing, check (1) reward beyond the search horizon at depth 3, (2) bad proxy — e.g. PawnStorm targeting the *uncastled* king's home square rewarded central pawns, the exact opposite of a storm.

## Failed experiments — do not re-attempt without new evidence

- **Transposition table**: 9.2% hit rate, net slower (depth-keyed entries don't cross-serve). Only worthwhile with iterative deepening, and only if depth 4+ ever becomes necessary.
- **Mobility eval term**: 65% of total evaluation time in profiling. Too expensive in Python.
- **Delta pruning in quiescence**: caused real blunders (skipped captures that mattered). Removed.

## The root-search bug (recognize the signature)

Early on, the bot hung queens while moving suspiciously fast. Cause: the root loop narrowed alpha, so every root move after the first returned a fail-low *bound* that tied with the best score, and moves were picked randomly from garbage. **Every root move gets a full window** (the `FULL window` comment in `select()` marks it). Fast moves + blunders together = check this first.

## Verifying an engine change

No automated tests; verify behaviorally against the running server:

```bash
curl -s -X POST http://localhost:5001/api/bot-move -H "Content-Type: application/json" \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1","personality":"Fianchetto","depth":3}'
# Fianchetto at depth 3 must answer 1.e4 with g6 or b6 — its signature.
# PawnStorm should storm (g5/h5-type pushes), never settle into 1...d5.
```

A grep proves the file changed; only a move proves the running process changed. Sample repeatedly — `RANDOM_MARGIN` means single moves vary.

**A personality verified at one depth is not verified at another.** Root
scores, not sampled moves, are the real check — a bad move can sit at
the top of the candidate set and just not get sampled in a handful of
tries (this is exactly how the depth-4 Fianchetto regression and the
original PawnStorm symmetric-bias bug both surfaced):

```python
bot = FianchettoSearchBot(depth=4)
scores = bot._root_scores(board)          # {move: score}, full window, every root move
best = max(scores.values())
for m, s in sorted(scores.items(), key=lambda kv: -kv[1]):
    print(board.san(m), s, "IN MARGIN" if s >= best - bot.RANDOM_MARGIN else "")
```

Any move tagged IN MARGIN can get picked by `RANDOM_MARGIN`; if that set
includes the personality's anti-move (d5 for PawnStorm, a non-g6/b6 for
Fianchetto), the weight needs work — regardless of how the sampled
`select()` calls happened to land.

## Security / deployment notes

- `lichess-bot/config.yml` holds a live Lichess API token (untracked; revoke if the Lichess path stays dead).
- `server.py` must stay on 127.0.0.1 until the hardening in MIGRATION.md lands (FEN validation, depth clamp, engine-crash recovery, rate limiting).
- **`/api/speak` shells out to `say`** via `subprocess.run` with a list of arguments (never `shell=True`), so client-supplied text can't be interpreted as a shell command regardless of content; a `[A-Za-z0-9 ,.'-]{1,120}` allowlist regex on top is defense-in-depth, not the actual injection guard. Same 127.0.0.1-until-hardened caveat as the rest of the API if this ever goes public — this endpoint has no rate limiting of its own yet.
- **Lichess failover constraint**: if the dormant `lichess-bot` is ever revived on a failover host, that host and the Mac's own instance must never connect the same Lichess account at once — a second simultaneous connection abandons/loses whatever game the first one had in progress.
- **2026-08-26/27 credential incident**: the `chesstrainer` deploy IAM user's access key was exposed in a leaked dotfiles backup and has been deleted. Verified 2026-08-28: the local default AWS profile is currently dead (`InvalidClientTokenId`/`AuthFailure` on every call) — the redeploy path in MIGRATION.md is blocked until a new credential is provisioned (prefer an instance role over another stored access key). The `chess-trainer-key.pem` SSH key was exposed too; once AWS access is restored, check both us-west-1 and us-west-2 (the EC2 instance's `authorized_keys` and each region's EC2 Key Pairs list) for anything still trusting it.
