"""Twikit client wrapper — singleton with cookie persistence."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import twikit
from twikit import Client

from config.settings import settings, COOKIES_FILE
from utils.logger import logger


class TwitterClient:
    """Thin async wrapper around twikit.Client with cookie save/load."""

    def __init__(self) -> None:
        self._client: Optional[Client] = None
        self._me: Optional[twikit.User] = None
        self._authenticated: bool = False

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    @property
    def me(self) -> Optional[twikit.User]:
        return self._me

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    async def login(
        self,
        username: str,
        email: str,
        password: str,
        language: str = "en-US",
    ) -> bool:
        """Log in with credentials and save cookies."""
        try:
            self._client = Client(language=language)
            await self._client.login(
                auth_info_1=email,
                auth_info_2=username,
                password=password,
            )
            self._authenticated = True
            self._me = await self._client.user()
            self._save_cookies()
            logger.info(f"Logged in as @{username}")
            return True
        except Exception as exc:
            logger.error(f"Login failed: {exc}")
            self._authenticated = False
            return False

    async def login_with_cookies(self, language: str = "en-US") -> bool:
        """Resume session from saved cookies."""
        if not COOKIES_FILE.exists():
            return False
        try:
            self._client = Client(language=language)
            self._load_cookies_normalized(str(COOKIES_FILE))
            self._me = await self._client.user()
            self._authenticated = True
            logger.info(f"Session restored for @{self._me.screen_name}")
            return True
        except Exception as exc:
            logger.warning(f"Cookie login failed ({exc}), cookies may be stale")
            self._authenticated = False
            return False

    def _load_cookies_normalized(self, path: str) -> None:
        """Load cookies handling both twikit format and Cookie-Editor export format."""
        with open(path) as f:
            data = json.load(f)

        # Cookie-Editor exports a list of dicts with 'name'/'value'/'domain' etc.
        # twikit's load_cookies expects {name: value, ...} or the same list format.
        # Normalize to {name: value} dict if needed.
        if isinstance(data, list) and data and "name" in data[0]:
            normalized = {c["name"]: c["value"] for c in data}
            import tempfile, os
            tmp = path + ".normalized"
            with open(tmp, "w") as f:
                json.dump(normalized, f)
            self._client.load_cookies(tmp)
            os.unlink(tmp)
        else:
            self._client.load_cookies(path)

    def logout(self) -> None:
        COOKIES_FILE.unlink(missing_ok=True)
        self._client = None
        self._me = None
        self._authenticated = False
        logger.info("Logged out — cookies deleted")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    async def search_tweets(
        self,
        query: str,
        product: str = "Latest",   # Latest | Top | Media
        count: int = 50,
    ) -> list[twikit.Tweet]:
        self._require_auth()
        try:
            results = await self._client.search_tweet(
                query=query,
                product=product,
                count=count,
            )
            return list(results)
        except Exception as exc:
            logger.error(f"search_tweets error: {exc}")
            return []

    async def search_tweets_paginated(
        self,
        query: str,
        product: str = "Latest",
        max_results: int = 200,
    ) -> list[twikit.Tweet]:
        """Fetch multiple pages up to max_results."""
        self._require_auth()
        collected: list[twikit.Tweet] = []
        try:
            page = await self._client.search_tweet(
                query=query,
                product=product,
                count=min(max_results, 50),
            )
            collected.extend(page)
            while len(collected) < max_results:
                remaining = max_results - len(collected)
                try:
                    page = await page.next()
                    if not page:
                        break
                    collected.extend(list(page)[:remaining])
                except Exception:
                    break
        except Exception as exc:
            logger.error(f"search_tweets_paginated error: {exc}")
        return collected[:max_results]

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    async def get_user_by_screen_name(self, screen_name: str) -> Optional[twikit.User]:
        self._require_auth()
        screen_name = screen_name.lstrip("@")
        try:
            return await self._client.get_user_by_screen_name(screen_name)
        except Exception as exc:
            logger.error(f"get_user error ({screen_name}): {exc}")
            return None

    async def get_user_tweets(
        self,
        user_id: str,
        tweet_type: str = "Tweets",
        count: int = 20,
        pages: int = 1,
    ) -> list[twikit.Tweet]:
        """Fetch user tweets with optional multi-page pagination.

        X returns ~20 tweets per page regardless of `count`.
        Use `pages` to fetch multiple pages automatically.
        """
        self._require_auth()
        try:
            results = await self._client.get_user_tweets(
                user_id=user_id,
                tweet_type=tweet_type,
                count=count,
            )
            all_tweets = list(results)
            for _ in range(pages - 1):
                if not hasattr(results, "next") or results.next is None:
                    break
                results = await results.next()
                all_tweets.extend(list(results))
            return all_tweets
        except Exception as exc:
            logger.error(f"get_user_tweets error: {exc}")
            return []

    async def search_user_lists(self, username: str) -> list[twikit.List]:
        """Return public lists created by a given @username."""
        self._require_auth()
        try:
            results = await self._client.search_list(username.lstrip("@"), count=20)
            # Filter to lists owned by that user
            clean = username.lstrip("@").lower()
            return [l for l in results if getattr(l, "member_count", None) is not None
                    and l.name and l.owner and l.owner.screen_name.lower() == clean]
        except Exception as exc:
            logger.error(f"search_user_lists error: {exc}")
            return []

    async def get_timeline(self, count: int = 20) -> list[twikit.Tweet]:
        self._require_auth()
        try:
            return list(await self._client.get_timeline(count=count))
        except Exception as exc:
            logger.error(f"get_timeline error: {exc}")
            return []

    async def get_trends(self) -> list:
        self._require_auth()
        try:
            return await self._client.get_trends("trending")
        except Exception as exc:
            logger.error(f"get_trends error: {exc}")
            return []

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _require_auth(self) -> None:
        if not self._authenticated or self._client is None:
            raise RuntimeError("Not authenticated — call login() or login_with_cookies() first")

    def _save_cookies(self) -> None:
        if self._client:
            self._client.save_cookies(str(COOKIES_FILE))
            logger.debug(f"Cookies saved to {COOKIES_FILE}")


# Module-level singleton
twitter_client = TwitterClient()
