"""
Local browser trainer: play the personality bots on a real chessboard UI,
with a live Stockfish eval + top-2 moves sidebar for immediate feedback.

No Lichess involved -- this talks to personality_bots.py directly and to
a native Stockfish binary over UCI. Stateless by design: the client
sends the FEN with every request, so the server holds no game state
(which is also what will make multi-user hosting straightforward).

Binds to 127.0.0.1 only. Do not rebind to 0.0.0.0 without the rate
limiting and abuse controls described in MIGRATION.md.
"""
import atexit
import os
import sys
import threading

import chess
import chess.engine
from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from personality_bots import (  # noqa: E402
    BeginnerSearchBot, SafeRandomSearchBot, WanderingQueenSearchBot,
    PawnStormSearchBot, FianchettoSearchBot,
)

PERSONALITIES = {
    "Beginner": BeginnerSearchBot,
    "SafeRandom": SafeRandomSearchBot,
    "WanderingQueen": WanderingQueenSearchBot,
    "PawnStorm": PawnStormSearchBot,
    "Fianchetto": FianchettoSearchBot,
}

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/opt/homebrew/bin/stockfish")
EVAL_TIME = 0.5   # seconds per eval call; MultiPV=2 for the top-2 lines
MIN_DEPTH = 1
# Depth is a cost dial an attacker can turn (depth 4+ = minutes of CPU per
# request), so public deployments set MAX_DEPTH=3 in the environment.
MAX_DEPTH = max(MIN_DEPTH, min(8, int(os.environ.get("MAX_DEPTH", "8"))))

# Per-IP rate limiting: bot moves are the expensive resource. In-memory
# token bucket, per gunicorn worker (workers don't share state, so the
# effective allowance is bucket_size x workers -- fine at this scale).
# 0 disables (the local default); public deployments set e.g. 10.
RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "0"))

app = Flask(__name__, static_folder="static", static_url_path="")
# Vendored libs/piece images are immutable; without this Flask sends
# Cache-Control: no-cache and the browser revalidates all 12 piece images
# on every board redraw — chessboard.js redraws on every click, which
# showed up as visible flicker. index.html is served with max_age=0 below
# so UI iteration stays instant.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 30 * 24 * 3600

# One shared Stockfish process. python-chess's SimpleEngine serializes
# access internally, but the process itself can die if fed a position it
# rejects -- so it's wrapped in a restart-on-failure helper rather than
# trusted to live forever.
_engine = None
_engine_lock = threading.Lock()


def _get_engine() -> chess.engine.SimpleEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        return _engine


def _kill_engine() -> None:
    """Drop a dead/wedged engine so the next request starts a fresh one."""
    global _engine
    with _engine_lock:
        if _engine is not None:
            try:
                _engine.quit()
            except Exception:
                pass
            _engine = None


@atexit.register
def _shutdown() -> None:
    _kill_engine()


_buckets: dict = {}
_buckets_lock = threading.Lock()


def _client_ip() -> str:
    # Behind CloudFront/nginx the real client is the first X-Forwarded-For
    # entry; direct connections fall back to the socket peer.
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "?")


def _rate_limited() -> bool:
    """Token bucket: RATE_LIMIT_PER_MIN tokens/min per client IP."""
    if RATE_LIMIT_PER_MIN <= 0:
        return False
    import time
    now = time.monotonic()
    ip = _client_ip()
    with _buckets_lock:
        tokens, last = _buckets.get(ip, (float(RATE_LIMIT_PER_MIN), now))
        tokens = min(float(RATE_LIMIT_PER_MIN),
                     tokens + (now - last) * RATE_LIMIT_PER_MIN / 60.0)
        if tokens < 1.0:
            _buckets[ip] = (tokens, now)
            return True
        _buckets[ip] = (tokens - 1.0, now)
        # Keep the table from growing unboundedly under IP churn.
        if len(_buckets) > 10000:
            _buckets.clear()
    return False


def _parse_board(data) -> chess.Board:
    """
    Validate client input into a legal chess position, or raise ValueError.
    board.is_valid() rejects positions Stockfish could crash or wedge on
    (missing kings, impossible pawn placement, side-not-to-move in check).
    """
    if not isinstance(data, dict) or "fen" not in data:
        raise ValueError("missing 'fen'")
    board = chess.Board(data["fen"])          # raises ValueError on bad FEN
    if not board.is_valid():
        raise ValueError(f"illegal position: {board.status()!r}")
    return board


def score_to_json(pov_score: chess.engine.PovScore) -> dict:
    score = pov_score.pov(chess.WHITE)
    if score.is_mate():
        return {"mate": score.mate()}
    return {"cp": score.score()}


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html", max_age=0)


@app.route("/api/config")
def config():
    """Deployment limits, so the UI can reflect them instead of silently clamping."""
    return jsonify({"maxDepth": MAX_DEPTH,
                    "personalities": sorted(PERSONALITIES)})


@app.route("/api/eval", methods=["POST"])
def eval_position():
    try:
        board = _parse_board(request.get_json(silent=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if board.is_game_over():
        return jsonify({"lines": [], "gameOver": True})

    try:
        info = _get_engine().analyse(
            board, chess.engine.Limit(time=EVAL_TIME), multipv=2)
    except (chess.engine.EngineError, chess.engine.EngineTerminatedError):
        # One bad interaction must not take eval down permanently.
        _kill_engine()
        return jsonify({"error": "engine restarted; retry"}), 503

    lines = []
    for entry in info:
        pv = entry.get("pv")
        if not pv:
            continue
        move = pv[0]
        lines.append({
            "uci": move.uci(),
            "san": board.san(move),
            "score": score_to_json(entry["score"]),
        })
    return jsonify({"lines": lines, "gameOver": False})


@app.route("/api/bot-move", methods=["POST"])
def bot_move():
    if _rate_limited():
        return jsonify({"error": "rate limited; slow down"}), 429
    data = request.get_json(silent=True)
    try:
        board = _parse_board(data)
        depth = int(data.get("depth", 3))
    except (ValueError, TypeError) as exc:
        return jsonify({"error": f"bad request: {exc}"}), 400
    depth = max(MIN_DEPTH, min(MAX_DEPTH, depth))
    personality = data.get("personality", "Beginner")

    if board.is_game_over():
        return jsonify({"error": "Game is over"}), 400
    if personality not in PERSONALITIES:
        return jsonify({"error": f"Unknown personality: {personality}"}), 400

    bot = PERSONALITIES[personality](depth=depth)
    move = bot.select(board)
    san = board.san(move)
    return jsonify({"uci": move.uci(), "san": san})


if __name__ == "__main__":
    print("Chess trainer running at http://localhost:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
