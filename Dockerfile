# Chess trainer deploy image. PyPy runtime: measured 3-5x faster per bot
# move than CPython on this engine (see MIGRATION.md).
FROM pypy:3.11-slim

# Debian packages Stockfish under /usr/games.
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*
ENV STOCKFISH_PATH=/usr/games/stockfish

WORKDIR /app
COPY web_trainer/requirements.txt web_trainer/requirements.txt
RUN pip install --no-cache-dir -r web_trainer/requirements.txt

# Mirror the repo layout: server.py resolves personality_bots.py from its
# parent directory, same as when run from a checkout.
COPY personality_bots.py .
COPY web_trainer/server.py web_trainer/
COPY web_trainer/static/ web_trainer/static/

WORKDIR /app/web_trainer
EXPOSE 5001

# Workers should match vCPUs on the host (bot moves are CPU-bound);
# override at run time with -e WEB_CONCURRENCY=N (gunicorn reads it).
ENV WEB_CONCURRENCY=2
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--timeout", "120", "server:app"]
