"""
Browser & Web Agent for J.A.R.V.I.S.
Executes web searches, Playwright CDP browser automation, and live DOM extraction.
Connects to operator's existing Chrome/Edge profile via port 9222 or lightweight HTTP fallbacks.
"""

from __future__ import annotations
import os
import re
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisBrowserAgent")


class BrowserAgent:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self.cdp_url = os.getenv("CHROME_CDP_URL", "http://127.0.0.1:9222")

    async def _is_cdp_available(self) -> bool:
        """Quick non-blocking probe to verify if Chrome DevTools Protocol port is open."""
        try:
            async with httpx.AsyncClient(timeout=0.6) as client:
                resp = await client.get(f"{self.cdp_url}/json/version")
                return resp.status_code == 200
        except Exception:
            return False

    def _find_browser_executable(self) -> Optional[str]:
        """Locates Chrome or Edge browser binary on Windows."""
        import shutil
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            shutil.which("chrome"),
            shutil.which("msedge")
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return None

    async def _launch_managed_cdp_browser(self) -> bool:
        """Launches a controlled browser process with --remote-debugging-port=9222."""
        exe = self._find_browser_executable()
        if not exe:
            logger.warning("[BrowserAgent] No Chrome or Edge executable found to auto-launch.")
            return False

        profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/browser_cdp_profile"))
        os.makedirs(profile_dir, exist_ok=True)

        cmd = [
            exe,
            "--remote-debugging-port=9222",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check"
        ]

        logger.info(f"[BrowserAgent] Auto-spawning controlled browser session: {exe} on port 9222...")
        try:
            import subprocess
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Poll for readiness up to 4 seconds
            for _ in range(20):
                await asyncio.sleep(0.2)
                if await self._is_cdp_available():
                    logger.info("[BrowserAgent] Managed browser session is ready on port 9222.")
                    return True
        except Exception as e:
            logger.error(f"[BrowserAgent] Failed to spawn managed browser session: {e}")

        return False

    async def _get_cdp_page(self):
        """Connects or reconnects to running Chrome/Edge instance via Chrome DevTools Protocol."""
        # 1. Self-healing check: if already connected and page is alive, return it
        try:
            if self._browser and self._browser.is_connected() and self._page and not self._page.is_closed():
                return self._page
        except Exception:
            pass

        # 2. Reset invalid handles
        self._browser = None
        self._page = None

        # 3. Check if CDP port is open; if not, auto-launch managed browser
        if not await self._is_cdp_available():
            await self._launch_managed_cdp_browser()

        # 4. Connect over CDP via Playwright
        try:
            from playwright.async_api import async_playwright
            if self._playwright is None:
                self._playwright = await async_playwright().start()

            if await self._is_cdp_available():
                self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
                contexts = self._browser.contexts
                if contexts and contexts[0].pages:
                    self._page = contexts[0].pages[0]
                else:
                    context = contexts[0] if contexts else await self._browser.new_context()
                    self._page = await context.new_page()
                logger.info("[BrowserAgent] Successfully attached Playwright to CDP session.")
                return self._page
            else:
                logger.debug("[BrowserAgent] CDP port 9222 not reachable. Using lightweight HTTP mode.")
                return None
        except Exception as e:
            logger.debug(f"[BrowserAgent] CDP connection error ({e}). Using lightweight HTTP mode.")
            return None

    async def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Performs web search using DuckDuckGo HTML endpoint with Playwright option."""
        logger.info(f"[BrowserAgent] Performing web search for: '{query}'")
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        results = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data={"q": query}, headers=headers)
                snippets = re.findall(
                    r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>.*?</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
                    resp.text,
                    re.DOTALL
                )
                for href, snippet in snippets[:max_results]:
                    clean_snip = re.sub(r'<[^>]+>', '', snippet).strip()
                    results.append({"url": href.strip(), "snippet": clean_snip})
        except Exception as e:
            logger.warning(f"Web search query failed: {e}")

        if not results:
            results.append({
                "url": f"https://duckduckgo.com/?q={query}",
                "snippet": f"Search results for: {query}"
            })
        return results

    async def fetch_page_summary(self, url: str) -> Dict[str, Any]:
        """Fetches and extracts clean text summary from a webpage using CDP or HTTP."""
        logger.info(f"[BrowserAgent] Fetching webpage: {url}")
        
        # Try Playwright CDP first
        page = await self._get_cdp_page()
        if page:
            try:
                await page.goto(url, timeout=12000)
                await page.wait_for_load_state("domcontentloaded")
                title = await page.title()
                content = await page.evaluate("() => document.body.innerText")
                clean_text = re.sub(r'\s+', ' ', content).strip()
                return {
                    "success": True,
                    "method": "playwright_cdp",
                    "url": url,
                    "title": title,
                    "content": clean_text[:2500]
                }
            except Exception as e:
                logger.debug(f"[BrowserAgent] CDP navigation failed: {e}. Falling back to HTTP.")

        # HTTP Fallback
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = await client.get(url, headers=headers, follow_redirects=True)
                clean_text = re.sub(r'<[^>]+>', ' ', resp.text)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                return {"success": True, "method": "httpx_fallback", "url": url, "content": clean_text[:2000]}
        except Exception as e:
            logger.error(f"[BrowserAgent] Failed to fetch webpage '{url}': {e}")
            return {"success": False, "error": str(e)}

    async def navigate_and_click(self, url: str, selector: str) -> Dict[str, Any]:
        """Navigates to URL and clicks selector via Playwright CDP."""
        page = await self._get_cdp_page()
        if not page:
            return {"success": False, "error": "Playwright CDP connection not active. Start browser with --remote-debugging-port=9222"}
        try:
            await page.goto(url, timeout=10000)
            await page.wait_for_selector(selector, timeout=5000)
            await page.click(selector)
            return {"success": True, "action": "click", "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        """Closes Playwright connection cleanly."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass


browser_agent = BrowserAgent()
