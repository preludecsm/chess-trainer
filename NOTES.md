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

## Status (2026-07-19): Lichess decommissioned, web trainer primary

The Lichess deployment is disabled (process killed, LaunchAgent renamed
to `.plist.disabled`, PATH symlinks removed — reactivation steps in
README's Legacy section). The active interface is `web_trainer/`. The
API token in `lichess-bot/config.yml` remains live on disk until revoked.

## Workflow — read this carefully

The one trap that spans every interface this project has ever had:
**Python caches imported modules in memory.** A running process keeps
executing the old engine no matter what the files on disk say.

| Change | What to do |
|---|---|
| **Engine code** (personality_bots.py) with web trainer running | Restart `web_trainer/server.py` (kill + `run.sh`). No deploy step — it imports the repo copy directly. |
| **index.html** (web trainer UI) | Nothing — served fresh from disk; hard-refresh the browser. |
| *(legacy)* Personality/depth on Lichess | `switch.sh Fianchetto depth 3` — two text files, read at next game start. No restart. |
| *(legacy)* Engine code on Lichess | `./deploy.sh` **then `restartbot.sh`**. |
| *(legacy)* config.yml | Edit, then `restartbot.sh` — read only at startup. |

**The trap:** `deploy.sh` alone is not enough for code changes. It copies
the file, but the running process has already imported the old module.
This bit us twice — the bot kept playing the old engine while every grep
said the new file was in place.

**Same trap, different process (2026-07-18):** `web_trainer/server.py`
imports `personality_bots.py` directly with no deploy step at all — but
that only means edits reach it *on the next process start*. A running
`server.py` has the old module cached exactly like the Lichess bot does.
Caught this live: edited PawnStorm's bias, tested in the browser, still
saw the old (buggy) behavior, because the server had been started before
the edit. Kill and restart `web_trainer`'s `server.py` (or just use
`run.sh`, which starts a fresh process each time) after any
`personality_bots.py` change, same discipline as `restartbot.sh` for the
Lichess side — just cheaper, since it's a local `kill` + relaunch, no
rate limit to wait out.

**Restarts are expensive.** Lichess rate-limits reconnections to
`/api/stream/event` per token. Several restarts in quick succession locks
the bot out for many minutes, and the retry loop can re-arm the limit so
it does not clear on its own. `restartbot.sh` waits 60 s with nothing
connected, which is what actually clears it. **Batch your changes and
restart once.** If it gets stuck: `pkill -9 -f lichess-bot.py; tmux
kill-server`, then wait 5+ minutes with nothing running.

---

## What's been tried and rejected (with measurements)

**Transposition table (bare, 2026-07)** — 9.2% hit rate, net *slower*.
The TT key includes depth, so entries from a depth-2 search do not serve
a depth-3 probe, and hashing/storing 14k positions cost more than it
saved. A TT only pays off alongside **iterative deepening**.
*Resolved 2026-07-20*: ID+TT landed (draft-based probing, bound flags,
TT-move-first ordering, root re-ordering by previous iteration). Measured
under PyPy: depth 3 a wash (3.45s vs 3.46s mean — shallow-pass overhead
cancels TT gains), **depth 4 1.6× faster** (41.9s → 26.7s over two
middlegames, ~13s/move mean), identical moves both depths. Known caveat:
`can_claim_draw()` is history-dependent, so repetition-tinted scores can
be cached — acceptable for a trainer, would matter for a real engine.

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

**Weak weights hide in plain sight.** PawnStorm's per-pawn coefficient
sat at `0.05` since it was first written, on the assumption that summing
across all eight pawns would make it accumulate fast enough on its own.
It didn't — a real game (2026-07-13) showed no storming at all, just
book opening theory, because a two-square opening push only nets ~0.20
pawns of bonus at that weight, too small to beat normal development at a
3-ply search. Bumped `0.05 → 0.2` (same 4x ratio as the Fianchetto fix)
to bring an early push's bonus to ~0.8 pawns. Unlike Fianchetto this bias
is incremental rather than a single-trigger reward, so it shouldn't have
a horizon problem — but it hadn't been checked against a real game before
now. Don't assume a bias is fine just because the formula looks like it
should compound; verify against an actual game.

**The weight bump wasn't the whole bug.** Even at `0.2`, PawnStorm as
Black kept playing 1...d5 (Scandinavian) against 1.e4 — a second, deeper
bad-proxy problem (2026-07-18). `style_for` measured file-distance from
the enemy king's *current* square, and before castling that's still e1/e8
— central. So the formula was rewarding central pawn pushes (d5/e5, small
file-gap from e) over actual flank storms (f5/g5/h5, large file-gap from
e) — backwards from the intended identity, and worse than useless before
the opponent commits to a side. Fixed by assuming kingside castling
(overwhelmingly the common case) as the target file whenever the enemy
king is still on its home square, falling through to the real king square
once it's moved. Confirmed fixed: Black now plays g5/h5-type pushes
instead of d5, and self-play material vs. Beginner stayed within the
usual ±2 pawn range. Lesson: proximity-to-a-square proxies need to ask
*which* square is meaningful at the point in the game the bias is
actually supposed to fire — a square that hasn't been committed to yet
(home-square king) can point the incentive the wrong way entirely,
not just weakly.

**Symmetric bias turns capturable opponent material into style targets
(2026-07-20).** Even after the king-target fix, PawnStorm kept playing
occasional 1...d5 Scandinavians — root-score dump showed d5 was its TOP
reply to 1.e4. Cause: the personality bias was applied symmetrically
(style_for(White) − style_for(Black)), so trading off White's advanced
e4 pawn scored as a style *gain* — the storm personality was picking the
anti-storm move. Fix: `SYMMETRIC_STYLE = False` on PawnStorm (new flag
on SearchingPersonality) so only its own pawns count. Symmetry stays the
default because it's *correct* where the opponent's style-material can't
be profitably captured — Fianchetto crediting YOUR fianchetto is what
makes it cling to its nested bishop when you try to trade it, which is
the documented counter-play. Diagnostic that found it: score every root
move with a full window and print the within-RANDOM_MARGIN candidate
set — sampling select() a handful of times can miss a bad move that's
sitting at the top of the list.

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

## Upstream patches (re-apply after any `git pull` in lichess-bot/)

**1. Correspondence-game KeyError.** lichess-bot has a bug: `KeyError: 'game'`
in `check_in_on_correspondence_games`. Fixed with:

```bash
sed -i '' 's/opponent_name = event\["game"\]/opponent_name = event.get("game", {})/' lib/lichess_bot.py
```

(Currently moot — correspondence games are declined — but it will bite if
that ever changes.)

**2. Control-stream rate-limit hammering (found 2026-07-13).** The bot
would repeatedly get stuck rate-limited on `/api/stream/event` for many
minutes, sometimes recurring within one game, and would *not* clear on
its own — only a full process kill + 5 min of nothing connecting fixed
it. Root cause found in the auto log
(`lichess_bot_auto_logs/lichess-bot.log`, which retains far more history
than the tmux pane scrollback and is the right place to look first next
time this happens):

- The actual trigger is a `TimeoutError` (SSL handshake or socket read
  timeout) on the long-lived control stream — a real, if infrequent,
  network hiccup, not abuse. This part is environmental (Wi-Fi/Tailscale)
  and not something to chase in the code.
- The bug that turned one hiccup into a long lockout: `watch_control_stream`
  in `lib/lichess_bot.py` catches *any* exception — including
  `lichess.RateLimitedError`, which carries the server's actual advised
  wait time (`exception.timeout`) — and unconditionally does
  `time.sleep(1)` before retrying. That means once rate-limited, it was
  re-hitting the rate-limited endpoint roughly once a second instead of
  waiting out the advised window, which looks like abusive reconnect
  behavior to Lichess and plausibly kept re-arming the block.

Fix: catch `lichess.RateLimitedError` specifically in
`watch_control_stream` and sleep for `exception.timeout` (+1s margin)
instead of the flat 1s used for other errors:

```python
        except lichess.RateLimitedError as exception:
            wait = to_seconds(exception.timeout) + 1
            logger.warning(f"Control stream is rate limited. Waiting {wait:.0f}s before reconnecting "
                            "(instead of hammering the endpoint every 1s).")
            time.sleep(wait)
        except Exception:
            logger.warning(f"Control stream error, reconnecting:\n{traceback.format_exc()}")
            time.sleep(1)
```

This is a real code fix, not just a workaround — but it can't undo an
*existing* lockout retroactively. If the bot is already stuck when this
patch goes in, still do the full kill + 5-minute-clean-wait once; the
patch's job is to stop that from being necessary again for future
timeouts.

---

## Ideas not yet built

- ~~Iterative deepening + TT~~ — done 2026-07-20 (see the TT entry
  above). Depth 4 is now ~13s/move locally. Still unbuilt from that
  project: **killer moves**, **aspiration windows**.
- ~~Time-budgeted search~~ — done 2026-07-20, same day. `think_time`
  seconds on any bot: iterative deepening runs on a **board copy** and
  aborts mid-iteration past the deadline (an `_OutOfTime` exception,
  checked every 256 nodes to keep `time.monotonic()` off the hot path),
  falling back to the last *fully completed* iteration — never a mix of
  depths at the root, which would resurrect the root-window bug in a
  different form. `bot.last_depth` reports what was actually reached.
  Depth 1 always completes first (milliseconds) so there's always a
  fallback before the clock starts. This is what let the hosted depth
  cap rise from 3 to 4: `MAX_DEPTH=4` + a mandatory `DEFAULT_THINK_TIME`
  bounds worst-case move time regardless of position or host CPU speed —
  t4g's slower core just settles for a completed depth 3 instead of
  risking an incomplete depth 4, which is exactly the point.

**Fianchetto needed re-tuning for depth 4 (2026-07-20, same session).**
Verifying the above at depth 4 for the first time (previously
impractical) surfaced a real regression: root-score dump showed the
g6/b6-vs-d5 gap shrinking from 0.55 pawns at depth 3 to 0.15 at depth 4
— *inside* RANDOM_MARGIN (0.25) — because the base evaluation sees more
of central play's real value one ply deeper, eroding the fixed style
bonus's relative weight. The horizon-problem lesson again, at a depth
the project had never run before. Non-obvious part: the fix didn't scale
linearly — a proportional 1.4x bump only widened the depth-4 gap to
0.20 (barely moved) while over-fixing depth 3 (gap to 0.95); 2.0x was
needed to get depth 4 to a safe 0.50 gap. Read as alpha-beta pruning
sensitivity: changing the evaluation constant changes which branches get
pruned, so the relationship between a static bonus and a searched score
isn't linear once real pruning is happening (i.e. depth 3 largely
free-searches this position, depth 4 doesn't). **Preparatory-move bonus
0.70/0.30 → 1.40/0.60, nest bonus 1.00/0.50 → 2.00/1.00.** Verified 10/10
g6/b6 at both depth 3 and depth 4, material dead even vs Beginner after
20 plies at both depths. Lesson: **when validating a new depth for the
first time, don't assume a personality's existing weight still holds —
dump root scores at that specific depth before trusting samples**, and
when a fix doesn't move the number as much as the math suggests, suspect
pruning interaction rather than re-deriving the math harder.
- **More eval knowledge** — rook on open files, outposts, passed-pawn
  blockades.
- **New personalities** — Simplifier (trades when ahead), Hypermodern.
- A **Reddit post** for r/chessbeginners is drafted but waiting on a game
  where he actually punishes the fianchetto structure rather than winning
  on a blunder.
