"""Persistent watchlist of Twitter profiles to analyze."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

_PATH = Path(__file__).parent.parent / "config" / "watchlist.json"


class WatchedUser(TypedDict):
    username: str
    name: str
    avatar_url: str


def load() -> list[WatchedUser]:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save(users: list[WatchedUser]) -> None:
    _PATH.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def add(username: str, name: str = "", avatar_url: str = "") -> None:
    users = load()
    if not any(u["username"].lower() == username.lower() for u in users):
        users.append({"username": username, "name": name, "avatar_url": avatar_url})
        save(users)


def remove(username: str) -> None:
    users = [u for u in load() if u["username"].lower() != username.lower()]
    save(users)


def contains(username: str) -> bool:
    return any(u["username"].lower() == username.lower() for u in load())
