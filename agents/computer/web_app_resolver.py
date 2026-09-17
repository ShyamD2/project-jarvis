"""
Intelligent Web, App & Music Resolver for Project J.A.R.V.I.S.
Parses natural language requests to open websites, applications, and streaming music:
- "play believer in amazon music"
- "play starboy on spotify"
- "open prime video"
- "open ibm career website"
- "amazon music on web"
"""
from __future__ import annotations
import os
import sys
import re
import urllib.parse
import webbrowser
from typing import Dict, Any, Optional, Tuple

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisWebAppResolver")

CANONICAL_DOMAINS = {
    # Streaming & Media
    "prime video": "https://www.primevideo.com",
    "amazon prime": "https://www.primevideo.com",
    "primevideo": "https://www.primevideo.com",
    "amazon prime video": "https://www.primevideo.com",
    "netflix": "https://www.netflix.com",
    "hotstar": "https://www.hotstar.com",
    "disney plus": "https://www.hotstar.com",
    "disney+": "https://www.hotstar.com",
    "youtube": "https://www.youtube.com",
    "youtube music": "https://music.youtube.com",
    "spotify": "https://open.spotify.com",
    "amazon music": "https://music.amazon.com",
    "amazon music on web": "https://music.amazon.com",
    "apple music": "https://music.apple.com",
    "soundcloud": "https://soundcloud.com",
    "twitch": "https://www.twitch.tv",

    # Corporate & Careers
    "ibm career": "https://www.ibm.com/careers",
    "ibm careers": "https://www.ibm.com/careers",
    "ibm career website": "https://www.ibm.com/careers",
    "google career": "https://careers.google.com",
    "google careers": "https://careers.google.com",
    "microsoft career": "https://careers.microsoft.com",
    "microsoft careers": "https://careers.microsoft.com",
    "apple career": "https://www.apple.com/careers",
    "apple careers": "https://www.apple.com/careers",
    "amazon career": "https://www.amazon.jobs",
    "amazon careers": "https://www.amazon.jobs",
    "amazon jobs": "https://www.amazon.jobs",
    "meta career": "https://www.metacareers.com",
    "meta careers": "https://www.metacareers.com",
    "tcs careers": "https://www.tcs.com/careers",
    "infosys careers": "https://www.infosys.com/careers.html",

    # Productivity & Social
    "linkedin": "https://www.linkedin.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "openai": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "gmail": "https://mail.google.com",
    "google mail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "whatsapp": "https://web.whatsapp.com",
    "whatsapp web": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "telegram web": "https://web.telegram.org",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
    "reddit": "https://www.reddit.com",
    "facebook": "https://www.facebook.com",
    "wikipedia": "https://www.wikipedia.org",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
}

MUSIC_PLATFORM_PATTERNS = {
    "youtube music": ("YouTube Music", "https://music.youtube.com/search?q="),
    "yt music": ("YouTube Music", "https://music.youtube.com/search?q="),
    "youtube": ("YouTube", "https://www.youtube.com/results?search_query="),
    "spotify": ("Spotify", "https://open.spotify.com/search/"),
    "amazon music": ("Amazon Music", "https://music.amazon.com/search/"),
    "amazon": ("Amazon Music", "https://music.amazon.com/search/"),
    "apple music": ("Apple Music", "https://music.apple.com/search?term="),
    "apple": ("Apple Music", "https://music.apple.com/search?term="),
    "soundcloud": ("SoundCloud", "https://soundcloud.com/search?q="),
    "jiosaavn": ("JioSaavn", "https://www.jiosaavn.com/search/"),
    "saavn": ("JioSaavn", "https://www.jiosaavn.com/search/"),
    "gaana": ("Gaana", "https://gaana.com/search/"),
}


class WebAppResolver:
    """Smart resolver for web addresses, music streaming, and corporate destinations."""

    def parse_music_intent(self, text: str) -> Optional[Tuple[str, str, str]]:
        """
        Extracts (song_name, platform_name, playback_url) from music intent.
        Handles phrases like:
        - "play believer in amazon music"
        - "play starboy on spotify"
        - "play shape of you on youtube"
        - "play believer"
        """
        clean = text.strip()
        lower = clean.lower()

        # Check if starts with play or stream
        m = re.match(r"^(?:play|stream|listen to)\s+(.+)$", lower, re.IGNORECASE)
        if not m:
            return None

        content = m.group(1).strip()

        # Check for specified platform suffix ("in/on <platform>")
        # e.g., "believer in amazon music", "believer on youtube music", "believer on spotify"
        detected_platform = None
        song_name = content

        for plat_key, (plat_name, search_base) in MUSIC_PLATFORM_PATTERNS.items():
            pattern = rf"^(.+?)\s+(?:in|on|using|via|at)\s+{re.escape(plat_key)}$"
            match_plat = re.match(pattern, content, re.IGNORECASE)
            if match_plat:
                song_name = match_plat.group(1).strip()
                detected_platform = plat_key
                break

        # If no specific platform matched via regex suffix, check if platform is prefix:
        # e.g., "play on spotify believer"
        if not detected_platform:
            for plat_key, (plat_name, search_base) in MUSIC_PLATFORM_PATTERNS.items():
                pattern = rf"^(?:on|in|using|via)\s+{re.escape(plat_key)}\s+(.+)$"
                match_prefix = re.match(pattern, content, re.IGNORECASE)
                if match_prefix:
                    song_name = match_prefix.group(1).strip()
                    detected_platform = plat_key
                    break

        # Default platform if none specified is YouTube Music (or YouTube)
        if not detected_platform:
            detected_platform = "youtube"

        plat_name, search_base = MUSIC_PLATFORM_PATTERNS.get(detected_platform, ("YouTube", "https://www.youtube.com/results?search_query="))
        encoded = urllib.parse.quote(song_name)
        final_url = f"{search_base}{encoded}"
        return song_name, plat_name, final_url

    def resolve_destination(self, query: str) -> Dict[str, Any]:
        """
        Intelligently resolves any website or application query to its exact target URL:
        - Exact canonical mappings ("prime video" -> https://www.primevideo.com)
        - Direct URLs / domains ("github.com", "https://...")
        - Search query fallback using Google Feeling-Lucky direct redirect
        """
        q = query.strip()
        lower = q.lower()

        # Strip common conversational prefixes
        lower = re.sub(r"^(?:open|launch|go to|visit|show|search for)\s+", "", lower).strip()
        lower = re.sub(r"\s+on\s+web$", "", lower).strip()
        lower = re.sub(r"\s+in\s+browser$", "", lower).strip()

        # 1. Exact canonical mapping match
        if lower in CANONICAL_DOMAINS:
            return {
                "success": True,
                "type": "canonical",
                "name": lower.title(),
                "url": CANONICAL_DOMAINS[lower]
            }

        # Substring / fuzzy check in canonical domains
        for key, url in CANONICAL_DOMAINS.items():
            if lower == key or (len(lower) > 3 and lower in key):
                return {
                    "success": True,
                    "type": "canonical",
                    "name": key.title(),
                    "url": url
                }

        # 2. Check if already a valid URL or domain
        if re.match(r"^https?://", q, re.IGNORECASE):
            return {"success": True, "type": "url", "name": q, "url": q}

        domain_match = re.match(r"^([a-zA-Z0-9-]+\.)+(com|org|net|io|in|co|gov|edu|ai|app|dev|tv|me)(\/.*)?$", q, re.IGNORECASE)
        if domain_match:
            return {"success": True, "type": "domain", "name": q, "url": f"https://{q}"}

        # 3. Intelligent Google "I'm Feeling Lucky" direct redirection:
        # Google's btnI=1 takes the browser directly to the top relevant corporate/destination page
        encoded_query = urllib.parse.quote(lower)
        feeling_lucky_url = f"https://www.google.com/search?q={encoded_query}&btnI=1"
        return {
            "success": True,
            "type": "search_direct",
            "name": q.title(),
            "url": feeling_lucky_url,
            "fallback_search": f"https://www.google.com/search?q={encoded_query}"
        }

    def open_target(self, query: str) -> Dict[str, Any]:
        """Resolves target and opens it in default Windows browser."""
        def _launch_url(target_url: str):
            try:
                from agents.computer.windows_agent import windows_agent
                windows_agent.open_url(target_url)
            except Exception:
                webbrowser.open(target_url)

        # 1. First check if it is a music playback request
        music_info = self.parse_music_intent(query)
        if music_info:
            song, platform, url = music_info
            logger.info(f"🎵 [WebAppResolver] Opening '{song}' on {platform}: {url}")
            _launch_url(url)
            return {
                "success": True,
                "is_music": True,
                "song": song,
                "platform": platform,
                "url": url,
                "message": f"🎵 Playing *{song.title()}* on *{platform}*!"
            }

        # 2. Otherwise resolve destination URL
        dest = self.resolve_destination(query)
        target_url = dest.get("url")
        name = dest.get("name", query)
        logger.info(f"🌐 [WebAppResolver] Opening '{name}': {target_url}")
        _launch_url(target_url)
        return {
            "success": True,
            "is_music": False,
            "name": name,
            "url": target_url,
            "type": dest.get("type"),
            "message": f"🌐 Opened *{name}* in your browser!"
        }


web_app_resolver = WebAppResolver()
