"""
Browser & Web Agent for J.A.R.V.I.S.
Executes web searches, extracts webpage markdown, and supports browser navigation.
"""

from __future__ import annotations
import httpx
import re
from typing import Dict, Any, List
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisBrowserAgent")


class BrowserAgent:
    async def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Performs lightweight web search using DuckDuckGo HTML endpoint"""
        logger.info(f"[BrowserAgent] Performing web search for: '{query}'")
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        results = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data={"q": query}, headers=headers)
                # Parse snippet results via regex
                snippets = re.findall(r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>.*?</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
                for href, snippet in snippets[:max_results]:
                    clean_snip = re.sub(r'<[^>]+>', '', snippet).strip()
                    results.append({"url": href.strip(), "snippet": clean_snip})
        except Exception as e:
            logger.warning(f"Web search query failed: {e}")

        # Fallback if network fails
        if not results:
            results.append({
                "url": f"https://duckduckgo.com/?q={query}",
                "snippet": f"Search results for: {query}"
            })
        return results

    async def fetch_page_summary(self, url: str) -> Dict[str, Any]:
        """Fetches and extracts clean text summary from a webpage"""
        logger.info(f"[BrowserAgent] Fetching webpage: {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, follow_redirects=True)
                clean_text = re.sub(r'<[^>]+>', ' ', resp.text)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                return {"success": True, "url": url, "content": clean_text[:1500]}
        except Exception as e:
            logger.error(f"[BrowserAgent] Failed to fetch webpage '{url}': {e}")
            return {"success": False, "error": str(e)}


browser_agent = BrowserAgent()
