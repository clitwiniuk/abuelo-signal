"""Tweet domain model."""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator


class TweetModel(BaseModel):
    id: str
    text: str
    author_id: str
    author_name: str
    author_username: str
    author_avatar: Optional[str] = None
    created_at: Optional[datetime] = None
    like_count: int = 0
    reply_count: int = 0
    retweet_count: int = 0
    view_count: Optional[int] = None
    quote_count: int = 0
    language: Optional[str] = None
    hashtags: list[str] = []
    mentions: list[str] = []
    urls: list[str] = []
    has_media: bool = False
    media_type: Optional[str] = None   # photo | video | gif
    is_retweet: bool = False
    is_reply: bool = False
    tweet_url: Optional[str] = None
    sentiment: Optional[str] = None    # positive | neutral | negative
    sentiment_score: Optional[float] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_date(cls, v: object) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v))
        except ValueError:
            return None

    def to_export_dict(self) -> dict:
        return {
            "id": self.id,
            "fecha": self.created_at.isoformat() if self.created_at else "",
            "usuario": self.author_username,
            "nombre": self.author_name,
            "texto": self.text,
            "likes": self.like_count,
            "replies": self.reply_count,
            "retweets": self.retweet_count,
            "visualizaciones": self.view_count or 0,
            "hashtags": ", ".join(self.hashtags),
            "menciones": ", ".join(self.mentions),
            "idioma": self.language or "",
            "sentimiento": self.sentiment or "",
            "enlace": self.tweet_url or "",
        }
