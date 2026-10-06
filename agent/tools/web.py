"""Web tools — fetch public pages for research."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


class WebTools:
    def __init__(self, timeout: float = 20.0, max_chars: int = 30_000) -> None:
        self.timeout = timeout
        self.max_chars = max_chars

    def fetch(self, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return {"error": "Only http/https URLs are allowed", "url": url}
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "AutonomousDigitalResident/0.1"})
            text = resp.text[: self.max_chars]
            return {
                "url": str(resp.url),
                "status_code": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "content": text,
                "truncated": len(resp.text) > self.max_chars,
            }
        except Exception as e:
            return {"error": str(e), "url": url}
