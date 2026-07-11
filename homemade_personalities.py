"""
lichess-bot adapters for the personality bots.

Personalities (config.yml engine name / switch.sh argument):
    Beginner        - plain search, no stylistic bias
    SafeRandom      - random among non-blundering moves (within its depth)
    WanderingQueen  - queen-activity-biased search
    PawnStorm       - pawn-advance-biased search

Search depth is read from engine_depth.txt in this directory
(default 4 if the file is missing). All personalities share it.
"""
import os
import chess
from chess.engine import PlayResult

from lib.engine_wrapper import MinimalEngine
from lib.lichess_types import HOMEMADE_ARGS_TYPE

from personality_bots import (
    BeginnerSearchBot, SafeRandomSearchBot,
    WanderingQueenSearchBot, PawnStormSearchBot,
)

_DEPTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "engine_depth.txt")


def _read_depth(default: int = 4) -> int:
    try:
        with open(_DEPTH_FILE) as f:
            return max(1, min(8, int(f.read().strip())))
    except (OSError, ValueError):
        return default


class _PersonalityEngine(MinimalEngine):
    """Shared adapter: lazily builds the bot, delegates move choice to it."""

    BOT_CLASS = None

    def search(self, board: chess.Board, *args: HOMEMADE_ARGS_TYPE) -> PlayResult:  # noqa: ARG002
        if not hasattr(self, "_bot"):
            self._bot = self.BOT_CLASS(depth=_read_depth())
        return PlayResult(self._bot.select(board), None)


class Beginner(_PersonalityEngine):
    BOT_CLASS = BeginnerSearchBot


class SafeRandom(_PersonalityEngine):
    BOT_CLASS = SafeRandomSearchBot


class WanderingQueen(_PersonalityEngine):
    BOT_CLASS = WanderingQueenSearchBot


class PawnStorm(_PersonalityEngine):
    BOT_CLASS = PawnStormSearchBot
