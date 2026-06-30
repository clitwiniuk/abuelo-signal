"""User / profile domain model."""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UserModel(BaseModel):
    id: str
    name: str
    username: str
    description: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    tweet_count: int = 0
    listed_count: int = 0
    is_verified: bool = False
    is_blue_verified: bool = False
    created_at: Optional[datetime] = None
    protected: bool = False

    @property
    def profile_url(self) -> str:
        return f"https://x.com/{self.username}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.name,
            "username": f"@{self.username}",
            "bio": self.description or "",
            "ubicacion": self.location or "",
            "web": self.url or "",
            "seguidores": self.followers_count,
            "seguidos": self.following_count,
            "tweets": self.tweet_count,
            "verificado": self.is_verified or self.is_blue_verified,
            "creado": self.created_at.isoformat() if self.created_at else "",
        }
