#!/usr/bin/env python3
"""
Daily usage report for the hosted chess trainer.

Reads the last 24h of the trainer container's logs (server.py logs one JSON
line per bot move to stdout, see web_trainer/server.py's _usage_log),
aggregates it, and emails a plain-text summary via iCloud SMTP.

Runs as an EC2 host crontab entry -- see MIGRATION.md. Needs no AWS
permissions: it reads Docker's local log capture directly and sends mail
itself, rather than going through CloudWatch/SES.
"""
import json
import smtplib
import subprocess
from email.mime.text import MIMEText
from pathlib import Path

CONTAINER = "trainer"
SINCE = "24h"
SMTP_HOST = "smtp.mail.me.com"
SMTP_PORT = 587
SMTP_USER = "mick@noordewier.net"
PASSWORD_PATH = Path("/opt/chess-trainer/icloud_smtp_password")
TO_ADDR = "beaters-remote.8n@icloud.com"


def fetch_events():
    proc = subprocess.run(
        ["docker", "logs", CONTAINER, "--since", SINCE],
        capture_output=True, text=True, check=True,
    )
    events = []
    for line in (proc.stdout + proc.stderr).splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if data.get("event") == "bot_move":
            events.append(data)
    return events


def percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, round(pct / 100 * len(values)) - 1))
    return values[idx]


def build_report(events) -> str:
    if not events:
        return "No bot-move activity in the last 24h."

    total = len(events)
    invites = sorted({e.get("invite", "none") for e in events} - {"none"})
    personalities = {}
    for e in events:
        p = e.get("personality", "?")
        personalities[p] = personalities.get(p, 0) + 1
    latencies = [e["latency_ms"] for e in events if "latency_ms" in e]

    lines = [
        "Chess Trainer -- Daily Usage Report (last 24h)",
        "",
        f"Total bot moves: {total}",
        f"Unique invites active: {len(invites)}"
        + (f" ({', '.join(invites)})" if invites else ""),
        "",
        "Personality popularity:",
    ]
    for name, count in sorted(personalities.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {name}: {count}")

    if latencies:
        lines += [
            "",
            "Bot-move latency:",
            f"  p50: {percentile(latencies, 50)} ms",
            f"  p95: {percentile(latencies, 95)} ms",
            f"  max: {max(latencies)} ms",
        ]

    return "\n".join(lines)


def send_email(body: str) -> None:
    password = PASSWORD_PATH.read_text().strip()
    msg = MIMEText(body)
    msg["Subject"] = "Chess Trainer -- Daily Usage Report"
    msg["From"] = SMTP_USER
    msg["To"] = TO_ADDR

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, password)
        smtp.sendmail(SMTP_USER, [TO_ADDR], msg.as_string())


if __name__ == "__main__":
    report = build_report(fetch_events())
    send_email(report)
    print(report)
