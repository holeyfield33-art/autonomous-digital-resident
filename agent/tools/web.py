"""Public-internet search and fetch. Loopback/private networks (Mneme, LAN) stay unreachable."""

import html
import ipaddress
import os
import re
import socket
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import httpx

from agent.tools.filesystem import redact

USER_AGENT = "Mozilla/5.0 (compatible; DigitalResident/0.3)"
MAX_BYTES = 2_000_000


def _public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only http(s) URLs with a hostname are supported")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not supported")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ConnectionError(f"Could not resolve {parsed.hostname}") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ValueError("Private, loopback and link-local addresses are not reachable from this tool")
    return url


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip, self.title, self.in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)

    def text(self):
        joined = "".join(self.parts)
        return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", joined)).strip()


def html_to_text(markup):
    parser = _Text()
    parser.feed(markup)
    return parser.title.strip(), parser.text()


class WebTools:
    def __init__(self, suggested_sources=()):
        self.suggested_sources = list(suggested_sources)

    def _client(self):
        return httpx.Client(timeout=20, follow_redirects=False, trust_env=False, headers={"User-Agent": USER_AGENT})

    def fetch(self, url: str, max_chars: int = 20000):
        """Fetch a public web page or text file; HTML is converted to readable text."""
        if type(max_chars) is not int or not 1 <= max_chars <= 40000:
            raise ValueError("max_chars must be 1..40000")
        current = url
        with self._client() as client:
            for _ in range(5):
                _public_url(current)
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        current = urljoin(current, response.headers.get("location", ""))
                        continue
                    raw = bytearray()
                    for chunk in response.iter_bytes(65536):
                        raw.extend(chunk)
                        if len(raw) > MAX_BYTES:
                            break
                    kind = response.headers.get("content-type", "")
                    status = response.status_code
                    break
            else:
                raise ConnectionError("Too many redirects")
        body = bytes(raw).decode(response.encoding or "utf-8", errors="replace")
        title = ""
        if "html" in kind or body.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
            title, body = html_to_text(body)
        return {
            "url": current,
            "status": status,
            "title": title,
            "content": redact(body[:max_chars]),
            "total_chars": len(body),
            "truncated": len(body) > max_chars,
            "provenance": "untrusted external source",
        }

    def search(self, query: str, max_results: int = 8):
        """Search the public web. Returns title, url and snippet for each result."""
        if not isinstance(query, str) or not query.strip() or len(query) > 400:
            raise ValueError("query must be 1..400 characters")
        if type(max_results) is not int or not 1 <= max_results <= 20:
            raise ValueError("max_results must be 1..20")
        if os.environ.get("TAVILY_API_KEY"):
            provider, results = "tavily", self._tavily(query, max_results)
        elif os.environ.get("BRAVE_API_KEY"):
            provider, results = "brave", self._brave(query, max_results)
        else:
            provider, results = "duckduckgo", self._duckduckgo(query, max_results)
        return {
            "query": query,
            "provider": provider,
            "results": [{k: redact(v) for k, v in r.items()} for r in results],
            "provenance": "untrusted external source",
        }

    def _tavily(self, query, limit):
        with self._client() as client:
            response = client.post(
                "https://api.tavily.com/search",
                json={"api_key": os.environ["TAVILY_API_KEY"], "query": query, "max_results": limit},
            )
            response.raise_for_status()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")[:500]}
            for r in response.json().get("results", [])
        ]

    def _brave(self, query, limit):
        with self._client() as client:
            response = client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": limit},
                headers={"X-Subscription-Token": os.environ["BRAVE_API_KEY"], "Accept": "application/json"},
            )
            response.raise_for_status()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")[:500]}
            for r in response.json().get("web", {}).get("results", [])[:limit]
        ]

    def _duckduckgo(self, query, limit):
        with self._client() as client:
            response = client.post("https://html.duckduckgo.com/html/", data={"q": query})
            response.raise_for_status()
        page = response.text
        links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page, re.S)
        results = []
        for index, (href, title) in enumerate(links):
            if "duckduckgo.com/y.js" in href:  # sponsored
                continue
            if "uddg=" in href:
                href = unquote(parse_qs(urlsplit(href).query).get("uddg", [href])[0])
            clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()  # noqa: E731
            results.append(
                {"title": clean(title), "url": href, "snippet": clean(snippets[index]) if index < len(snippets) else ""}
            )
            if len(results) >= limit:
                break
        if not results and "anomaly" in page.lower():
            raise ConnectionError("DuckDuckGo rate-limited this search; try again later or set TAVILY_API_KEY")
        return results
