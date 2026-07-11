#!/usr/bin/env python3
"""
Personality chess bots — a skeleton framework.

Requires:  pip install chess

Included personalities:
  SafeRandomBot     - plays randomly, but never (knowingly) hangs a piece
  WanderingQueenBot - loves moving the queen, the farther the better
  PawnStormBot      - shoves pawns toward the enemy king

Run directly for a terminal game:  python personality_bots.py
"""

import random
import chess

PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
}


# ----------------------------------------------------------------------
# Shared tactical helper
# ----------------------------------------------------------------------

def hanging_material(board: chess.Board, color: chess.Color) -> int:
    """
    Rough estimate of material `color` has en prise right now.

    A piece counts as hanging if it is attacked by a cheaper piece,
    or attacked while undefended. This is a heuristic, not a full
    static exchange evaluation — deliberately imperfect, like a
    human club player's quick scan.
    """
    total = 0
    for square, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(not color, square)
        if not attackers:
            continue
        value = PIECE_VALUES[piece.piece_type]
        cheapest = min(
            PIECE_VALUES[board.piece_at(a).piece_type] for a in attackers
        )
        defenders = board.attackers(color, square)
        if cheapest < value:
            total += value - cheapest        # loses the exchange
        elif not defenders:
            total += value                   # free to take
    return total


def move_safety_score(board: chess.Board, move: chess.Move) -> float:
    """
    Score a move by immediate material consequences:
      + value of anything we capture
      - value of our material left hanging afterward
      + big bonus for delivering checkmate
    """
    score = 0.0
    if board.is_capture(move):
        captured = board.piece_at(move.to_square)
        if captured:                          # (en passant has no piece on to_square)
            score += PIECE_VALUES[captured.piece_type]
        else:
            score += 1                        # en passant capture
    board.push(move)
    if board.is_checkmate():
        score += 1000
    score -= hanging_material(board, not board.turn)  # our color after push
    board.pop()
    return score


# ----------------------------------------------------------------------
# Personality framework
# ----------------------------------------------------------------------

class PersonalityBot:
    """Base class: subclasses override style_bonus() and/or select()."""

    name = "Base"

    def style_bonus(self, board: chess.Board, move: chess.Move) -> float:
        """Extra points for moves that fit the personality. Override me."""
        return 0.0

    def select(self, board: chess.Board) -> chess.Move:
        """Default: safety score + style bonus, random among the best tier."""
        moves = list(board.legal_moves)
        scored = [
            (move_safety_score(board, m) + self.style_bonus(board, m), m)
            for m in moves
        ]
        best = max(s for s, _ in scored)
        # "best tier" = within half a pawn of the top; adds variety
        candidates = [m for s, m in scored if s >= best - 0.5]
        return random.choice(candidates)


class SafeRandomBot(PersonalityBot):
    """Random moves, but filtered so it doesn't hang material."""

    name = "SafeRandom"

    def select(self, board: chess.Board) -> chess.Move:
        moves = list(board.legal_moves)
        scored = [(move_safety_score(board, m), m) for m in moves]
        # Prefer any move that doesn't lose material; among those, pure random.
        safe = [m for s, m in scored if s >= 0]
        if safe:
            return random.choice(safe)
        # Everything loses something — pick the least bad option.
        best = max(s for s, _ in scored)
        return random.choice([m for s, m in scored if s == best])


class WanderingQueenBot(PersonalityBot):
    """Brings the queen out early and keeps her roaming."""

    name = "WanderingQueen"

    def style_bonus(self, board: chess.Board, move: chess.Move) -> float:
        piece = board.piece_at(move.from_square)
        if piece and piece.piece_type == chess.QUEEN:
            distance = chess.square_distance(move.from_square, move.to_square)
            return 2.0 + 0.3 * distance      # queen moves, long ones best
        return 0.0


class PawnStormBot(PersonalityBot):
    """Advances pawns toward the enemy king's side of the board."""

    name = "PawnStorm"

    def style_bonus(self, board: chess.Board, move: chess.Move) -> float:
        piece = board.piece_at(move.from_square)
        if not piece or piece.piece_type != chess.PAWN:
            return 0.0
        enemy_king = board.king(not board.turn)
        if enemy_king is None:
            return 0.0
        file_gap = abs(
            chess.square_file(move.to_square) - chess.square_file(enemy_king)
        )
        advance = chess.square_rank(move.to_square) - chess.square_rank(move.from_square)
        if board.turn == chess.BLACK:
            advance = -advance
        # reward pushing pawns, especially near the enemy king's file
        return advance * (2.0 - 0.4 * min(file_gap, 4))


class FourPlyBot(PersonalityBot):
    """
    Plain alpha-beta search to a fixed depth (default 4 plies) with a
    material-plus-centralization evaluation. No quiescence search, so it
    suffers from the horizon effect — it will sometimes start a capture
    sequence it can't finish seeing. For a trainer, that's a feature:
    it plays sound tactical chess but can be outcalculated.
    """

    name = "FourPly"
    CENTER = chess.SquareSet(
        [chess.D4, chess.E4, chess.D5, chess.E5,
         chess.C3, chess.D3, chess.E3, chess.F3,
         chess.C6, chess.D6, chess.E6, chess.F6]
    )

    def __init__(self, depth: int = 4):
        self.depth = depth

    def evaluate(self, board: chess.Board) -> float:
        """Score from the side-to-move's perspective (for negamax)."""
        score = 0.0
        for square, piece in board.piece_map().items():
            value = PIECE_VALUES[piece.piece_type]
            if square in self.CENTER and piece.piece_type in (
                chess.PAWN, chess.KNIGHT, chess.BISHOP
            ):
                value += 0.15                 # mild centralization nudge
            score += value if piece.color == chess.WHITE else -value
        return score if board.turn == chess.WHITE else -score

    def _move_order_key(self, board: chess.Board, move: chess.Move) -> float:
        """MVV-LVA: prefer capturing valuable victims with cheap attackers."""
        if not board.is_capture(move):
            return -1.0
        victim = board.piece_at(move.to_square)
        victim_value = PIECE_VALUES[victim.piece_type] if victim else 1  # en passant
        attacker = board.piece_at(move.from_square)
        return 10.0 * victim_value - PIECE_VALUES[attacker.piece_type]

    def _ordered_moves(self, board: chess.Board):
        """Best captures first — good ordering makes alpha-beta prune far more."""
        return sorted(board.legal_moves,
                      key=lambda m: self._move_order_key(board, m), reverse=True)

    def _quiesce(self, board, alpha, beta) -> float:
        """
        Quiescence search: at the depth horizon, keep resolving captures
        until the position is quiet, so we never evaluate mid-exchange.
        In check there is no 'quiet': all evasions are searched instead.
        """
        in_check = board.is_check()
        moves = list(board.legal_moves)
        if not moves:
            return -1000.0 if in_check else 0.0     # mate or stalemate

        if in_check:
            best = -float("inf")                     # no stand-pat in check
            candidates = moves                       # every evasion
        else:
            best = self.evaluate(board)              # stand pat
            if best >= beta:
                return best
            alpha = max(alpha, best)
            candidates = [m for m in moves if board.is_capture(m)]

        candidates.sort(key=lambda m: self._move_order_key(board, m),
                        reverse=True)
        for move in candidates:
            if not in_check:
                # Delta pruning: skip captures that can't plausibly raise alpha.
                victim = board.piece_at(move.to_square)
                gain = PIECE_VALUES[victim.piece_type] if victim else 1
                if best + gain + 2 < alpha:
                    continue
            board.push(move)
            score = -self._quiesce(board, -beta, -alpha)
            board.pop()
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return best

    def _negamax(self, board, depth, alpha, beta) -> float:
        if board.is_checkmate():
            return -1000 - depth              # prefer faster mates
        if board.is_stalemate() or board.is_insufficient_material() \
                or board.can_claim_draw():
            return 0.0
        if depth == 0:
            return self._quiesce(board, alpha, beta)
        best = -float("inf")
        for move in self._ordered_moves(board):
            board.push(move)
            score = -self._negamax(board, depth - 1, -beta, -alpha)
            board.pop()
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break                          # prune
        return best

    def select(self, board: chess.Board) -> chess.Move:
        best_score = -float("inf")
        best_moves = []
        alpha, beta = -float("inf"), float("inf")
        for move in self._ordered_moves(board):
            board.push(move)
            score = -self._negamax(board, self.depth - 1, -beta, -alpha)
            board.pop()
            if score > best_score + 1e-9:
                best_score, best_moves = score, [move]
            elif abs(score - best_score) <= 1e-9:
                best_moves.append(move)
            alpha = max(alpha, score)
        return random.choice(best_moves)


class SearchingPersonality(FourPlyBot):
    """
    Alpha-beta search whose evaluation carries a personality bias.

    Subclasses override style_for(board, color) to score how well a
    position fits the personality for one side. The bias is applied
    symmetrically (the bot assumes its opponent shares its tastes),
    which keeps the negamax bookkeeping honest.

    RANDOM_MARGIN: if > 0, the bot picks randomly among all root moves
    scoring within that margin of the best, instead of always playing
    the top move. Costs extra search time (no root pruning).
    """

    RANDOM_MARGIN = 0.0

    def style_for(self, board: chess.Board, color: chess.Color) -> float:
        return 0.0

    def evaluate(self, board: chess.Board) -> float:
        base = super().evaluate(board)     # side-to-move perspective
        style = self.style_for(board, chess.WHITE) - self.style_for(board, chess.BLACK)
        if board.turn == chess.BLACK:
            style = -style
        return base + style

    def select(self, board: chess.Board) -> chess.Move:
        if self.RANDOM_MARGIN <= 0:
            return super().select(board)
        # Full-window score for every root move, then random within margin.
        scored = []
        for move in self._ordered_moves(board):
            board.push(move)
            score = -self._negamax(board, self.depth - 1,
                                   -float("inf"), float("inf"))
            board.pop()
            scored.append((score, move))
        best = max(s for s, _ in scored)
        candidates = [m for s, m in scored if s >= best - self.RANDOM_MARGIN]
        return random.choice(candidates)


class BeginnerSearchBot(SearchingPersonality):
    """No stylistic bias — just plain material-and-center search."""


class SafeRandomSearchBot(SearchingPersonality):
    """
    Random play that doesn't blunder within its search horizon:
    picks randomly among all moves within ~3/4 pawn of the best.
    At depth 1 this closely matches the original SafeRandomBot.
    """
    RANDOM_MARGIN = 0.75


class WanderingQueenSearchBot(SearchingPersonality):
    """Values an active, far-flung queen — but now she calculates."""

    HOME = {chess.WHITE: chess.D1, chess.BLACK: chess.D8}

    def style_for(self, board: chess.Board, color: chess.Color) -> float:
        bonus = 0.0
        for square in board.pieces(chess.QUEEN, color):
            bonus += 0.10                                  # keep the queen on
            bonus += 0.05 * chess.square_distance(square, self.HOME[color])
        return bonus


class PawnStormSearchBot(SearchingPersonality):
    """Values pawns advanced toward the enemy king."""

    def style_for(self, board: chess.Board, color: chess.Color) -> float:
        enemy_king = board.king(not color)
        if enemy_king is None:
            return 0.0
        bonus = 0.0
        for square in board.pieces(chess.PAWN, color):
            advance = (chess.square_rank(square) - 1 if color == chess.WHITE
                       else 6 - chess.square_rank(square))
            file_gap = abs(chess.square_file(square) - chess.square_file(enemy_king))
            bonus += 0.05 * advance * (2.0 - 0.4 * min(file_gap, 4))
        return bonus


# ----------------------------------------------------------------------
# Terminal play loop
# ----------------------------------------------------------------------

BOTS = {"1": SafeRandomBot, "2": WanderingQueenBot,
        "3": PawnStormBot, "4": FourPlyBot}


def play():
    print("Choose your opponent:")
    print("  1) SafeRandom   2) WanderingQueen   3) PawnStorm")
    bot = BOTS.get(input("> ").strip(), SafeRandomBot)()
    human_is_white = input("Play as White? [Y/n] ").strip().lower() != "n"

    board = chess.Board()
    while not board.is_game_over():
        print("\n" + str(board) + "\n")
        if (board.turn == chess.WHITE) == human_is_white:
            move = None
            while move is None:
                text = input("Your move (SAN, e.g. Nf3): ").strip()
                try:
                    move = board.parse_san(text)
                except ValueError:
                    print("Illegal or unparseable — try again.")
            board.push(move)
        else:
            move = bot.select(board)
            print(f"{bot.name} plays: {board.san(move)}")
            board.push(move)

    print("\n" + str(board))
    print("Game over:", board.result(), "-", board.outcome().termination.name)


if __name__ == "__main__":
    play()


class FianchettoSearchBot(SearchingPersonality):
    """Loves bishops on the long diagonals, snug behind their pawns."""

    NEST = {chess.WHITE: (chess.B2, chess.G2), chess.BLACK: (chess.B7, chess.G7)}
    SHELTER = {chess.WHITE: (chess.B3, chess.G3), chess.BLACK: (chess.B6, chess.G6)}

    def style_for(self, board: chess.Board, color: chess.Color) -> float:
        bonus = 0.0
        bishops = board.pieces(chess.BISHOP, color)
        for square in self.NEST[color]:
            if square in bishops:
                bonus += 0.25                                # bishop in the nest
        for square in self.SHELTER[color]:
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                bonus += 0.10                                # sheltering pawn
        return bonus
