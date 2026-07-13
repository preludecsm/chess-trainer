# NOTES — context for anyone (human or AI) picking this project up

This file exists because the *reasons* behind the design are not obvious
from the code, and several plausible-looking "improvements" have already
been tried and rejected with measurements. Read this before changing the
engine.

---

## Who this is for

Mick, ~900 Lichess rapid, ~400 blitz. **The bot is calibrated to be a
real contest for a ~900 player.** Depth 3 is currently at the frontier of
his ability — he wins some, loses some. That is the target. A stronger
bot is *not* better; the point is a trainable opponent, not an oracle.

His identified weakness (from game analysis): he plays quiet developing
or retreating moves in sharp positions instead of calculating forcing
lines. Specifically he skips the "what are my opponent's checks,
captures, and threats?" step. Several games have been lost from winning
positions this way.

---

## The core design idea

Each personality is a **bias in the evaluation function**, not an opening
book. This is deliberate and load-bearing:

- A book would make the bot play a memorized line correctly for 12 moves
  and teach nothing about *why*.
- An evaluation bias makes the bot pursue its style **into positions
  where it is a bad idea** — which is exactly what makes it punishable
  over the board.

**Do not add an opening book.** This was considered and rejected.

Corollary: **a caricature beats a subtlety.** The Fianchetto weights were
originally 0.25, and it fianchettoed maybe half the time — which teaches
nothing reliably. At 1.00 it plays 1...b6 or 1...g6 *every game*, at a
cost of about half a pawn. That is correct. The weakness must be visible
to be punishable.

---

## Workflow — read this carefully

Three different kinds of change, three different procedures:

| Change | What to do |
|---|---|
| **Personality or depth** | `switch.sh Fianchetto depth 3` — writes two text files, read at the start of the next game. **No restart.** |
| **Engine code** (personality_bots.py, homemade_personalities.py) | `./deploy.sh` **then `restartbot.sh`** — Python caches imported modules in memory, so a running bot keeps executing the old code until the process restarts. |
| **config.yml** (greeting, time controls, allow_list) | Edit directly, then `restartbot.sh` — read only at startup. |

**The trap:** `deploy.sh` alone is not enough for code changes. It copies
the file, but the running process has already imported the old module.
This bit us twice — the bot kept playing the old engine while every grep
said the new file was in place.

**Restarts are expensive.** Lichess rate-limits reconnections to
`/api/stream/event` per token. Several restarts in quick succession locks
the bot out for many minutes, and the retry loop can re-arm the limit so
it does not clear on its own. `restartbot.sh` waits 60 s with nothing
connected, which is what actually clears it. **Batch your changes and
restart once.** If it gets stuck: `pkill -9 -f lichess-bot.py; tmux
kill-server`, then wait 5+ minutes with nothing running.

---

## What's been tried and rejected (with measurements)

**Transposition table** — 9.2% hit rate, net *slower*. The TT key
includes depth, so entries from a depth-2 search do not serve a depth-3
probe, and hashing/storing 14k positions cost more than it saved. A TT
only pays off alongside **iterative deepening** (search depth 1, 2, 3…
reusing the table and the previous iteration's best move for ordering).
That is the correct next performance project if depth 4+ is ever needed.

**Mobility term in the evaluation** (bonus per legal move) — profiling
showed it consumed **65% of total evaluation time**. Generating legal
moves at every leaf is too expensive in Python for the strength it buys.

**Delta pruning in quiescence** — skipped captures that mattered, so the
engine evaluated positions as quiet while material was still hanging. A
genuine source of blunders. Removed.

---

## The bug that mattered (recognise this signature)

For most of the build the bot played nonsense — hanging queens, moving in
1 second when it should take 15. The cause was in the **root search**:
`select()` narrowed alpha across root moves, so every move after the
first returned a fail-low **bound** rather than its true score. Those
bogus values tied with the best and got picked at random. The bot was
literally choosing a random move from a pool of garbage scores.

**Every root move must be searched with a full window.** If the bot ever
starts moving suspiciously fast *and* blundering, check this first.

---

## Current performance (Mac mini, middlegame positions)

| Depth | Think/move | Notes |
|---|---|---|
| 2 | ~1 s | weak but instant |
| 3 | ~15–20 s | **the recommended setting** — at Mick's level |
| 4 | ~80–135 s | classical time controls only |
| 5+ | minutes | impractical without iterative deepening |

Think time varies a lot with position — simplified positions are much
faster than cluttered middlegames. Depth 3 has felt closer to 3–6 s in
real games.

---

## Tuning style weights

Two lessons, both learned the hard way:

**The horizon problem.** Fianchetto originally only scored the bishop
*once it reached* g7. But getting there takes g6, then Bg7 — and at depth
3 the engine cannot see that payoff from far enough away to start the
journey. The fix was to reward the **preparatory pawn move** on its own.
If a personality is not expressing itself, ask whether the reward is
beyond its search horizon before assuming the weight is too low.

**Bad proxies.** WanderingQueen originally rewarded raw distance from
d1/d8 — so a queen on a8 scored well while doing nothing. Adding a
centralization term made the bias unmistakable.

**Sanity check when tuning:** play the personality against Beginner for
20 moves and check material. **Within ±2 pawns of even = biased, not
broken.** It should pay a small price for its obsession, not collapse.

---

## Randomness

`RANDOM_MARGIN` (0.25 for the four "serious" personalities, 0.75 for
SafeRandom) picks randomly among root moves within that many pawns of the
best. This keeps repeated games from following the same script without
making the bot play badly. Mick explicitly does **not** want a
deterministic opponent — he wants it to vary so it cannot be memorized.

---

## Verification discipline

A recurring failure mode in this project: pasting a multi-command block
where step 1 fails silently and steps 2–4 run anyway. There is a commit
literally named "Actually deploy quiescence engine" that deployed nothing.

**Run the check, read the output, then run the action.** Useful greps:

```bash
grep -c 'bishop in the nest' personality_bots.py   # 1 = Fianchetto cranked
grep -c 'FULL window' personality_bots.py          # 1 = root search fixed
grep -c 'Delta pruning' personality_bots.py        # 0 = correctly removed
grep -c '_pawn_structure' personality_bots.py      # 2 = eval upgrade present
grep -c 'class Personality' homemade_personalities.py  # 1 = live-switch adapter
```

And the decisive one: **does Fianchetto open with 1...b6 or 1...g6?** If
not, the deployed engine is stale regardless of what the greps say.

---

## Upstream patch (re-apply after any `git pull` in lichess-bot/)

lichess-bot has a bug: `KeyError: 'game'` in
`check_in_on_correspondence_games`. Fixed with:

```bash
sed -i '' 's/opponent_name = event\["game"\]/opponent_name = event.get("game", {})/' lib/lichess_bot.py
```

(Currently moot — correspondence games are declined — but it will bite if
that ever changes.)

---

## Ideas not yet built

- **Iterative deepening + TT + killer moves** — the real performance fix.
  Would make depth 5–6 practical. Worth doing *only* when depth 3 stops
  beating him.
- **More eval knowledge** — rook on open files, outposts, passed-pawn
  blockades.
- **New personalities** — Simplifier (trades when ahead), Hypermodern.
- A **Reddit post** for r/chessbeginners is drafted but waiting on a game
  where he actually punishes the fianchetto structure rather than winning
  on a blunder.
