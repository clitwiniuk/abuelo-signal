"""Persistent store of tweets marked as read/used."""

from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).parent.parent / "config" / "marked_tweets.json"


def _load() -> set[str]:
    try:
        return set(json.loads(_PATH.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save(ids: set[str]) -> None:
    _PATH.write_text(json.dumps(sorted(ids), ensure_ascii=False), encoding="utf-8")


def is_marked(tweet_id: str) -> bool:
    return tweet_id in _load()


def mark(tweet_id: str) -> None:
    ids = _load()
    ids.add(tweet_id)
    _save(ids)


def unmark(tweet_id: str) -> None:
    ids = _load()
    ids.discard(tweet_id)
    _save(ids)


def toggle(tweet_id: str) -> bool:
    """Toggle mark state. Returns new state (True = marked)."""
    ids = _load()
    if tweet_id in ids:
        ids.discard(tweet_id)
        marked = False
    else:
        ids.add(tweet_id)
        marked = True
    _save(ids)
    return marked


def load_all() -> set[str]:
    return _load()
