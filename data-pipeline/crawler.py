from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class CrawledChunk:
    category: str
    subcategory: str
    content: str
    source_url: str
    crawled_at: datetime


async def crawl_page(url: str, category: str, subcategory: str) -> list[CrawledChunk]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for item in soup(["script", "style", "noscript"]):
        item.decompose()
    text = " ".join(soup.get_text(" ").split())
    return [
        CrawledChunk(
            category=category,
            subcategory=subcategory,
            content=part,
            source_url=url,
            crawled_at=datetime.now(UTC),
        )
        for part in chunk_text(text)
    ]


def chunk_text(text: str, max_chars: int = 800) -> list[str]:
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars) if text[index:]]
