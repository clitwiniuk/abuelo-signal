"""Manual Fase 5 probe — inspect pagination behaviour on scroll.

Usage:
    python -m stocktwits_client.probe TSLA
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from stocktwits_client.client import stocktwits_client, run
from utils.logger import logger

calls = []


async def _main(ticker: str) -> None:
    await stocktwits_client.start(headless=False)
    try:
        page = await stocktwits_client._context.new_page()

        async def on_response(r):
            if "/api/2/streams/symbol/" in r.url:
                try:
                    payload = await r.json()
                    calls.append({"url": r.url, "n_messages": len(payload.get("messages", [])),
                                   "cursor": payload.get("cursor")})
                    logger.info(f"call: {r.url} -> {len(payload.get('messages', []))} msgs, cursor={payload.get('cursor')}")
                except Exception:
                    pass

        page.on("response", lambda r: page.context.__class__ and None or None)
        page.on("response", lambda r: sys_hook(r))

        def sys_hook(r):
            import asyncio
            asyncio.create_task(on_response(r))

        url = f"https://stocktwits.com/symbol/{ticker.upper()}"
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(4_000)

        # try clicking "All" tab if present
        try:
            all_tab = page.get_by_text("All", exact=True)
            if await all_tab.count() > 0:
                await all_tab.first.click()
                await page.wait_for_timeout(2_000)
                logger.info("Clicked 'All' tab")
        except Exception as e:
            logger.warning(f"No All tab: {e}")

        for i in range(4):
            await page.mouse.wheel(0, 4000)
            await page.wait_for_timeout(2_000)
            logger.info(f"scroll {i+1} done")

        await page.close()
        with open("/tmp/st_calls.json", "w") as f:
            json.dump(calls, f, indent=2)
    finally:
        await stocktwits_client.stop()


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "TSLA"
    run(_main(ticker))
