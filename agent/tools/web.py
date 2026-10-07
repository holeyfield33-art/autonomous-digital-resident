"""Opt-in exact-URL reader. The model cannot construct exfiltration URLs."""

from urllib.parse import urlsplit

import httpx


class WebTools:
    def __init__(self, allowed_urls=()):
        self.allowed_urls = frozenset(allowed_urls)
        for url in self.allowed_urls:
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.username
                or parsed.password
                or parsed.port not in (None, 443)
            ):
                raise ValueError("Sources must be operator-selected HTTPS URLs")

    def fetch(self, url):
        if url not in self.allowed_urls:
            raise ValueError("URL not in operator-selected source catalog")
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", url, headers={"User-Agent": "DigitalResident/0.2"}) as response:
                response.raise_for_status()
                raw = bytearray()
                for chunk in response.iter_bytes(chunk_size=4096):
                    raw.extend(chunk)
                    if len(raw) > 16000:
                        break
                from agent.tools.filesystem import check_text

                text = bytes(raw[:16000]).decode("utf-8", errors="replace")
                check_text(text)
                return {
                    "url": url,
                    "content": text,
                    "truncated": len(raw) > 16000,
                    "provenance": "untrusted external source",
                }
