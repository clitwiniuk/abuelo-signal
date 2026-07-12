"""Stocktwits service — maps raw stream JSON messages to domain models."""

from __future__ import annotations

from typing import Callable, Optional

from database.schema import DBSetting, DBStocktwitsPost, SessionLocal
from models.stocktwits_post import StocktwitsPostModel
from utils.logger import logger
from utils.translate import translate_to_spanish


def map_post(raw: dict, ticker: str) -> StocktwitsPostModel:
    """Convert a raw message dict from the streams/symbol API into a StocktwitsPostModel."""
    try:
        post_id = str(raw.get("id", ""))
        user = raw.get("user") or {}
        username = str(user.get("username", ""))

        likes = raw.get("likes") or {}
        conversation = raw.get("conversation") or {}
        entities = raw.get("entities") or {}
        media = entities.get("media") or []

        cashtags = [s.get("symbol_display") or s.get("symbol") for s in raw.get("symbols") or [] if s.get("symbol")]
        mentions = [m.get("username") for m in raw.get("mentioned_users") or [] if m.get("username")]
        raw_links = raw.get("links") or []
        urls = [l.get("url") for l in raw_links if l.get("url")]
        first_link = raw_links[0] if raw_links else {}

        sentiment = (entities.get("sentiment") or {}).get("basic")

        return StocktwitsPostModel(
            id=post_id,
            ticker=ticker.upper(),
            body=raw.get("body", "") or "",
            author_id=str(user.get("id", "")),
            author_username=username,
            author_name=str(user.get("name", "")),
            author_avatar=user.get("avatar_url"),
            author_followers=_safe_int(user.get("followers")),
            created_at=raw.get("created_at"),
            like_count=int(likes.get("total", 0) or 0),
            reply_count=int(conversation.get("replies", 0) or 0),
            sentiment=sentiment,
            cashtags=cashtags,
            mentions=mentions,
            urls=urls,
            has_media=bool(media),
            media_url=(media[0].get("large") or media[0].get("url")) if media else None,
            link_title=first_link.get("title"),
            link_url=first_link.get("url"),
            link_image_url=first_link.get("image_url"),
            is_reply=bool(conversation.get("in_reply_to_message_id")),
            post_url=f"https://stocktwits.com/{username}/message/{post_id}" if username and post_id else None,
        )
    except Exception as exc:
        logger.warning(f"map_post failed: {exc}")
        return StocktwitsPostModel(id="error", ticker=ticker.upper(), body="", author_id="",
                                    author_username="", author_name="")


def map_posts(raws: list[dict], ticker: str) -> list[StocktwitsPostModel]:
    return [map_post(r, ticker) for r in raws]


def save_posts(posts: list[StocktwitsPostModel]) -> int:
    """Upsert-by-id: skip posts already stored, return count of newly saved rows."""
    db = SessionLocal()
    saved = 0
    try:
        for p in posts:
            if p.id == "error":
                continue
            exists = db.query(DBStocktwitsPost).filter(
                DBStocktwitsPost.id == p.id, DBStocktwitsPost.ticker == p.ticker
            ).first()
            if exists:
                continue
            db.add(DBStocktwitsPost(
                id=p.id,
                ticker=p.ticker,
                body=p.body,
                author_id=p.author_id,
                author_username=p.author_username,
                author_name=p.author_name,
                author_followers=p.author_followers,
                created_at=p.created_at,
                like_count=p.like_count,
                reply_count=p.reply_count,
                sentiment=p.sentiment,
                cashtags=",".join(p.cashtags),
                mentions=",".join(p.mentions),
                has_media=p.has_media,
                media_url=p.media_url,
                link_title=p.link_title,
                link_url=p.link_url,
                link_image_url=p.link_image_url,
                is_reply=p.is_reply,
                post_url=p.post_url,
            ))
            saved += 1
        db.commit()
    except Exception as exc:
        logger.error(f"save_posts error: {exc}")
        db.rollback()
    finally:
        db.close()
    return saved


def get_translation(post_id: str, ticker: str) -> Optional[str]:
    """Return the cached Spanish translation for a post, translating and
    persisting it on first request. Returns None if translation fails —
    caller should fall back to showing the original body."""
    db = SessionLocal()
    try:
        row = db.query(DBStocktwitsPost).filter(
            DBStocktwitsPost.id == post_id, DBStocktwitsPost.ticker == ticker.upper()
        ).first()
        if row is None:
            return None
        if row.body_es:
            return row.body_es
        translated = translate_to_spanish(row.body)
        if translated:
            row.body_es = translated
            db.commit()
        return translated
    finally:
        db.close()


def list_tickers() -> list[dict]:
    """Summary of every ticker currently stored: message count and date range."""
    from sqlalchemy import func
    db = SessionLocal()
    try:
        rows = (
            db.query(
                DBStocktwitsPost.ticker,
                func.count(DBStocktwitsPost.id),
                func.min(DBStocktwitsPost.created_at),
                func.max(DBStocktwitsPost.created_at),
            )
            .group_by(DBStocktwitsPost.ticker)
            .order_by(DBStocktwitsPost.ticker)
            .all()
        )
        return [
            {"ticker": t, "count": c, "oldest": mn, "newest": mx}
            for t, c, mn, mx in rows
        ]
    finally:
        db.close()


def delete_ticker(ticker: str) -> int:
    """Delete every stored post and the checkpoint for a ticker. Returns rows deleted."""
    db = SessionLocal()
    try:
        deleted = db.query(DBStocktwitsPost).filter(DBStocktwitsPost.ticker == ticker.upper()).delete()
        db.query(DBSetting).filter(DBSetting.key == _checkpoint_key(ticker)).delete()
        db.commit()
        logger.info(f"[stocktwits] Deleted {deleted} posts for {ticker.upper()}")
        return deleted
    except Exception as exc:
        logger.error(f"delete_ticker error: {exc}")
        db.rollback()
        return 0
    finally:
        db.close()


def _filtered_posts_query(db, ticker=None, from_date=None, to_date=None, sentiment=None, keyword=None):
    q = db.query(DBStocktwitsPost)
    if ticker:
        q = q.filter(DBStocktwitsPost.ticker == ticker.upper())
    if from_date:
        q = q.filter(DBStocktwitsPost.created_at >= from_date)
    if to_date:
        q = q.filter(DBStocktwitsPost.created_at <= to_date)
    if sentiment:
        q = q.filter(DBStocktwitsPost.sentiment == sentiment)
    if keyword:
        q = q.filter(DBStocktwitsPost.body.ilike(f"%{keyword}%"))
    return q


def query_posts(
    ticker: Optional[str] = None,
    from_date=None,
    to_date=None,
    sentiment: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 500,
) -> list[DBStocktwitsPost]:
    db = SessionLocal()
    try:
        q = _filtered_posts_query(db, ticker, from_date, to_date, sentiment, keyword)
        return q.order_by(DBStocktwitsPost.created_at.desc()).limit(limit).all()
    finally:
        db.close()


def count_posts(
    ticker: Optional[str] = None,
    from_date=None,
    to_date=None,
    sentiment: Optional[str] = None,
    keyword: Optional[str] = None,
) -> int:
    db = SessionLocal()
    try:
        return _filtered_posts_query(db, ticker, from_date, to_date, sentiment, keyword).count()
    finally:
        db.close()


def ticker_stats(ticker: str) -> dict:
    db = SessionLocal()
    try:
        rows = db.query(DBStocktwitsPost).filter(DBStocktwitsPost.ticker == ticker.upper()).all()
        bullish = sum(1 for r in rows if r.sentiment == "Bullish")
        bearish = sum(1 for r in rows if r.sentiment == "Bearish")
        return {
            "total": len(rows),
            "bullish": bullish,
            "bearish": bearish,
            "no_sentiment": len(rows) - bullish - bearish,
        }
    finally:
        db.close()


def _checkpoint_key(ticker: str) -> str:
    return f"stocktwits_checkpoint_{ticker.upper()}"


def get_checkpoint(ticker: str) -> Optional[int]:
    """Return the last message id seen for this ticker (oldest boundary of prior download)."""
    db = SessionLocal()
    try:
        row = db.query(DBSetting).filter(DBSetting.key == _checkpoint_key(ticker)).first()
        return int(row.value) if row else None
    finally:
        db.close()


def set_checkpoint(ticker: str, message_id: int) -> None:
    db = SessionLocal()
    try:
        key = _checkpoint_key(ticker)
        row = db.query(DBSetting).filter(DBSetting.key == key).first()
        if row:
            row.value = str(message_id)
        else:
            db.add(DBSetting(key=key, value=str(message_id)))
        db.commit()
    finally:
        db.close()


async def download_ticker(
    client,
    ticker: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    max_messages: int = 2000,
    resume: bool = True,
    should_stop: Optional[Callable[[], bool]] = None,
) -> int:
    """Download a ticker's message history for a date window and persist it
    incrementally (page by page), checkpointing progress as it goes.

    client: a started StocktwitsClient instance.
    from_date / to_date: ISO date strings bounding the period of interest.
        from_date is the older edge (stop once messages older than this appear),
        to_date is the newer edge (skip messages newer than this without stopping).
    resume: if True, stop once we reach the last checkpointed message id (already
            covered by a previous run for this ticker).
    should_stop: polled between pages — return True to cancel early (e.g. a UI
        "Stop" button). Whatever was fetched and saved before the stop is kept,
        and the checkpoint reflects the newest message actually seen.
    """
    stop_before_id = get_checkpoint(ticker) if resume else None
    logger.info(
        f"[stocktwits] Downloading {ticker} (resume from id={stop_before_id}, "
        f"from_date={from_date}, to_date={to_date})"
    )

    total_saved = 0
    checkpoint_id: Optional[int] = None

    def _on_batch(batch: list[dict]) -> None:
        nonlocal total_saved, checkpoint_id
        posts = map_posts(batch, ticker)
        total_saved += save_posts(posts)
        # The first batch processed is always the newest (stream walks
        # backwards), so only set the checkpoint once from it — later,
        # older batches must not drag it down.
        if checkpoint_id is None:
            ids = [m["id"] for m in batch if m.get("id") is not None]
            if ids:
                checkpoint_id = max(ids)

    raw_messages = await client.fetch_ticker_history(
        ticker,
        max_messages=max_messages,
        stop_before_id=stop_before_id,
        stop_before_date=from_date,
        to_date=to_date,
        should_stop=should_stop,
        on_batch=_on_batch,
    )

    if checkpoint_id is not None:
        set_checkpoint(ticker, checkpoint_id)

    logger.info(
        f"[stocktwits] {ticker}: {len(raw_messages)} fetched, {total_saved} new rows saved, "
        f"checkpoint={checkpoint_id}"
    )
    return total_saved


def _safe_int(v: object) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
