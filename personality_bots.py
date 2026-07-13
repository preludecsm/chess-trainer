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

# Piece-square tables, White's perspective, rank 8 (index 0) down to rank 1.
# Values in centipawns/100 (i.e. pawn units). Classic "simplified evaluation" set.
PST = {
    "P": [  # pawns: advance, control center, don't push rook pawns early
        0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,
        0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5,
        0.1,  0.1,  0.2,  0.3,  0.3,  0.2,  0.1,  0.1,
        0.05, 0.05, 0.10, 0.25, 0.25, 0.10, 0.05, 0.05,
        0.0,  0.0,  0.0,  0.20, 0.20, 0.0,  0.0,  0.0,
        0.05,-0.05,-0.10, 0.0,  0.0, -0.10,-0.05, 0.05,
        0.05, 0.10, 0.10,-0.20,-0.20, 0.10, 0.10, 0.05,
        0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,
    ],
    "N": [  # knights: centralize; rim is grim
       -0.50,-0.40,-0.30,-0.30,-0.30,-0.30,-0.40,-0.50,
       -0.40,-0.20, 0.0,  0.0,  0.0,  0.0, -0.20,-0.40,
       -0.30, 0.0,  0.10, 0.15, 0.15, 0.10, 0.0, -0.30,
       -0.30, 0.05, 0.15, 0.20, 0.20, 0.15, 0.05,-0.30,
       -0.30, 0.0,  0.15, 0.20, 0.20, 0.15, 0.0, -0.30,
       -0.30, 0.05, 0.10, 0.15, 0.15, 0.10, 0.05,-0.30,
       -0.40,-0.20, 0.0,  0.05, 0.05, 0.0, -0.20,-0.40,
       -0.50,-0.40,-0.30,-0.30,-0.30,-0.30,-0.40,-0.50,
    ],
    "B": [  # bishops: long diagonals, avoid corners
       -0.20,-0.10,-0.10,-0.10,-0.10,-0.10,-0.10,-0.20,
       -0.10, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.10,
       -0.10, 0.0,  0.05, 0.10, 0.10, 0.05, 0.0, -0.10,
       -0.10, 0.05, 0.05, 0.10, 0.10, 0.05, 0.05,-0.10,
       -0.10, 0.0,  0.10, 0.10, 0.10, 0.10, 0.0, -0.10,
       -0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10,-0.10,
       -0.10, 0.05, 0.0,  0.0,  0.0,  0.0,  0.05,-0.10,
       -0.20,-0.10,-0.10,-0.10,-0.10,-0.10,-0.10,-0.20,
    ],
    "R": [  # rooks: 7th rank, central files, don't move early
        0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,
        0.05, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.05,
       -0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05,
       -0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05,
       -0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05,
       -0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05,
       -0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05,
        0.0,  0.0,  0.0,  0.05, 0.05, 0.0,  0.0,  0.0,
    ],
    "Q": [  # queen: mild centralization, don't develop too early
       -0.20,-0.10,-0.10,-0.05,-0.05,-0.10,-0.10,-0.20,
       -0.10, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.10,
       -0.10, 0.0,  0.05, 0.05, 0.05, 0.05, 0.0, -0.10,
       -0.05, 0.0,  0.05, 0.05, 0.05, 0.05, 0.0, -0.05,
        0.0,  0.0,  0.05, 0.05, 0.05, 0.05, 0.0, -0.05,
       -0.10, 0.05, 0.05, 0.05, 0.05, 0.05, 0.0, -0.10,
       -0.10, 0.0,  0.05, 0.0,  0.0,  0.0,  0.0, -0.10,
       -0.20,-0.10,-0.10,-0.05,-0.05,-0.10,-0.10,-0.20,
    ],
    "K": [  # king (middlegame): castle, stay behind pawns
       -0.30,-0.40,-0.40,-0.50,-0.50,-0.40,-0.40,-0.30,
       -0.30,-0.40,-0.40,-0.50,-0.50,-0.40,-0.40,-0.30,
       -0.30,-0.40,-0.40,-0.50,-0.50,-0.40,-0.40,-0.30,
       -0.30,-0.40,-0.40,-0.50,-0.50,-0.40,-0.40,-0.30,
       -0.20,-0.30,-0.30,-0.40,-0.40,-0.30,-0.30,-0.20,
       -0.10,-0.20,-0.20,-0.20,-0.20,-0.20,-0.20,-0.10,
        0.20, 0.20, 0.0,  0.0,  0.0,  0.0,  0.20, 0.20,
        0.20, 0.30, 0.10, 0.0,  0.0,  0.10, 0.30, 0.20,
    ],
}

# King's endgame table: centralize instead of hiding once the queens are gone.
PST["K_END"] = [
   -0.50,-0.40,-0.30,-0.20,-0.20,-0.30,-0.40,-0.50,
   -0.30,-0.20,-0.10, 0.0,  0.0, -0.10,-0.20,-0.30,
   -0.30,-0.10, 0.20, 0.30, 0.30, 0.20,-0.10,-0.30,
   -0.30,-0.10, 0.30, 0.40, 0.40, 0.30,-0.10,-0.30,
   -0.30,-0.10, 0.30, 0.40, 0.40, 0.30,-0.10,-0.30,
   -0.30,-0.10, 0.20, 0.30, 0.30, 0.20,-0.10,-0.30,
   -0.30,-0.30, 0.0,  0.0,  0.0,  0.0, -0.30,-0.30,
   -0.50,-0.30,-0.30,-0.30,-0.30,-0.30,-0.30,-0.50,
]

# Total non-pawn material at the start (per side), used to taper the king table.
PHASE_MAX = 2 * (PIECE_VALUES[chess.KNIGHT] + PIECE_VALUES[chess.BISHOP]
                 + PIECE_VALUES[chess.ROOK]) + PIECE_VALUES[chess.QUEEN]

DOUBLED_PAWN = -0.20
ISOLATED_PAWN = -0.20
PASSED_PAWN = (0.0, 0.10, 0.15, 0.25, 0.40, 0.65, 1.00, 0.0)  # by rank advanced
BISHOP_PAIR = 0.30
MOBILITY_WEIGHT = 0.02
CASTLED_BONUS = 0.25


PST_SYMBOL = {
    chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B",
    chess.ROOK: "R", chess.QUEEN: "Q", chess.KING: "K",
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

    def _phase(self, board: chess.Board) -> float:
        """1.0 = full middlegame, 0.0 = bare endgame. Tapers the king table."""
        material = 0
        for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            material += PIECE_VALUES[pt] * (
                len(board.pieces(pt, chess.WHITE)) +
                len(board.pieces(pt, chess.BLACK))
            )
        return min(1.0, material / (2.0 * PHASE_MAX))

    def _pawn_structure(self, board: chess.Board, color: chess.Color) -> float:
        """Doubled and isolated pawn penalties; passed pawn bonuses."""
        score = 0.0
        pawns = board.pieces(chess.PAWN, color)
        enemy_pawns = board.pieces(chess.PAWN, not color)
        files = [0] * 8
        for sq in pawns:
            files[chess.square_file(sq)] += 1

        for f in range(8):
            if files[f] > 1:
                score += DOUBLED_PAWN * (files[f] - 1)
            if files[f] > 0:
                left = files[f - 1] if f > 0 else 0
                right = files[f + 1] if f < 7 else 0
                if left == 0 and right == 0:
                    score += ISOLATED_PAWN * files[f]      # no neighbours

        for sq in pawns:
            f, r = chess.square_file(sq), chess.square_rank(sq)
            advanced = r - 1 if color == chess.WHITE else 6 - r
            blocked = False
            for ef in (f - 1, f, f + 1):
                if not 0 <= ef <= 7:
                    continue
                for esq in enemy_pawns:
                    if chess.square_file(esq) != ef:
                        continue
                    er = chess.square_rank(esq)
                    ahead = er > r if color == chess.WHITE else er < r
                    if ahead:
                        blocked = True
                        break
                if blocked:
                    break
            if not blocked and 0 <= advanced <= 7:
                score += PASSED_PAWN[advanced]
        return score

    def _king_safety(self, board: chess.Board, color: chess.Color,
                     phase: float) -> float:
        """Reward a castled king with pawns still in front of it."""
        king = board.king(color)
        if king is None:
            return 0.0
        score = 0.0
        kf, kr = chess.square_file(king), chess.square_rank(king)
        home = 0 if color == chess.WHITE else 7
        if kr == home and (kf >= 6 or kf <= 2):
            score += CASTLED_BONUS                          # tucked away
        shield = 0
        step = 1 if color == chess.WHITE else -1
        for f in (kf - 1, kf, kf + 1):
            if not 0 <= f <= 7:
                continue
            for dr in (1, 2):
                r = kr + step * dr
                if not 0 <= r <= 7:
                    continue
                piece = board.piece_at(chess.square(f, r))
                if piece and piece.piece_type == chess.PAWN \
                        and piece.color == color:
                    shield += 1
                    break
        score += 0.10 * shield
        return score * phase          # king safety only matters with pieces on

    def evaluate(self, board: chess.Board) -> float:
        """
        Material, piece-square tables, and positional knowledge, scored
        from the side-to-move's perspective (for negamax).

        Beyond material and the tables, this adds:
          - tapered king table (hide in the middlegame, centralize in the endgame)
          - pawn structure (doubled, isolated, passed)
          - king safety (castled, pawn shield) — weighted by game phase
          - bishop pair

        (Mobility was tried and removed: generating legal moves at every
        leaf cost ~65% of total evaluation time in Python, which bought
        less strength than the extra search depth it consumed.)
        """
        phase = self._phase(board)
        score = 0.0

        for square, piece in board.piece_map().items():
            value = PIECE_VALUES[piece.piece_type]
            index = chess.square_mirror(square) if piece.color == chess.WHITE \
                else square
            if piece.piece_type == chess.KING:
                mid = PST["K"][index]
                end = PST["K_END"][index]
                value += mid * phase + end * (1.0 - phase)
            else:
                value += PST[PST_SYMBOL[piece.piece_type]][index]
            score += value if piece.color == chess.WHITE else -value

        for color in (chess.WHITE, chess.BLACK):
            sub = self._pawn_structure(board, color)
            sub += self._king_safety(board, color, phase)
            if len(board.pieces(chess.BISHOP, color)) >= 2:
                sub += BISHOP_PAIR
            score += sub if color == chess.WHITE else -sub

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
        """
        Root search. Every root move gets a FULL window: narrowing alpha
        here would make later moves return fail-low bounds rather than
        true scores, and those bogus values would tie with the best and
        get picked at random. (This bug made the bot play nonsense.)
        """
        scored = []
        for move in self._ordered_moves(board):
            board.push(move)
            score = -self._negamax(board, self.depth - 1,
                                   -float("inf"), float("inf"))
            board.pop()
            scored.append((score, move))
        best = max(s for s, _ in scored)
        best_moves = [m for s, m in scored if abs(s - best) <= 1e-9]
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
    """
    No stylistic bias — plain material and positional search.

    RANDOM_MARGIN gives variety: among root moves scoring within this
    many pawns of the best, one is picked at random. Small enough that
    it never plays a real blunder; large enough that repeated games from
    the same opening don't follow the same script. Tune to taste — 0.0
    is fully deterministic, 0.5 starts to look careless.
    """
    RANDOM_MARGIN = 0.25


class SafeRandomSearchBot(SearchingPersonality):
    """
    Random play that doesn't blunder within its search horizon:
    picks randomly among all moves within ~3/4 pawn of the best.
    At depth 1 this closely matches the original SafeRandomBot.
    """
    RANDOM_MARGIN = 0.75


class WanderingQueenSearchBot(SearchingPersonality):
    """Values an active, far-flung queen — but now she calculates."""

    RANDOM_MARGIN = 0.25
    HOME = {chess.WHITE: chess.D1, chess.BLACK: chess.D8}

    CENTRE = chess.SquareSet([chess.D4, chess.E4, chess.D5, chess.E5,
                             chess.C4, chess.F4, chess.C5, chess.F5])

    def style_for(self, board: chess.Board, color: chess.Color) -> float:
        """
        Wants the queen out and roaming — the further from home and the
        more central, the better. She will come out early and stay out,
        which costs tempo and invites attack. That is the lesson.
        """
        bonus = 0.0
        for square in board.pieces(chess.QUEEN, color):
            bonus += 0.12 * chess.square_distance(square, self.HOME[color])
            if square in self.CENTRE:
                bonus += 0.25                              # queen in the middle
        return bonus


class PawnStormSearchBot(SearchingPersonality):
    """Values pawns advanced toward the enemy king."""

    RANDOM_MARGIN = 0.25

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

    RANDOM_MARGIN = 0.25
    NEST = {chess.WHITE: (chess.B2, chess.G2), chess.BLACK: (chess.B7, chess.G7)}
    SHELTER = {chess.WHITE: (chess.B3, chess.G3), chess.BLACK: (chess.B6, chess.G6)}
    HOME = {chess.WHITE: (chess.C1, chess.F1), chess.BLACK: (chess.C8, chess.F8)}

    def style_for(self, board: chess.Board, color: chess.Color) -> float:
        """
        Wants a bishop nested on g2/b2 (g7/b7) behind its own pawn, and
        clings to it. The weights are deliberately large enough that it
        will fianchetto in positions where it is a bad idea — which is
        the point: the weakness has to be visible to be punishable.
        """
        bonus = 0.0
        bishops = board.pieces(chess.BISHOP, color)
        pawns = board.pieces(chess.PAWN, color)

        for nest, shelter, home in zip(self.NEST[color], self.SHELTER[color],
                                       self.HOME[color]):
            has_bishop = nest in bishops
            has_shelter = shelter in pawns
            if has_bishop:
                bonus += 0.55                       # bishop in the nest
                if has_shelter:
                    bonus += 0.35                   # ...and it has its pawn
            elif has_shelter:
                # The preparatory pawn move is rewarded on its own, so the
                # engine will play g6/b6 even though the bishop has not
                # arrived yet — otherwise the payoff is beyond its horizon.
                bonus += 0.30
                if home in bishops:
                    bonus += 0.20                   # bishop still home, ready
        return bonus
