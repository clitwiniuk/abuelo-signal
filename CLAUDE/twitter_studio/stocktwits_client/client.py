"""Stocktwits client — Playwright wrapper that intercepts the internal JSON API.

Stocktwits sits behind Cloudflare's bot challenge, so plain HTTP requests to
api.stocktwits.com return a 403 "Just a moment..." page. The public site itself
calls that same API via fetch() once the challenge is solved by a real browser.
Instead of parsing the rendered HTML, we let Playwright load the page (solving
the challenge) and capture the JSON responses the page requests on its own.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Callable, Optional

import nest_asyncio
from patchright.async_api import async_playwright, Browser, BrowserContext, Page, Response

from config.settings import STOCKTWITS_COOKIES_FILE
from utils.logger import logger

STREAM_API_PATTERN = "**/api/2/streams/symbol/*.json"

# Ad/tracker/analytics domains observed on stocktwits.com — blocking these
# cuts page load and scroll-response latency substantially. Never block
# stocktwits.com/api.stocktwits.com themselves or challenges.cloudflare.com
# (needed for the Cloudflare bot-challenge to resolve).
_BLOCKED_DOMAINS = (
    # Session-replay/recording beacon — floods dozens of requests per second
    # from numbered subdomains. Kept as a fallback: see _BLOCKED_URL_PATTERNS
    # below, this vendor rotates its root domain (html-load.com ->
    # duhquietly.com -> content-loader.com, observed across this same
    # session) specifically to dodge exact-domain blocklists like this one.
    "html-load.com", "duhquietly.com", "content-loader.com",
    # Video ad network — live.primis.tech/video.primis.tech/rtb.primis.tech.
    "primis.tech",
    "doubleclick.net", "googlesyndication.com", "google-analytics.com",
    "googletagmanager.com", "googletagservices.com", "smartadserver.com",
    "mixpanel.com", "hotjar.com", "taboola.com", "outbrain.com",
    "adsystem.com", "amazon-adsystem.com", "pubmatic.com", "rubiconproject.com",
    "casalemedia.com", "criteo.com", "criteo.net", "moatads.com",
    "scorecardresearch.com", "quantserve.com", "adnxs.com", "bidswitch.net",
    "contextweb.com", "indexww.com", "openx.net", "sharethrough.com",
    "sovrn.com", "spotxchange.com", "teads.tv", "tremorhub.com", "yieldmo.com",
    "connatix.com", "permutive.com", "wisepops.com", "zetaglobal.com",
    "everesttech.net", "adform.net", "adroll.com", "bing.com/action",
    "facebook.net", "facebook.com/tr", "snapchat.com", "tiktok.com/i18n",
    "yandex.ru/metrika",
    # Smaller header-bidding/identity-sync networks observed on stocktwits.com.
    "ascendeummedia.com", "kargo.com", "gumgum.com", "adsrvr.org",
    "onetag-sys.com", "intentiq.com", "hypelab.com",
    # Deliberately NOT blocking onetrust.com/cookielaw.org: the page can wait
    # on the consent SDK before rendering the feed, so blocking it risks a
    # blank/stuck page instead of a faster one.
)

# Fingerprint of the rotating-domain session-replay vendor (html-load.com /
# duhquietly.com / content-loader.com are all the same integration, same URL
# shape, different root domain per session). Path structure is stable even
# when the domain isn't, so match on that instead of maintaining a whack-a-mole
# domain list every time it renames itself.
_BLOCKED_URL_PATTERNS = (
    re.compile(r"/loader\.min\.js"),
    re.compile(r"/script/stocktwits\.com\.js"),
    re.compile(r"^https?://\d+\.stg\."),          # N.stg.<whatever-today's-domain-is>
    re.compile(r"/session/.*stocktwits\.com/"),   # session beacon embedding our own hostname
)

# Dedicated event loop, same pattern as twikit_client — Playwright's async
# objects (Browser, Page) are bound to the loop active when they're created.
_LOOP = asyncio.new_event_loop()
nest_asyncio.apply(_LOOP)
asyncio.set_event_loop(_LOOP)


def run(coro):
    """Run a coroutine on the dedicated event loop."""
    return _LOOP.run_until_complete(coro)


class StocktwitsClient:
    """Thin async wrapper around Playwright, scoped to Stocktwits symbol streams."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._started: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self, headless: bool = True) -> None:
        if self._started:
            return
        self._playwright = await async_playwright().start()
        try:
            # patchright's anti-detection patches are most effective against
            # the real installed Chrome, not the bundled Chromium-for-Testing.
            self._browser = await self._playwright.chromium.launch(headless=headless, channel="chrome")
        except Exception:
            logger.warning("Chrome channel not available, falling back to bundled Chromium")
            self._browser = await self._playwright.chromium.launch(headless=headless)
        self._context = await self._browser.new_context()
        await self._context.route("**/*", self._route_handler)
        await self._load_cookies()
        self._started = True
        logger.info("Stocktwits Playwright client started")

    @staticmethod
    async def _route_handler(route) -> None:
        url = route.request.url
        blocked = (
            any(domain in url for domain in _BLOCKED_DOMAINS)
            or any(pattern.search(url) for pattern in _BLOCKED_URL_PATTERNS)
        )
        if blocked:
            await route.abort()
        else:
            await route.continue_()

    async def stop(self) -> None:
        if not self._started:
            return
        await self._save_cookies()
        await self._context.close()
        await self._browser.close()
        await self._playwright.stop()
        self._started = False
        logger.info("Stocktwits Playwright client stopped")

    # ------------------------------------------------------------------
    # Cookies (Cloudflare clearance + session), same pattern as twikit_client
    # ------------------------------------------------------------------
    async def _load_cookies(self) -> None:
        """Load cf_clearance + session cookies exported from a real browser.

        Cloudflare's Turnstile challenge detects Playwright/CDP automation and
        never resolves headlessly, so we can't solve it in-process. Instead we
        reuse a `cf_clearance` cookie captured by a logged-in human browser
        session (e.g. via the Cookie-Editor extension), same approach already
        used for X's session in twikit_client.
        """
        if not STOCKTWITS_COOKIES_FILE.exists():
            logger.warning(
                f"No Stocktwits cookies at {STOCKTWITS_COOKIES_FILE} — "
                "export them from a logged-in browser session (Cookie-Editor "
                "'Export' as JSON) before starting the client."
            )
            return
        try:
            raw = json.loads(STOCKTWITS_COOKIES_FILE.read_text())
            cookies = [self._normalize_cookie(c) for c in raw]
            await self._context.add_cookies(cookies)
            logger.debug(f"Loaded {len(cookies)} Stocktwits cookies")
        except Exception as exc:
            logger.warning(f"Failed to load Stocktwits cookies: {exc}")

    @staticmethod
    def _normalize_cookie(c: dict) -> dict:
        """Map Cookie-Editor export fields to Playwright's expected cookie shape."""
        same_site_map = {"no_restriction": "None", "lax": "Lax", "strict": "Strict", "unspecified": "Lax"}
        normalized = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".stocktwits.com"),
            "path": c.get("path", "/"),
            "secure": c.get("secure", True),
            "httpOnly": c.get("httpOnly", False),
        }
        same_site = c.get("sameSite")
        if isinstance(same_site, str):
            normalized["sameSite"] = same_site_map.get(same_site.lower(), "Lax")
        if "expirationDate" in c:
            normalized["expires"] = c["expirationDate"]
        return normalized

    async def _save_cookies(self) -> None:
        try:
            cookies = await self._context.cookies()
            STOCKTWITS_COOKIES_FILE.write_text(json.dumps(cookies))
            logger.debug(f"Saved {len(cookies)} Stocktwits cookies")
        except Exception as exc:
            logger.warning(f"Failed to save Stocktwits cookies: {exc}")

    # ------------------------------------------------------------------
    # Symbol stream capture
    # ------------------------------------------------------------------
    async def fetch_symbol_stream_sample(self, ticker: str, timeout_ms: int = 30_000) -> Optional[dict]:
        """Open the ticker page and return the first intercepted stream JSON payload.

        This is a Fase 2 probe: it proves the Cloudflare challenge can be
        passed headlessly and that the internal API response is reachable via
        response interception. No parsing/persistence yet — that's Fase 3+.
        """
        self._require_started()
        page: Page = await self._context.new_page()
        captured: dict = {}
        done = asyncio.Event()

        async def _on_response(response: Response) -> None:
            path = response.url.split("?", 1)[0]
            if "/api/2/streams/symbol/" in path and path.endswith(".json"):
                if response.status != 200:
                    logger.warning(f"Stream response {response.status} for {response.url}")
                    return
                try:
                    payload = await response.json()
                except Exception as exc:
                    logger.warning(f"Could not decode stream JSON ({response.url}): {exc}")
                    return
                captured["url"] = response.url
                captured["payload"] = payload
                done.set()

        page.on("response", lambda r: asyncio.create_task(_on_response(r)))

        try:
            url = f"https://stocktwits.com/symbol/{ticker.upper()}"
            logger.info(f"Opening {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                await asyncio.wait_for(done.wait(), timeout=timeout_ms / 1000)
            except asyncio.TimeoutError:
                logger.error(f"No stream JSON captured for {ticker} within {timeout_ms}ms — "
                              f"likely still behind Cloudflare challenge")
                return None
            logger.info(f"Captured stream response for {ticker}: {captured['url']}")
            return captured["payload"]
        finally:
            await page.close()

    # ------------------------------------------------------------------
    # Paginated history fetch
    # ------------------------------------------------------------------
    async def fetch_ticker_history(
        self,
        ticker: str,
        max_messages: int = 500,
        stop_before_id: Optional[int] = None,
        stop_before_date: Optional[str] = None,
        to_date: Optional[str] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        on_batch: Optional[Callable[[list[dict]], None]] = None,
        scroll_wait_s: float = 0.5,
        page_timeout_s: float = 35.0,
        max_scrolls: int = 400,
    ) -> list[dict]:
        """Walk the symbol stream backwards by scrolling the real page and
        intercepting each response the site issues on its own.

        A direct in-page fetch() to api.stocktwits.com fails (blocked at the
        network level even with valid cookies/CSP allowance) — only requests
        the page's own JS bundle issues (e.g. scrolling the last rendered
        message into view) go through. So we drive the UI instead of calling
        the API directly.

        Three things had to be true for pagination to actually walk backward
        through the whole history: (1) an authenticated session (anonymous
        sessions hit a hard 2-page/44-message cap — a soft "sign up to see
        more" wall); (2) `page.mouse.wheel` on the body doesn't reliably
        trigger the site's infinite-scroll fetch; and (3) neither does
        `scroll_into_view_if_needed()` on the last message link — it's a
        documented Playwright no-op once that element is already visible,
        which silently stalls pagination after page 1 on a short feed (the
        site just keeps re-firing its own ~4s live-update poll of the same
        top page instead). `page.evaluate("window.scrollTo(0,
        document.body.scrollHeight)")` is what actually advances the cursor.
        Blocking ad/tracker/session-replay traffic (see _BLOCKED_DOMAINS /
        _BLOCKED_URL_PATTERNS) cut per-page latency from up to ~45s down to
        a few seconds, hence the still-generous `page_timeout_s` margin.

        stop_before_id: stop once a message id <= this appears (already covered by a prior run).
        stop_before_date: ISO date string (lower bound) — stop once messages older than this appear.
        to_date: ISO date string (upper bound) — skip messages newer than this without stopping,
                 i.e. fast-forward through the top of the stream until we reach this window.
        should_stop: polled between pages; return True to stop early (e.g. a UI "Stop" button).
                     Whatever was already collected/handed to `on_batch` is kept.
        on_batch: called with each page's newly collected messages as soon as they arrive, so
                  the caller can persist incrementally instead of waiting for the whole run.
        """
        self._require_started()
        page: Page = await self._context.new_page()
        collected: list[dict] = []
        seen_ids: set[str] = set()
        queue: asyncio.Queue = asyncio.Queue()

        async def _on_response(response: Response) -> None:
            path = response.url.split("?", 1)[0]
            if "/api/2/streams/symbol/" in path and path.endswith(".json") and response.status == 200:
                try:
                    await queue.put(await response.json())
                except Exception:
                    pass

        # Attach the listener before navigating — the first symbol stream
        # call fires as part of the initial page load, not on scroll.
        page.on("response", lambda r: asyncio.create_task(_on_response(r)))
        url = f"https://stocktwits.com/symbol/{ticker.upper()}"
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        def _consume(payload: dict) -> tuple[bool, bool]:
            """Add new in-range messages from payload to `collected`. Returns (should_stop, has_more)."""
            batch: list[dict] = []
            stop = False
            for m in payload.get("messages", []):
                mid = str(m.get("id", ""))
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)
                if stop_before_id is not None and m.get("id", 0) <= stop_before_id:
                    stop = True
                    break
                created = str(m.get("created_at", ""))
                if stop_before_date is not None and created < stop_before_date:
                    stop = True
                    break
                if to_date is not None and created > to_date:
                    continue  # newer than the requested window — skip, keep paginating
                batch.append(m)
            collected.extend(batch)
            if batch and on_batch:
                on_batch(batch)
            cursor = payload.get("cursor") or {}
            return stop, bool(cursor.get("more"))

        try:
            try:
                first_payload = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                logger.error(f"No initial stream payload for {ticker} — page may still be behind Cloudflare")
                return collected
            stop, has_more = _consume(first_payload)

            scrolls = 0
            while not stop and has_more and len(collected) < max_messages and scrolls < max_scrolls:
                if should_stop and should_stop():
                    logger.info(f"Stopped by request for {ticker} after {scrolls} scrolls")
                    break
                # scroll_into_view_if_needed() on the last message link is a
                # documented Playwright no-op once that element is already
                # visible — which it is after the very first page on a short
                # feed. That silently stopped real pagination: the site kept
                # re-firing its own ~4s live-update poll of page 1 (same
                # cursor.max every time) instead of ever loading page 2+.
                # Forcing an actual scroll to the live bottom of the document
                # is what the site's infinite-scroll listener actually needs.
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                except Exception:
                    pass
                scrolls += 1
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=page_timeout_s)
                except asyncio.TimeoutError:
                    logger.info(f"No further pages for {ticker} after {scrolls} scrolls — assuming end of stream")
                    break
                stop, has_more = _consume(payload)
                await asyncio.sleep(scroll_wait_s)

            return collected[:max_messages]
        finally:
            await page.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("Client not started — call start() first")


# Module-level singleton, same pattern as twikit_client.twitter_client
stocktwits_client = StocktwitsClient()
