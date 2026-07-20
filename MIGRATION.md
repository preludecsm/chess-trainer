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
| Time-budgeted search | **Done 2026-07-20**: `think_time` param, safe mid-iteration abort, `last_depth` reports what was reached. Hosted now runs `MAX_DEPTH=4` with a mandatory `DEFAULT_THINK_TIME=8` (clients may request up to `MAX_THINK_TIME=15`) — move time is now bounded regardless of position complexity or host CPU speed. Verified live: t4g settles for a completed depth 3 within budget rather than risking an incomplete depth 4. | Done |
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
| Container env | `MAX_DEPTH=4 DEFAULT_THINK_TIME=8 MAX_THINK_TIME=15 RATE_LIMIT_PER_MIN=10 WEB_CONCURRENCY=2` |
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
        -e MAX_DEPTH=4 -e DEFAULT_THINK_TIME=8 -e MAX_THINK_TIME=15 \
        -e RATE_LIMIT_PER_MIN=10 -e WEB_CONCURRENCY=2 \
        175691005574.dkr.ecr.us-west-2.amazonaws.com/chess-trainer:latest"
```

Note: home IP changes break SSH access (rule is /32-scoped) — update with
`aws ec2 authorize-security-group-ingress`. Measured on t4g.small: depth-3
middlegame ~15s cold, improving as the PyPy JIT warms.

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
