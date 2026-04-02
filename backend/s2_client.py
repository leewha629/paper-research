import asyncio
import httpx
from typing import Optional

S2_BASE = "https://api.semanticscholar.org/graph/v1"

PAPER_SEARCH_FIELDS = "title,authors,year,venue,abstract,externalIds,openAccessPdf,citationCount,referenceCount,fieldsOfStudy,isOpenAccess"
PAPER_DETAIL_FIELDS = "title,authors,year,venue,abstract,externalIds,openAccessPdf,citationCount,referenceCount,fieldsOfStudy,isOpenAccess"
REFERENCE_FIELDS = "title,authors,year,venue,citationCount,externalIds,isOpenAccess,openAccessPdf"


class RateLimitError(Exception):
    pass


class NotFoundError(Exception):
    pass


class S2Client:
    def __init__(self, api_key: Optional[str] = None):
        self.headers = {"x-api-key": api_key} if api_key else {}

    async def _get(self, url: str, params: dict = None) -> dict:
        """GET with exponential backoff: 5s -> 10s -> 30s on 429"""
        delays = [5, 10, 30]
        last_error = None

        async with httpx.AsyncClient(timeout=20.0) as client:
            for attempt in range(len(delays) + 1):
                if attempt > 0:
                    delay = delays[attempt - 1]
                    await asyncio.sleep(delay)
                try:
                    resp = await client.get(url, params=params or {}, headers=self.headers)
                    if resp.status_code == 200:
                        return resp.json()
                    if resp.status_code == 429:
                        last_error = RateLimitError(f"Rate limit hit on attempt {attempt + 1}")
                        if attempt < len(delays):
                            continue
                        raise RateLimitError(f"Rate limit exceeded after {len(delays)} retries")
                    if resp.status_code == 404:
                        raise NotFoundError(f"Not found: {url}")
                    resp.raise_for_status()
                except (RateLimitError, NotFoundError):
                    raise
                except httpx.TimeoutException as e:
                    raise httpx.TimeoutException(f"Request timed out: {url}") from e

        if last_error:
            raise last_error
        raise Exception(f"Failed to get {url}")

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        year_from: int = None,
        year_to: int = None,
        open_access_only: bool = False,
    ) -> dict:
        params = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "fields": PAPER_SEARCH_FIELDS,
        }
        if year_from or year_to:
            params["year"] = f"{year_from or ''}-{year_to or ''}"
        if open_access_only:
            params["openAccessPdf"] = ""
        return await self._get(f"{S2_BASE}/paper/search", params)

    async def get_paper(self, paper_id: str) -> dict:
        """Get full paper details"""
        params = {"fields": PAPER_DETAIL_FIELDS}
        return await self._get(f"{S2_BASE}/paper/{paper_id}", params)

    async def get_references(self, paper_id: str, limit: int = 50) -> dict:
        params = {"fields": REFERENCE_FIELDS, "limit": limit}
        return await self._get(f"{S2_BASE}/paper/{paper_id}/references", params)

    async def get_citations(self, paper_id: str, limit: int = 50) -> dict:
        params = {"fields": REFERENCE_FIELDS, "limit": limit}
        return await self._get(f"{S2_BASE}/paper/{paper_id}/citations", params)

    async def get_recommendations(self, paper_id: str) -> dict:
        params = {"fields": REFERENCE_FIELDS, "limit": 10}
        try:
            return await self._get(
                f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}",
                params,
            )
        except Exception:
            return {"recommendedPapers": []}
