"""
Benchmark the personality engine under different Python runtimes.

Usage:  <python> bench_engine.py
Runs a fixed set of depth-3 searches on middlegame positions and reports
wall-clock per move. Same positions every run, RANDOM_MARGIN disabled via
Beginner-with-margin-0 subclass, so runs are comparable across runtimes.
"""
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chess
from personality_bots import BeginnerSearchBot

# Middlegame positions (mix of open/cluttered, both colors to move).
FENS = [
    "r1bqk2r/pp2bppp/2n1pn2/2pp4/3P1B2/2P1PN2/PP1N1PPP/R2QKB1R w KQkq - 0 8",
    "r2q1rk1/1b2bppp/p1n1pn2/1pp5/4P3/1BNP1N2/PPP2PPP/R1BQR1K1 b - - 4 11",
    "2rq1rk1/pb1nbppp/1p2pn2/2p5/2PP4/1PN1PN2/PB2BPPP/R2Q1RK1 w - - 2 12",
]

class DeterministicBot(BeginnerSearchBot):
    RANDOM_MARGIN = 0.0   # always the top move: comparable across runs

def main():
    print(f"runtime: {sys.implementation.name} {sys.version.split()[0]}")
    bot = DeterministicBot(depth=3)
    times = []
    for fen in FENS:
        board = chess.Board(fen)
        t0 = time.perf_counter()
        move = bot.select(board)
        dt = time.perf_counter() - t0
        times.append(dt)
        print(f"  {dt:6.2f}s  {board.san(move):8s}  {fen[:30]}...")
    print(f"total: {sum(times):.2f}s   mean/move: {sum(times)/len(times):.2f}s")

if __name__ == "__main__":
    main()
