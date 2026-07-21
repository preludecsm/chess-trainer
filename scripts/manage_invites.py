#!/usr/bin/env python3
"""
Add, revoke, or list per-person invite tokens for the hosted chess trainer.

Runs on the EC2 host against the invites file the container reads
(read-only bind mount, see MIGRATION.md). The server re-reads that file on
every request -- no cache, no restart -- so revocation here takes effect
on the very next request from that visitor.

Usage (on the EC2 host):
    python3 manage_invites.py add "Alice"
    python3 manage_invites.py revoke "Alice"      # or the raw token
    python3 manage_invites.py list
"""
import json
import secrets
import sys
from pathlib import Path

PATH = Path("/opt/chess-trainer/invites.json")
BASE_URL = "https://dty47fe9cic2a.cloudfront.net"


def load() -> dict:
    if PATH.exists():
        return json.loads(PATH.read_text())
    return {}


def save(data: dict) -> None:
    PATH.write_text(json.dumps(data, indent=2))


def add(label: str) -> None:
    data = load()
    token = secrets.token_hex(16)
    data[token] = {"label": label}
    save(data)
    print(f"{BASE_URL}/invite/{token}")


def revoke(label_or_token: str) -> None:
    data = load()
    removed = [t for t, v in data.items()
               if t == label_or_token or v.get("label") == label_or_token]
    for t in removed:
        del data[t]
    save(data)
    print(f"revoked {len(removed)} token(s)")


def list_invites() -> None:
    for token, v in load().items():
        print(f"{v.get('label', '?'):20s} {token}")


def main() -> None:
    usage = "usage: manage_invites.py add <label> | revoke <label-or-token> | list"
    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)
    cmd, *rest = sys.argv[1:]
    if cmd == "add" and rest:
        add(" ".join(rest))
    elif cmd == "revoke" and rest:
        revoke(rest[0])
    elif cmd == "list":
        list_invites()
    else:
        print(usage)
        sys.exit(1)


if __name__ == "__main__":
    main()
