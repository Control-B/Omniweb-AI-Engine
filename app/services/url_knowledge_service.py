from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx


class UrlKnowledgeService:
    """Lightweight URL-based knowledge ingestion for tenant websites.

    V1 goal: ingest subscriber URL content quickly without adding new infra.
    """

    MAX_PAGES = 12
    MAX_CHARS_PER_PAGE = 8000
    REQUEST_TIMEOUT_SECONDS = 12.0

    @staticmethod
    async def ingest_website(url: str, *, max_pages: int | None = None) -> dict:
        target_pages = max(1, min(max_pages or UrlKnowledgeService.MAX_PAGES, 30))
        normalized = UrlKnowledgeService._normalize_url(url)
        parsed = urlparse(normalized)
        root = f"{parsed.scheme}://{parsed.netloc}"

        seen: set[str] = set()
        queue: list[str] = [normalized]
        pages: list[dict] = []

        async with httpx.AsyncClient(
            timeout=UrlKnowledgeService.REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            while queue and len(pages) < target_pages:
                current = queue.pop(0)
                if current in seen:
                    continue
                seen.add(current)
                try:
                    resp = await client.get(current)
                except Exception:
                    continue
                ctype = (resp.headers.get("content-type") or "").lower()
                if resp.status_code >= 400 or "text/html" not in ctype:
                    continue
                html = resp.text
                text = UrlKnowledgeService._extract_text(html)[: UrlKnowledgeService.MAX_CHARS_PER_PAGE]
                if len(text) < 80:
                    continue
                title = UrlKnowledgeService._extract_title(html) or current
                pages.append({"url": current, "title": title, "text": text})
                for link in UrlKnowledgeService._extract_links(html, base=current):
                    if not link.startswith(root):
                        continue
                    if UrlKnowledgeService._looks_like_content_url(link):
                        queue.append(link)

        summary = UrlKnowledgeService._build_summary(pages)
        return {
            "source_url": normalized,
            "pages_crawled": len(pages),
            "pages": pages,
            "summary": summary,
        }

    @staticmethod
    def _normalize_url(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            raise ValueError("URL is required")
        if not raw.startswith(("http://", "https://")):
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        if not parsed.netloc:
            raise ValueError("Invalid URL")
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"

    @staticmethod
    def _extract_title(html: str) -> str | None:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            return None
        return UrlKnowledgeService._clean_text(m.group(1))

    @staticmethod
    def _extract_text(html: str) -> str:
        content = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        content = re.sub(r"(?is)<style.*?>.*?</style>", " ", content)
        content = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", content)
        content = re.sub(r"(?is)<[^>]+>", " ", content)
        return UrlKnowledgeService._clean_text(content)

    @staticmethod
    def _extract_links(html: str, *, base: str) -> list[str]:
        links: list[str] = []
        for href in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            links.append(urljoin(base, href))
        return links

    @staticmethod
    def _looks_like_content_url(url: str) -> bool:
        lower = url.lower()
        blocked_fragments = ["/cart", "/account", "/checkout", "/collections/all?"]
        blocked_ext = [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf", ".zip"]
        if any(f in lower for f in blocked_fragments):
            return False
        if any(lower.endswith(ext) for ext in blocked_ext):
            return False
        return True

    @staticmethod
    def _clean_text(text: str) -> str:
        t = unescape(text or "")
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @staticmethod
    def _build_summary(pages: list[dict]) -> str:
        if not pages:
            return ""
        lines = [
            "Knowledge extracted from merchant website. Use this as grounded context for product/service explanations and site guidance.",
        ]
        for page in pages[:10]:
            lines.append(f"- {page.get('title')}: {page.get('url')}")
            snippet = (page.get("text") or "")[:450]
            if snippet:
                lines.append(f"  {snippet}")
        return "\n".join(lines)
