#!/usr/bin/env python3
"""
Personality chess bots.

Requires:  pip install chess

One engine core (FourPlyBot: negamax + alpha-beta + quiescence, with a
material/PST/pawn-structure/king-safety evaluation) and one personality
per subclass of SearchingPersonality, each adding a small evaluation
bias so style emerges from search rather than an opening book:

  BeginnerSearchBot       - no bias; the clean baseline
  SafeRandomSearchBot     - wide random margin: never blunders, never plans
  WanderingQueenSearchBot - queen out early, roaming, centralized
  PawnStormSearchBot      - pawns advanced toward the enemy king
  FianchettoSearchBot     - bishops nested on the long diagonals

Consumed by web_trainer/server.py (the primary interface) and
homemade_personalities.py (the dormant lichess-bot adapter).
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
CASTLED_BONUS = 0.25


PST_SYMBOL = {
    chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B",
    chess.ROOK: "R", chess.QUEEN: "Q", chess.KING: "K",
}


# ----------------------------------------------------------------------
# Engine core
# ----------------------------------------------------------------------

class FourPlyBot:
    """
    Alpha-beta (negamax) search to a fixed depth, with quiescence search
    at the horizon so captures are resolved before a leaf is evaluated —
    this is what stops it blundering material mid-exchange. Evaluation
    covers material, piece-square tables, pawn structure, king safety
    (tapered by game phase), and the bishop pair.
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
        enemy_color = not color
        enemy_king = board.king(enemy_color)
        if enemy_king is None:
            return 0.0
        enemy_home = chess.E1 if enemy_color == chess.WHITE else chess.E8
        if enemy_king == enemy_home:
            # The enemy hasn't castled yet, so their home-square king is
            # still central -- aiming at it literally rewards central pawn
            # play (d5/e5) over real flank storms (f5/g5/h5), which is
            # backwards. Assume kingside castling, by far the common case,
            # so there's a real storm target from move one. Once the enemy
            # actually castles (or gets flushed off e1/e8 some other way)
            # this falls through to their true square below.
            target_square = chess.G1 if enemy_color == chess.WHITE else chess.G8
        else:
            target_square = enemy_king
        target_file = chess.square_file(target_square)

        bonus = 0.0
        for square in board.pieces(chess.PAWN, color):
            advance = (chess.square_rank(square) - 1 if color == chess.WHITE
                       else 6 - chess.square_rank(square))
            file_gap = abs(chess.square_file(square) - target_file)
            bonus += 0.2 * advance * (2.0 - 0.4 * min(file_gap, 4))
        return bonus


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
                bonus += 1.00                       # bishop in the nest
                if has_shelter:
                    bonus += 0.50                   # ...and it has its pawn
            elif has_shelter:
                # The preparatory pawn move is rewarded on its own, so the
                # engine will play g6/b6 even though the bishop has not
                # arrived yet — otherwise the payoff is beyond its horizon.
                bonus += 0.70
                if home in bishops:
                    bonus += 0.30                   # bishop still home, ready
        return bonus
