"""Tests for services/stocktwits_service.py — mapping + persistence, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.stocktwits_service import (
    download_ticker,
    get_checkpoint,
    map_post,
    map_posts,
    query_posts,
    save_posts,
    set_checkpoint,
    ticker_stats,
)

_SAMPLE_PATH = Path(__file__).parent / "fixtures" / "stocktwits_stream_sample.json"


@pytest.fixture
def sample_messages() -> list[dict]:
    return json.loads(_SAMPLE_PATH.read_text())["messages"]


# ---------------------------------------------------------------------------
# map_post
# ---------------------------------------------------------------------------

def test_map_post_extracts_core_fields(sample_messages):
    post = map_post(sample_messages[0], "TSLA")
    assert post.id == str(sample_messages[0]["id"])
    assert post.ticker == "TSLA"
    assert post.author_username == sample_messages[0]["user"]["username"]
    assert post.body == sample_messages[0]["body"]


def test_map_post_reads_sentiment_from_entities():
    raw = {
        "id": 1, "body": "to the moon", "user": {"id": 1, "username": "trader1", "name": "Trader"},
        "likes": {"total": 3}, "conversation": {"replies": 1},
        "entities": {"sentiment": {"basic": "Bullish"}, "media": []},
        "symbols": [{"symbol": "TSLA", "symbol_display": "TSLA"}], "mentioned_users": [], "links": [],
        "created_at": "2026-07-11T10:00:00Z",
    }
    post = map_post(raw, "TSLA")
    assert post.sentiment == "Bullish"
    assert post.like_count == 3
    assert post.reply_count == 1
    assert post.cashtags == ["TSLA"]


def test_map_post_handles_missing_sentiment():
    raw = {
        "id": 2, "body": "just watching", "user": {"id": 2, "username": "u2", "name": "U2"},
        "created_at": "2026-07-11T10:00:00Z",
    }
    post = map_post(raw, "TSLA")
    assert post.sentiment is None
    assert post.like_count == 0


def test_map_post_never_raises_on_malformed_input():
    post = map_post(None, "TSLA")  # totally broken payload
    assert post.id == "error"  # falls back to the sentinel instead of raising


def test_map_posts_maps_every_message(sample_messages):
    posts = map_posts(sample_messages, "TSLA")
    assert len(posts) == len(sample_messages)
    assert all(p.ticker == "TSLA" for p in posts)


# ---------------------------------------------------------------------------
# Persistence (uses the throwaway sqlite db from conftest.py)
# ---------------------------------------------------------------------------

def test_save_posts_persists_and_dedupes(sample_messages):
    posts = map_posts(sample_messages, "TSLA")
    first = save_posts(posts)
    second = save_posts(posts)  # same ids again
    assert first == len(posts)
    assert second == 0


def test_save_posts_skips_error_sentinel():
    bad = map_post(None, "TSLA")
    saved = save_posts([bad])
    assert saved == 0


def test_query_posts_filters_by_ticker_and_sentiment(sample_messages):
    save_posts(map_posts(sample_messages, "AAPL"))
    all_aapl = query_posts(ticker="AAPL")
    bullish_aapl = query_posts(ticker="AAPL", sentiment="Bullish")
    assert all(p.ticker == "AAPL" for p in all_aapl)
    assert all(p.sentiment == "Bullish" for p in bullish_aapl)
    assert len(bullish_aapl) <= len(all_aapl)


def test_query_posts_filters_by_keyword(sample_messages):
    save_posts(map_posts(sample_messages, "MSFT"))
    hits = query_posts(ticker="MSFT", keyword="zzz_nonexistent_zzz")
    assert hits == []


def test_ticker_stats_counts_sentiment_buckets(sample_messages):
    save_posts(map_posts(sample_messages, "GOOG"))
    stats = ticker_stats("GOOG")
    assert stats["total"] == len(sample_messages)
    assert stats["bullish"] + stats["bearish"] + stats["no_sentiment"] == stats["total"]


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def test_checkpoint_roundtrip():
    assert get_checkpoint("NEWTICKER") is None
    set_checkpoint("NEWTICKER", 12345)
    assert get_checkpoint("NEWTICKER") == 12345
    set_checkpoint("NEWTICKER", 99999)
    assert get_checkpoint("NEWTICKER") == 99999


# ---------------------------------------------------------------------------
# download_ticker orchestration (client is faked — no browser/network)
# ---------------------------------------------------------------------------

class _FakeClient:
    def __init__(self, batches: list[list[dict]]):
        self._batches = batches
        self.calls = []

    async def fetch_ticker_history(self, ticker, max_messages, stop_before_id, stop_before_date,
                                    to_date=None, should_stop=None, on_batch=None):
        self.calls.append({
            "stop_before_id": stop_before_id, "stop_before_date": stop_before_date, "to_date": to_date,
        })
        batch = self._batches.pop(0) if self._batches else []
        batch = batch[:max_messages]
        if batch and on_batch:
            on_batch(batch)
        return batch


@pytest.mark.asyncio
async def test_download_ticker_saves_and_advances_checkpoint(sample_messages):
    client = _FakeClient([sample_messages])
    saved = await download_ticker(client, "TQQQ", max_messages=100, resume=True)
    assert saved == len(sample_messages)
    newest_id = max(m["id"] for m in sample_messages)
    assert get_checkpoint("TQQQ") == newest_id


@pytest.mark.asyncio
async def test_download_ticker_resume_passes_checkpoint_to_client(sample_messages):
    set_checkpoint("RESUMED", 555)
    client = _FakeClient([[]])
    await download_ticker(client, "RESUMED", resume=True)
    assert client.calls[0]["stop_before_id"] == 555


@pytest.mark.asyncio
async def test_download_ticker_no_messages_returns_zero():
    client = _FakeClient([[]])
    saved = await download_ticker(client, "EMPTYTICKER", resume=True)
    assert saved == 0
