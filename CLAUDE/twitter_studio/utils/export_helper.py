"""Export helpers — DataFrame → CSV / Excel bytes."""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

from models.stocktwits_post import StocktwitsPostModel
from models.tweet import TweetModel
from utils.logger import logger


def tweets_to_dataframe(tweets: list[TweetModel]) -> pd.DataFrame:
    rows = [t.to_export_dict() for t in tweets]
    return pd.DataFrame(rows)


def stocktwits_posts_to_dataframe(posts: list[StocktwitsPostModel]) -> pd.DataFrame:
    rows = [p.to_export_dict() for p in posts]
    return pd.DataFrame(rows)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tweets")
    return buf.getvalue()


def export_filename(prefix: str, ext: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.{ext}"
