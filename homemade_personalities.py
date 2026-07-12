"""
lichess-bot adapter for the personality bots.

The bot process stays connected permanently. Personality and depth are
read from files at the start of every game, so switch.sh can change them
without restarting — which matters because Lichess rate-limits the event
stream, and every restart reconnects to it.

  engine_personality.txt   e.g. "Fianchetto"
  engine_depth.txt         e.g. "3"

config.yml keeps a constant engine name:

  engine:
    dir: "."
    protocol: "homemade"
    name: "Personality"

A change takes effect on the NEXT game — never mid-game, which is the
behaviour you want anyway.
"""
import os
import chess
from chess.engine import PlayResult

from lib.engine_wrapper import MinimalEngine
from lib.lichess_types import HOMEMADE_ARGS_TYPE

from personality_bots import (
    BeginnerSearchBot, SafeRandomSearchBot, WanderingQueenSearchBot,
    PawnStormSearchBot, FianchettoSearchBot,
)

# The switch.sh usage menu is generated from these keys.
PERSONALITIES = {
    "Beginner": BeginnerSearchBot,
    "SafeRandom": SafeRandomSearchBot,
    "WanderingQueen": WanderingQueenSearchBot,
    "PawnStorm": PawnStormSearchBot,
    "Fianchetto": FianchettoSearchBot,
}

_HERE = os.path.dirname(os.path.abspath(__file__))
_PERSONALITY_FILE = os.path.join(_HERE, "engine_personality.txt")
_DEPTH_FILE = os.path.join(_HERE, "engine_depth.txt")

DEFAULT_PERSONALITY = "Beginner"
DEFAULT_DEPTH = 3


def _read_personality() -> str:
    try:
        with open(_PERSONALITY_FILE) as f:
            name = f.read().strip()
        return name if name in PERSONALITIES else DEFAULT_PERSONALITY
    except OSError:
        return DEFAULT_PERSONALITY


def _read_depth() -> int:
    try:
        with open(_DEPTH_FILE) as f:
            return max(1, min(8, int(f.read().strip())))
    except (OSError, ValueError):
        return DEFAULT_DEPTH


class Personality(MinimalEngine):
    """
    One engine class for every personality. Re-reads the config files
    whenever a new game starts, so switch.sh never needs to restart the
    process.
    """

    def _refresh(self) -> None:
        name, depth = _read_personality(), _read_depth()
        current = getattr(self, "_settings", None)
        if current != (name, depth):
            self._settings = (name, depth)
            self._bot = PERSONALITIES[name](depth=depth)
            print(f"[personality] now playing as {name} at depth {depth}",
                  flush=True)

    def search(self, board: chess.Board, *args: HOMEMADE_ARGS_TYPE) -> PlayResult:  # noqa: ARG002
        # Re-read at the start of each game, and on the very first call.
        # Mid-game changes are deliberately ignored.
        if not hasattr(self, "_bot") or board.fullmove_number <= 1:
            self._refresh()
        return PlayResult(self._bot.select(board), None)
