"""Lightweight EN->ES translation via the unofficial Google Translate endpoint.

No API key required. This is an undocumented endpoint (translate.googleapis.com's
gtx client) — it can break or rate-limit without notice, so callers must treat
failures as non-fatal and keep the original text.
"""

from __future__ import annotations

import requests

from utils.logger import logger

_ENDPOINT = "https://translate.googleapis.com/translate_a/single"


def translate_to_spanish(text: str) -> str | None:
    """Best-effort translation. Returns None on any failure (caller keeps the original)."""
    if not text or not text.strip():
        return None
    try:
        resp = requests.get(
            _ENDPOINT,
            params={"client": "gtx", "sl": "en", "tl": "es", "dt": "t", "q": text},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        # data[0] is a list of [translated_chunk, original_chunk, ...] segments
        return "".join(chunk[0] for chunk in data[0] if chunk[0])
    except Exception as exc:
        logger.warning(f"translate_to_spanish failed: {exc}")
        return None
