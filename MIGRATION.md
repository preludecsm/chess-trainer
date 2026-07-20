# MIGRATION.md — public multi-user hosting on AWS

Plan only; nothing here is provisioned yet. Written 2026-07-19.

## What we're starting from (the good news)

The trainer is already the right shape for multi-user hosting:

- **Stateless API.** The client sends the full position (FEN) with every
  request; the server holds no game state. Any request can go to any
  worker — no sessions, no sticky routing, no database for core play.
- **Hardened input path.** FEN validated (`board.is_valid()`) before it
  reaches Stockfish, depth clamped 1–8, malformed input → 400, engine
  auto-restarts if it dies.
- **Self-contained frontend.** All JS/CSS/piece images vendored under
  `static/` — no CDN dependencies, trivially cacheable.

## The dominant constraint (the honest news)

**A bot move at depth 3 costs 15–20 seconds of pure-Python CPU on one
core.** Everything about scaling follows from this number:

- One core serves ~3–4 moves/minute. Ten simultaneous games ≈ ten cores
  during think time.
- Depth is a *cost dial an attacker can turn*: depth 4 is ~2 minutes of
  CPU per request. Public deployment must cap depth lower than the local
  clamp of 8 — **cap at 3 (maybe 4 for authenticated users)**.
- The Stockfish eval calls are cheap by comparison (0.5s, capped by
  `EVAL_TIME`) but still need per-IP rate limiting.

Cheap wins worth evaluating before scaling hardware:

| Option | Expected effect | Effort |
|---|---|---|
| **PyPy** instead of CPython | **MEASURED 2026-07-19 (`bench_engine.py`): 3× mean, 4–5× once the JIT warms** (10.5s → 3.5s mean per depth-3 move; steady-state ~2.2s; identical moves chosen). Full stack verified under PyPy 3.11 — flask, python-chess, Stockfish UCI, hardening. `run.sh` now prefers the `venv-pypy` venv. **Decision: build the deploy image on PyPy.** | Done locally |
| Iterative deepening + TT | **Done 2026-07-20**: depth 3 unchanged, depth 4 1.6× faster (~13s/move locally). | Done |
| Time-budgeted search | **Done 2026-07-20**: `think_time` param, safe mid-iteration abort, `last_depth` reports what was reached. First deploy used `DEFAULT_THINK_TIME=8`, which turned out to let hard positions fall back all the way to depth 2 (weak) on t4g — a real inconsistency, not just a latency wobble. Re-measured and fixed same day: `DEFAULT_THINK_TIME=18` (`MAX_THINK_TIME=25`) guarantees **depth 3 as a floor** on t4g regardless of position — depth 4 only ever adds, never subtracts. Worst-case move time ~19s. See "Depth-3 floor" below for the full investigation. | Done |
| Time-budgeted search | A hard per-move CPU ceiling regardless of position — the right *public* interface even if depth stays the internal dial | Small, pairs with iterative deepening |

## Architecture options

### Option A — single small instance (recommended v1)

EC2 `t3.small`/`t3.medium` or Lightsail ($10–25/mo):

```
CloudFront (TLS, static caching) ──► nginx ──► gunicorn (N workers) ──► Flask app
                                                  │ one Stockfish process per worker
                                                  └ worker count = vCPUs (bot moves are CPU-bound)
```

- gunicorn `--workers <vCPUs> --timeout 60`; spawn the Stockfish engine
  **after** fork (per worker), not preloaded — the current lazy
  `_get_engine()` already does this correctly.
- Requests beyond worker capacity queue in gunicorn's backlog; add a
  low `backlog` + return 503 fast so the client can show "server busy"
  rather than hanging.
- Good for ~2–4 concurrent games. Invite-link audience, not HN-front-page.

### Option B — Lambda (surprisingly good fit for spiky low traffic)

Container-image Lambda (Python + Stockfish binary), API Gateway front:

- A 20s depth-3 move at 1.8GB ≈ **$0.0005/move**; scale-to-zero when
  nobody's playing; per-request isolation kills the noisy-neighbor
  problem entirely.
- Cold start (~1–2s) is noise next to a 15s think.
- Caveats: 15-min hard limit (fine), API Gateway 29s default timeout
  (needs raising or async pattern for depth 4), Lambda pricing punishes
  *sustained* traffic — if usage grows steady, move to Option C.

### Option C — ECS Fargate (when there's real sustained usage)

Containerize once (same image works for B), autoscale on CPU. Skip until
metrics from A or B justify it.

### Not needed (yet)

- Database — only if accounts/game-history features are added (then:
  DynamoDB for games, Cognito or magic links for identity).
- WebSockets — request/response fits the move cadence fine.

## Required before going public (any option)

1. **Rate limiting**: per-IP token bucket (flask-limiter behind nginx,
   or API Gateway throttling). Bot moves are the expensive resource:
   something like 10 moves/min/IP, 200/day/IP to start.
2. **Public depth cap ≤ 3** (see above). Keep 1–8 only for a trusted
   mode.
3. **TLS everywhere**: CloudFront or ALB + ACM cert, or certbot on the
   instance. Never expose the Flask dev server — gunicorn only.
4. **Concurrency backpressure**: bounded queue + fast 503; client shows
   "server busy, retrying…" (small `index.html` change — retry with
   backoff on 503/429).
5. **Observability**: structured request logs (personality, depth,
   think-time, IP hash) → CloudWatch; alarm on sustained CPU and 5xx.
6. **CORS**: same-origin only (the page and API share an origin; no
   `Access-Control-Allow-Origin` needed — don't add one).
7. **Licensing check** (done): MIT (ours, chess.js, chessboard.js),
   jQuery MIT, Stockfish GPLv3 (server-side execution of the unmodified
   binary; source link in the page footer is good citizenship),
   Wikipedia piece set (CC — add attribution to the footer).
8. **No secrets ship**: the repo holds none (the old Lichess token stays
   local in untracked `lichess-bot/`; revoke it regardless).

## Client changes needed

Small: retry-with-backoff on 429/503, a "server busy" status line, and a
footer (license attributions + "moves may take ~15s" expectation-setting).
Everything else already works — the UI is stateless against the same API.

## Deployed (2026-07-19)

Option A is live:

| Piece | Value |
|---|---|
| URL | https://dty47fe9cic2a.cloudfront.net |
| CloudFront distribution | `E34DPKJWVJ2M2Z` (CachingDisabled policy; static edge-caching is a future optimization) |
| EC2 instance | `i-07eaf30b71b79b2cd`, t4g.small, us-west-2, AL2023 arm64 |
| Elastic IP | 44.227.208.213 (`eipalloc-04e1966634d26100d`) |
| Security group | `sg-080c28ba615f5e647` — port 22 from home IP only, port 80 from CloudFront origin-facing prefix list only |
| ECR image | `175691005574.dkr.ecr.us-west-2.amazonaws.com/chess-trainer:latest` |
| Container env | `MAX_DEPTH=4 DEFAULT_THINK_TIME=18 MAX_THINK_TIME=25 RATE_LIMIT_PER_MIN=10 WEB_CONCURRENCY=2` |
| CPU credits | Instance is in **Unlimited** mode (checked 2026-07-20) — under sustained load it keeps bursting at full speed rather than throttling to baseline; the cost is billed overage, not a performance cliff. Balance was healthy (~440+, stable) as of the check. |
| SSH | `ssh -i ~/.ssh/chess-trainer-key.pem ec2-user@44.227.208.213` |

**To redeploy after a code change** (from the repo root):

```bash
docker build -t chess-trainer .
aws ecr get-login-password | docker login --username AWS --password-stdin 175691005574.dkr.ecr.us-west-2.amazonaws.com
docker tag chess-trainer:latest 175691005574.dkr.ecr.us-west-2.amazonaws.com/chess-trainer:latest
docker push 175691005574.dkr.ecr.us-west-2.amazonaws.com/chess-trainer:latest
ECR_PW=$(aws ecr get-login-password)
ssh -i ~/.ssh/chess-trainer-key.pem ec2-user@44.227.208.213 \
  "echo '$ECR_PW' | docker login --username AWS --password-stdin 175691005574.dkr.ecr.us-west-2.amazonaws.com \
   && docker pull 175691005574.dkr.ecr.us-west-2.amazonaws.com/chess-trainer:latest \
   && docker rm -f trainer \
   && docker run -d --name trainer --restart always -p 80:5001 \
        -e MAX_DEPTH=4 -e DEFAULT_THINK_TIME=18 -e MAX_THINK_TIME=25 \
        -e RATE_LIMIT_PER_MIN=10 -e WEB_CONCURRENCY=2 \
        175691005574.dkr.ecr.us-west-2.amazonaws.com/chess-trainer:latest"
```

Note: home IP changes break SSH access (rule is /32-scoped) — update with
`aws ec2 authorize-security-group-ingress`. Measured on t4g.small: depth-3
middlegame ~15s cold, improving as the PyPy JIT warms.

### Depth-3 floor investigation (2026-07-20)

The first `MAX_DEPTH=4` deploy used `DEFAULT_THINK_TIME=8`, chosen without
measurement. Testing it properly (explicit `depth:4` requests against
real positions, not the default-depth curl calls used to "verify" the
initial deploy — those had silently used the server's `depth=3` fallback
and proved nothing) showed the actual behavior was a **2–4 depth swing**,
not a mild "sometimes 3 instead of 4": hard middlegames fell back all
the way to depth 2, which this project's own docs call "weak but
instant." That's a real inconsistency against NOTES.md's explicit design
goal (depth 3 deliberately calibrated to the target player's skill
frontier — "a stronger bot is not better").

Two questions followed, both benchmarked rather than guessed:

**Would a faster instance fix it?** Spot-launched `c8g.medium`
(Graviton4, 1 vCPU — note *half* the cores of `t4g.small`'s 2, so
matching capacity would actually need `c8g.large`) and ran the identical
`bench_engine.py`, plus the same explicit-depth-4 hard-position test,
directly against both instances:

| | depth-3 mean | depth-4, 8s budget, hard position |
|---|---|---|
| Local (Apple Silicon) | 3.46s | completes fully (~13s) |
| c8g.medium (Graviton4) | 5.38s | falls back to depth 3 |
| t4g.small (Graviton2) | 11.45s | falls back to depth 2 |

A newer instance changes *what* you fall back to (3 vs 2) but doesn't
eliminate the fallback — even Graviton4 doesn't close the gap to Apple
Silicon's single-core performance. Real effect, not a full fix on its
own, and `c8g.large` (matching current 2-vCPU capacity) is a materially
bigger cost jump than 2×.

**Is the credit model a second hidden risk?** Checked instance credit
mode directly (`describe-instance-credit-specifications`): `t4g.small`
is in **Unlimited** mode, not Standard — under sustained load it keeps
bursting at full speed rather than throttling to baseline, billing the
overage instead of degrading silently. One less risk than initially
flagged; still worth knowing this is a cost lever, not just a
performance one, under real concurrent-user load.

**Fix shipped**: raise the budget so depth 3 always completes, on the
current instance, at zero added cost — `DEFAULT_THINK_TIME=18` (measured
worst-case depth-3 was 13.12s; that leaves real margin), `MAX_THINK_TIME=25`.
Depth 4 becomes pure bonus on easy positions, never a step down from the
calibrated baseline. Verified on all three benchmark positions: opening
reaches depth 4, both hard middlegames floor at depth 3 (worst-case
latency ~19s, bounded and known). The UI now also displays the depth
actually reached when it falls short of the request, so any remaining
variance (3 vs 4) is visible rather than silent — the instance/budget
question was never really about eliminating variance, it was about
making sure it never becomes invisible or falls below the design floor.

The instance-upgrade lever (`c8g.large`) remains available later if the
depth-4 bonus case matters enough to be worth ~2-4x the monthly cost —
not needed today.

## Suggested sequence

1. ~~Benchmark PyPy locally~~ **Done (2026-07-19)**: 3–5×, full stack
   verified. Depth-3 moves drop to ~2–4s; a 2-vCPU instance now serves
   ~15–30 moves/min instead of ~6, and depth 4 becomes publicly plausible.
2. Dockerfile: pypy-slim + stockfish + gunicorn; prove it runs locally
   in-container. (Requires Docker Desktop — not yet installed.)
3. Deploy Option A behind CloudFront with rate limits + depth cap;
   invite-only link; watch CloudWatch for a couple of weeks.
4. Decide B vs C from observed traffic shape (spiky → Lambda, steady →
   Fargate); the Dockerfile from step 2 works for either.
