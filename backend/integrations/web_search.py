"""
openclaw/backend/integrations/web_search.py
Web search via DuckDuckGo Instant Answer API — no API key required.
Used by the risk classifier to enrich Mistral context with real-world info.
"""
import logging

import httpx

logger = logging.getLogger("openclaw.integrations.web_search")

_DDG_URL = "https://api.duckduckgo.com/"


async def search(query: str, max_results: int = 3) -> list[dict]:
    """
    Search DuckDuckGo for `query` and return up to `max_results` snippets.

    Each result is a dict with keys: title, snippet, url.
    Returns an empty list on any error (callers should degrade gracefully).
    """
    query = (query or "").strip()
    if len(query) < 8:
        return []

    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            resp = await client.get(
                _DDG_URL,
                params={
                    "q":              query,
                    "format":         "json",
                    "no_html":        "1",
                    "skip_disambig":  "1",
                    "no_redirect":    "1",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results: list[dict] = []

        # Primary abstract
        if data.get("Abstract"):
            results.append({
                "title":   data.get("Heading", query)[:120],
                "snippet": data["Abstract"][:400],
                "url":     data.get("AbstractURL", ""),
            })

        # Related topics
        for topic in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title":   (topic.get("Result") or "")[:120],
                    "snippet": topic["Text"][:400],
                    "url":     topic.get("FirstURL", ""),
                })

        logger.info(f"[web_search] '{query[:60]}' → {len(results)} result(s)")
        return results[:max_results]

    except Exception as exc:
        logger.warning(f"[web_search] Query failed for '{query[:60]}': {exc}")
        return []
