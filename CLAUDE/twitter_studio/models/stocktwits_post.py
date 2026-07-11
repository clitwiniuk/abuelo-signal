"""Stocktwits post domain model."""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class StocktwitsPostModel(BaseModel):
    id: str
    ticker: str
    body: str
    author_id: str
    author_username: str
    author_name: str
    author_avatar: Optional[str] = None
    author_followers: Optional[int] = None
    created_at: Optional[datetime] = None
    like_count: int = 0
    reply_count: int = 0
    sentiment: Optional[str] = None    # Bullish | Bearish | None
    cashtags: list[str] = []
    mentions: list[str] = []
    urls: list[str] = []
    has_media: bool = False
    media_url: Optional[str] = None
    link_title: Optional[str] = None
    link_url: Optional[str] = None
    link_image_url: Optional[str] = None
    is_reply: bool = False
    post_url: Optional[str] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_date(cls, v: object) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            return None

    def to_export_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "fecha": self.created_at.isoformat() if self.created_at else "",
            "usuario": self.author_username,
            "nombre": self.author_name,
            "texto": self.body,
            "likes": self.like_count,
            "replies": self.reply_count,
            "cashtags": ", ".join(self.cashtags),
            "menciones": ", ".join(self.mentions),
            "sentimiento": self.sentiment or "",
            "enlace": self.post_url or "",
        }
