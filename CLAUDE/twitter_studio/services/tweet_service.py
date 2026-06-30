"""Tweet service — maps raw twikit objects to domain models + sentiment."""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import twikit
from textblob import TextBlob

from models.tweet import TweetModel
from models.user import UserModel
from utils.logger import logger

_URL_RE = re.compile(r"https?://\S+")
_HASHTAG_RE = re.compile(r"#(\w+)")
_MENTION_RE = re.compile(r"@(\w+)")


def _parse_twitter_date(value) -> Optional[datetime]:
    """Parse Twitter's date format: 'Thu Jun 24 11:43:01 +0000 2010'"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return parsedate_to_datetime(str(value))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Mappers
# ---------------------------------------------------------------------------
def map_tweet(raw: twikit.Tweet) -> TweetModel:
    """Convert a twikit Tweet into a TweetModel."""
    try:
        text = getattr(raw, "text", "") or ""
        author = getattr(raw, "user", None)

        hashtags = _HASHTAG_RE.findall(text)
        mentions = _MENTION_RE.findall(text)
        urls = _URL_RE.findall(text)

        media = getattr(raw, "media", None) or []
        has_media = bool(media)
        media_type: Optional[str] = None
        if has_media:
            m = media[0]
            media_type = getattr(m, "type", None)

        sentiment, score = _analyse_sentiment(text)

        tweet_id = str(getattr(raw, "id", ""))
        username = str(getattr(author, "screen_name", "")) if author else ""

        return TweetModel(
            id=tweet_id,
            text=text,
            author_id=str(getattr(author, "id", "")) if author else "",
            author_name=str(getattr(author, "name", "")) if author else "",
            author_username=username,
            author_avatar=getattr(author, "profile_image_url", None) if author else None,
            created_at=_parse_twitter_date(getattr(raw, "created_at", None)),
            like_count=int(getattr(raw, "favorite_count", 0) or 0),
            reply_count=int(getattr(raw, "reply_count", 0) or 0),
            retweet_count=int(getattr(raw, "retweet_count", 0) or 0),
            view_count=_safe_int(getattr(raw, "view_count", None)),
            quote_count=int(getattr(raw, "quote_count", 0) or 0),
            language=getattr(raw, "lang", None),
            hashtags=hashtags,
            mentions=mentions,
            urls=urls,
            has_media=has_media,
            media_type=media_type,
            is_retweet=bool(getattr(raw, "retweeted_tweet", None)),
            is_reply=bool(getattr(raw, "in_reply_to", None)),
            tweet_url=f"https://x.com/{username}/status/{tweet_id}" if username else None,
            sentiment=sentiment,
            sentiment_score=score,
        )
    except Exception as exc:
        logger.warning(f"map_tweet failed: {exc}")
        return TweetModel(id="error", text="", author_id="", author_name="", author_username="")


def map_user(raw: twikit.User) -> UserModel:
    """Convert a twikit User into a UserModel."""
    try:
        return UserModel(
            id=str(getattr(raw, "id", "")),
            name=str(getattr(raw, "name", "")),
            username=str(getattr(raw, "screen_name", "")),
            description=getattr(raw, "description", None),
            location=getattr(raw, "location", None),
            url=getattr(raw, "url", None),
            avatar_url=getattr(raw, "profile_image_url", None),
            banner_url=getattr(raw, "profile_banner_url", None),
            followers_count=int(getattr(raw, "followers_count", 0) or 0),
            following_count=int(getattr(raw, "friends_count", 0) or 0),
            tweet_count=int(getattr(raw, "statuses_count", 0) or 0),
            listed_count=int(getattr(raw, "listed_count", 0) or 0),
            is_verified=bool(getattr(raw, "verified", False)),
            is_blue_verified=bool(getattr(raw, "is_blue_verified", False)),
            created_at=_parse_twitter_date(getattr(raw, "created_at", None)),
            protected=bool(getattr(raw, "protected", False)),
        )
    except Exception as exc:
        logger.warning(f"map_user failed: {exc}")
        return UserModel(id="error", name="", username="")


def map_tweets(raws: list[twikit.Tweet]) -> list[TweetModel]:
    return [map_tweet(r) for r in raws]


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------
def _analyse_sentiment(text: str) -> tuple[str, float]:
    """Simple polarity via TextBlob. Returns (label, score)."""
    try:
        clean = _URL_RE.sub("", text)
        blob = TextBlob(clean)
        score = blob.sentiment.polarity
        if score > 0.05:
            label = "positive"
        elif score < -0.05:
            label = "negative"
        else:
            label = "neutral"
        return label, round(score, 4)
    except Exception:
        return "neutral", 0.0


def _safe_int(v: object) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
