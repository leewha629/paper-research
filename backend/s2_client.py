import asyncio
import httpx
from typing import Optional, List

S2_BASE = "https://api.semanticscholar.org/graph/v1"

PAPER_SEARCH_FIELDS = "title,authors,year,venue,abstract,externalIds,openAccessPdf,citationCount,referenceCount,fieldsOfStudy,isOpenAccess"
PAPER_DETAIL_FIELDS = "title,authors,year,venue,abstract,externalIds,openAccessPdf,citationCount,referenceCount,fieldsOfStudy,isOpenAccess"
REFERENCE_FIELDS = "title,authors,year,venue,citationCount,externalIds,isOpenAccess,openAccessPdf,abstract"


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
        fields_of_study: List[str] = None,
        venue: List[str] = None,
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
        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)
        return await self._get(f"{S2_BASE}/paper/search", params)

    async def search_by_author(self, author_name: str, limit: int = 20) -> dict:
        """저자 이름으로 논문 검색"""
        params = {
            "query": author_name,
            "limit": limit,
            "fields": "name,paperCount,citationCount,papers.title,papers.year,papers.paperId,papers.citationCount,papers.venue",
        }
        return await self._get(f"{S2_BASE}/author/search", params)

    async def get_author_papers(self, author_id: str, limit: int = 50) -> dict:
        """특정 저자의 논문 목록"""
        params = {
            "fields": PAPER_SEARCH_FIELDS,
            "limit": limit,
        }
        return await self._get(f"{S2_BASE}/author/{author_id}/papers", params)

    async def get_paper(self, paper_id: str) -> dict:
        params = {"fields": PAPER_DETAIL_FIELDS}
        return await self._get(f"{S2_BASE}/paper/{paper_id}", params)

    async def get_references(self, paper_id: str, limit: int = 50) -> dict:
        params = {"fields": REFERENCE_FIELDS, "limit": limit}
        return await self._get(f"{S2_BASE}/paper/{paper_id}/references", params)

    async def get_citations(self, paper_id: str, limit: int = 50) -> dict:
        params = {"fields": REFERENCE_FIELDS, "limit": limit}
        return await self._get(f"{S2_BASE}/paper/{paper_id}/citations", params)

    async def get_recommendations(self, paper_id: str, limit: int = 10) -> dict:
        params = {"fields": REFERENCE_FIELDS, "limit": limit}
        try:
            return await self._get(
                f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}",
                params,
            )
        except Exception:
            return {"recommendedPapers": []}

    async def bulk_search(
        self,
        queries: List[str],
        limit_per_query: int = 20,
        delay: float = 1.5,
        year_from: int = None,
        year_to: int = None,
        open_access_only: bool = False,
        fields_of_study: List[str] = None,
        venue: List[str] = None,
    ) -> List[dict]:
        """여러 쿼리를 순차 실행하고 결과를 합침. 각 쿼리 결과에 query 필드 추가."""
        all_results = []
        for i, q in enumerate(queries):
            try:
                result = await self.search(
                    query=q,
                    limit=limit_per_query,
                    year_from=year_from,
                    year_to=year_to,
                    open_access_only=open_access_only,
                    fields_of_study=fields_of_study,
                    venue=venue,
                )
                papers = result.get("data") or []
                for p in papers:
                    p["_query"] = q
                    p["_query_index"] = i
                all_results.extend(papers)
            except RateLimitError:
                pass
            except Exception:
                pass
            if i < len(queries) - 1:
                await asyncio.sleep(delay)
        return all_results
