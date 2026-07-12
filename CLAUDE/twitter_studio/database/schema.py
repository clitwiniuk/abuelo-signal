"""SQLAlchemy ORM schema."""

from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, UniqueConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config.settings import settings


class Base(DeclarativeBase):
    pass


class DBUser(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    username = Column(String, nullable=False, index=True)
    description = Column(Text)
    location = Column(String)
    url = Column(String)
    avatar_url = Column(String)
    banner_url = Column(String)
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    tweet_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    is_blue_verified = Column(Boolean, default=False)
    created_at = Column(DateTime)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class DBTweet(Base):
    __tablename__ = "tweets"
    id = Column(String, primary_key=True)
    text = Column(Text, nullable=False)
    author_id = Column(String, index=True)
    author_name = Column(String)
    author_username = Column(String, index=True)
    created_at = Column(DateTime, index=True)
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    retweet_count = Column(Integer, default=0)
    view_count = Column(Integer)
    language = Column(String)
    hashtags = Column(Text)       # comma-separated
    mentions = Column(Text)       # comma-separated
    is_retweet = Column(Boolean, default=False)
    is_reply = Column(Boolean, default=False)
    sentiment = Column(String)
    sentiment_score = Column(Float)
    tweet_url = Column(String)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    keyword_id = Column(Integer)  # FK to keywords (nullable — manual searches)


class DBStocktwitsPost(Base):
    __tablename__ = "stocktwits_posts"
    # Composite PK: the same message id can surface under several tickers
    # when it carries multiple cashtags (e.g. "$TSLA $NVDA ..."), and each
    # ticker's stream download should keep its own row for it.
    id = Column(String, primary_key=True)
    ticker = Column(String, primary_key=True, index=True)
    body = Column(Text, nullable=False)
    body_es = Column(Text)   # lazily translated + cached on first view in "Explorar"
    author_id = Column(String, index=True)
    author_username = Column(String, index=True)
    author_name = Column(String)
    author_followers = Column(Integer)
    created_at = Column(DateTime, index=True)
    market_session = Column(String, index=True)  # PM | RTH | AH | Closed (US Eastern, derived from created_at)
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    sentiment = Column(String)    # Bullish | Bearish | NULL
    cashtags = Column(Text)       # comma-separated
    mentions = Column(Text)       # comma-separated
    has_media = Column(Boolean, default=False)
    media_url = Column(String)
    link_title = Column(String)
    link_url = Column(String)
    link_image_url = Column(String)
    is_reply = Column(Boolean, default=False)
    post_url = Column(String)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class DBKeyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)
    last_checked = Column(DateTime)
    tweet_count = Column(Integer, default=0)


class DBSearch(Base):
    __tablename__ = "searches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String, nullable=False)
    result_count = Column(Integer, default=0)
    searched_at = Column(DateTime, default=datetime.utcnow)
    filters = Column(Text)   # JSON blob


class DBSession(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    logged_in_at = Column(DateTime, default=datetime.utcnow)
    logged_out_at = Column(DateTime)
    active = Column(Boolean, default=True)


class DBLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    module = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class DBSetting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Engine + Session factory
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite only
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Context-manager-style session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
