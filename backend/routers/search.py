import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import Paper, AppSetting, SearchCache, SearchHistory
from s2_client import S2Client, RateLimitError, NotFoundError
from ai_client import AIClient

router = APIRouter(prefix="/search", tags=["search"])

CACHE_TTL_HOURS = 24
QUERY_DELAY_SECONDS = 1.5
S2_RESULTS_PER_QUERY = 20
RELEVANCE_THRESHOLD = 6      # 이 점수 이상만 메인 결과로 표시
ABSTRACT_PREVIEW_CHARS = 400 # 스코어링 시 초록 앞부분만 사용


# ─── Normalize helpers ────────────────────────────────────────────────────────

def get_s2_client(db: Session) -> S2Client:
    s = db.query(AppSetting).filter(AppSetting.key == "semantic_scholar_api_key").first()
    return S2Client(api_key=s.value if s and s.value else None)


def normalize_paper(data: dict, saved_ids: set = None) -> dict:
    authors = data.get("authors") or []
    authors_list = [{"name": a.get("name", ""), "affiliations": a.get("affiliations", [])} for a in authors]
    external_ids = data.get("externalIds") or {}
    open_access_pdf = data.get("openAccessPdf") or {}
    pdf_url = open_access_pdf.get("url") if open_access_pdf else None
    paper_id = data.get("paperId", "")
    return {
        "paper_id": paper_id,
        "title": data.get("title", ""),
        "authors_json": json.dumps(authors_list, ensure_ascii=False),
        "authors": authors_list,
        "year": data.get("year"),
        "venue": data.get("venue"),
        "abstract": data.get("abstract"),
        "doi": external_ids.get("DOI"),
        "citation_count": data.get("citationCount") or 0,
        "reference_count": data.get("referenceCount") or 0,
        "is_open_access": data.get("isOpenAccess") or False,
        "pdf_url": pdf_url,
        "external_ids_json": json.dumps(external_ids, ensure_ascii=False),
        "fields_of_study_json": json.dumps(data.get("fieldsOfStudy") or [], ensure_ascii=False),
        "is_saved": paper_id in (saved_ids or set()),
        "query_hit_count": 1,
        "relevance_score": None,
    }


def normalize_ref_paper(data: dict) -> dict:
    authors = data.get("authors") or []
    external_ids = data.get("externalIds") or {}
    open_access_pdf = data.get("openAccessPdf") or {}
    return {
        "paper_id": data.get("paperId", ""),
        "title": data.get("title", ""),
        "authors": [{"name": a.get("name", ""), "affiliations": []} for a in authors],
        "year": data.get("year"),
        "venue": data.get("venue"),
        "citation_count": data.get("citationCount") or 0,
        "is_open_access": data.get("isOpenAccess") or False,
        "doi": external_ids.get("DOI"),
        "pdf_url": (open_access_pdf.get("url") if open_access_pdf else None),
        "external_ids": external_ids,
    }


def merge_results(all_papers: list, saved_ids: set) -> list:
    """중복 제거, query_hit_count 집계, 인용수 정렬."""
    seen: dict[str, dict] = {}
    for paper in all_papers:
        pid = paper.get("paper_id", "")
        if not pid:
            continue
        if pid in seen:
            seen[pid]["query_hit_count"] += 1
        else:
            paper["query_hit_count"] = 1
            paper["is_saved"] = pid in saved_ids
            seen[pid] = paper

    merged = list(seen.values())
    with_c = sorted([p for p in merged if p.get("citation_count", 0) > 0],
                    key=lambda x: x["citation_count"], reverse=True)
    without_c = [p for p in merged if p.get("citation_count", 0) == 0]
    return with_c + without_c


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ─── Step A: Must-contain filter ─────────────────────────────────────────────

def apply_must_contain_filter(papers: list, terms: list[str]) -> tuple[list, list]:
    """title + abstract에 must_contain_terms 중 하나라도 있으면 통과."""
    if not terms:
        return papers, []

    passing, rejected = [], []
    for paper in papers:
        haystack = (
            (paper.get("title") or "") + " " + (paper.get("abstract") or "")
        ).lower()
        if any(t in haystack for t in terms):
            passing.append(paper)
        else:
            rejected.append(paper)
    return passing, rejected


# ─── AI: Query generation + must_contain extraction ──────────────────────────

async def generate_queries_and_terms(keywords: str, db: Session) -> tuple[list[str], list[str], str]:
    """
    쿼리 6~8개 + must_contain_terms 3~6개를 동시에 생성.
    반환: (queries, must_contain_terms, expanded_terms_json)
    """
    client = AIClient(db)
    system = (
        "You are a scientific literature search expert specializing in chemistry and catalysis.\n\n"
        "CRITICAL — Abbreviation & shorthand expansion:\n"
        "Users often use abbreviations. You MUST first identify what each abbreviation means "
        "based on the chemistry context, then use FULL chemical names in your queries.\n"
        "Common examples (not exhaustive):\n"
        "- CPE → cyclopentene\n"
        "- CPN / CPONE → cyclopentanone\n"
        "- CPL → cyclopentanol\n"
        "- CHE → cyclohexene\n"
        "- CHN / CHONE → cyclohexanone\n"
        "- CHL → cyclohexanol\n"
        "- MeOH → methanol, EtOH → ethanol\n"
        "- PDH → propane dehydrogenation\n"
        "- SCR → selective catalytic reduction\n"
        "- WGS → water-gas shift\n"
        "- FT → Fischer-Tropsch\n"
        "- HDS → hydrodesulfurization\n"
        "- ORR → oxygen reduction reaction\n"
        "- OER → oxygen evolution reaction\n"
        "- HER → hydrogen evolution reaction\n"
        "If unsure, infer from context. Always use both the abbreviation AND full name in queries.\n\n"
        "The user may provide short keywords OR a natural language question. "
        "Analyze the research intent deeply and produce THREE things:\n"
        "1. 'expanded_terms': A brief string explaining what abbreviations/shorthand you identified "
        "(e.g., 'CPE = cyclopentene, CPN = cyclopentanone'). If none, use empty string.\n"
        "2. 'queries': 6-8 diverse English search query strings for Semantic Scholar. "
        "Use FULL chemical names (not abbreviations) in most queries. "
        "Cover: exact reaction, catalyst types, alternative synthesis routes, mechanism studies, "
        "industrial applications, and related review papers.\n"
        "3. 'must_contain_terms': 3-6 key terms that a truly relevant paper MUST mention. "
        "Include BOTH abbreviations AND full names as separate entries. Use lowercase.\n\n"
        "Return ONLY valid JSON — no markdown, no explanation:\n"
        '{"expanded_terms": "...", "queries": ["...", "..."], "must_contain_terms": ["...", "..."]}'
    )
    user = (
        f'User input: "{keywords}"\n\n'
        "First identify any abbreviations, then generate search queries using full chemical names."
    )

    try:
        result_text, _, _ = await client.complete(system=system, user=user)
        clean = re.sub(r"```[a-z]*\n?", "", result_text).strip()
        data = json.loads(clean)
        queries = [q.strip() for q in data.get("queries", []) if isinstance(q, str) and q.strip()][:8]
        terms = [t.strip().lower() for t in data.get("must_contain_terms", []) if isinstance(t, str) and t.strip()][:6]
        expanded = data.get("expanded_terms", "")
        if queries:
            return queries, terms, expanded
    except Exception:
        pass

    return [keywords], [], ""


# ─── Step B: AI batch relevance scoring ──────────────────────────────────────

async def ai_score_papers(
    papers: list, original_query: str, db: Session
) -> tuple[list, list]:
    """
    논문 배치를 AI에게 보내 관련도 0~10 점수 평가.
    반환: (high_relevance [score >= THRESHOLD], low_relevance)
    AI 실패 시 전체를 high_relevance로 반환 (graceful fallback).
    """
    if not papers:
        return [], []

    client = AIClient(db)

    papers_text = ""
    for i, p in enumerate(papers):
        abstract_preview = (p.get("abstract") or "")[:ABSTRACT_PREVIEW_CHARS]
        papers_text += f"[{i}] Title: {p.get('title', '(no title)')}\n"
        if abstract_preview:
            papers_text += f"    Abstract: {abstract_preview}\n"
        papers_text += "\n"

    system = (
        "You are a scientific literature relevance judge. "
        "Score each paper's relevance to the given research query on a scale of 0-10:\n"
        "9-10 = directly studies the exact compounds/reactions in the query\n"
        "7-8  = highly relevant, discusses the same specific chemistry\n"
        "5-6  = somewhat related, same broad field but different focus\n"
        "0-4  = not relevant (different compounds, unrelated field)\n\n"
        "Return ONLY a valid JSON array — no markdown, no explanation:\n"
        '[{"id": 0, "score": 8}, {"id": 1, "score": 3}, ...]'
    )
    user = (
        f'Research query: "{original_query}"\n\n'
        f"Papers to score:\n{papers_text}\n"
        "Return relevance scores for each paper."
    )

    try:
        result_text, _, _ = await client.complete(system=system, user=user)
        clean = re.sub(r"```[a-z]*\n?", "", result_text).strip()
        scores = json.loads(clean)
        score_map = {
            item["id"]: item["score"]
            for item in scores
            if isinstance(item, dict) and "id" in item and "score" in item
        }
        for i, paper in enumerate(papers):
            paper["relevance_score"] = score_map.get(i)

        high = [p for p in papers if (p.get("relevance_score") or 0) >= RELEVANCE_THRESHOLD]
        low = [p for p in papers if (p.get("relevance_score") or 0) < RELEVANCE_THRESHOLD]
        # high 내부도 relevance_score 내림차순 → 같은 점수면 인용수
        high.sort(key=lambda x: (x.get("relevance_score") or 0, x.get("citation_count") or 0), reverse=True)
        return high, low

    except Exception:
        # fallback: 스코어링 실패 시 전체 반환
        for p in papers:
            p["relevance_score"] = None
        return papers, []


# ─── Original simple search (kept) ───────────────────────────────────────────

@router.get("")
async def search_papers(
    q: str = Query(...),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    open_access_only: bool = False,
    sort: str = Query("relevance"),
    db: Session = Depends(get_db),
):
    s2 = get_s2_client(db)
    try:
        result = await s2.search(query=q, limit=limit, offset=offset,
                                 year_from=year_from, year_to=year_to,
                                 open_access_only=open_access_only)
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Semantic Scholar API 요청 한도 초과.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Semantic Scholar API 응답 시간 초과.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 오류: {str(e)}")

    papers_data = result.get("data") or []
    paper_ids = [p.get("paperId", "") for p in papers_data]
    saved_ids = {p.paper_id for p in db.query(Paper).filter(Paper.paper_id.in_(paper_ids)).all()}
    papers = [normalize_paper(p, saved_ids) for p in papers_data]
    if sort == "citations":
        papers = sorted(papers, key=lambda x: x.get("citation_count", 0), reverse=True)
    return {"data": papers, "total": result.get("total") or 0, "offset": offset, "limit": limit}


# ─── AI-mediated search — SSE stream (C = A + B) ─────────────────────────────

class AiSearchRequest(BaseModel):
    keywords: str
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    open_access_only: bool = False


@router.post("/ai-search/stream")
async def ai_search_stream(request: AiSearchRequest):
    keywords = request.keywords.strip()
    cache_key = keywords.lower()

    async def generate():
        db = SessionLocal()
        try:
            # ── 1. 캐시 확인 ─────────────────────────────────────────────────
            yield sse({"phase": "checking_cache", "message": "캐시 확인 중..."})
            cutoff = datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)
            cached = (
                db.query(SearchCache)
                .filter(SearchCache.keyword == cache_key, SearchCache.created_at >= cutoff)
                .first()
            )
            if cached:
                payload = json.loads(cached.results_json)
                # 구버전 캐시(리스트 포맷)는 캐시 미스로 처리
                if not isinstance(payload, dict):
                    cached = None

            if cached:
                payload = json.loads(cached.results_json)
                # 캐시 히트에도 검색 기록 저장
                db.add(SearchHistory(
                    keyword=keywords,
                    expanded_terms=None,
                    queries_json=cached.queries_json,
                    result_count=len(payload.get("results", [])),
                    total_collected=payload.get("filter_stats", {}).get("raw", 0),
                ))
                db.commit()
                yield sse({
                    "phase": "done",
                    "cache_hit": True,
                    "queries": json.loads(cached.queries_json),
                    "must_contain_terms": payload.get("must_contain_terms", []),
                    "results": payload.get("results", []),
                    "low_relevance_results": payload.get("low_relevance_results", []),
                    "filter_stats": payload.get("filter_stats", {}),
                    "total": len(payload.get("results", [])),
                })
                return

            # ── 2. AI 쿼리 + must_contain_terms 생성 ─────────────────────────
            yield sse({"phase": "generating", "message": "AI가 검색 전략 수립 중..."})
            queries, must_contain_terms, expanded_terms = await generate_queries_and_terms(keywords, db)
            estimated_sec = round(len(queries) * QUERY_DELAY_SECONDS + 8)
            yield sse({
                "phase": "queries_ready",
                "queries": queries,
                "must_contain_terms": must_contain_terms,
                "expanded_terms": expanded_terms,
                "estimated_seconds": estimated_sec,
            })

            # ── 3. S2 순차 검색 ───────────────────────────────────────────────
            s2 = get_s2_client(db)
            all_papers: list = []
            query_counts: list[int] = []

            for i, q in enumerate(queries):
                yield sse({"phase": "searching", "current": i + 1, "total": len(queries), "query": q})
                try:
                    result = await s2.search(
                        query=q,
                        limit=S2_RESULTS_PER_QUERY,
                        year_from=request.year_from,
                        year_to=request.year_to,
                        open_access_only=request.open_access_only,
                    )
                    batch = result.get("data") or []
                    all_papers.extend([normalize_paper(p) for p in batch])
                    count = len(batch)
                except RateLimitError:
                    count = 0
                    yield sse({"phase": "warning", "message": f"쿼리 {i+1} 요청 한도 초과, 건너뜀"})
                except Exception:
                    count = 0

                query_counts.append(count)
                yield sse({"phase": "query_done", "index": i, "result_count": count})
                if i < len(queries) - 1:
                    await asyncio.sleep(QUERY_DELAY_SECONDS)

            # ── 4. 중복 제거 + 인용수 정렬 ───────────────────────────────────
            yield sse({"phase": "processing", "message": "결과 통합 중..."})
            saved_ids = {p.paper_id for p in db.query(Paper).all()}
            merged = merge_results(all_papers, saved_ids)
            raw_count = len(merged)

            # ── 5. Step A: Must-contain 필터 ─────────────────────────────────
            yield sse({
                "phase": "filtering",
                "message": f"관련 논문 필터링 중... ({raw_count}건 → 핵심 키워드 포함 논문만)",
                "terms": must_contain_terms,
            })
            if must_contain_terms:
                passing, must_contain_rejected = apply_must_contain_filter(merged, must_contain_terms)
            else:
                passing, must_contain_rejected = merged, []

            after_filter_count = len(passing)
            yield sse({
                "phase": "filter_done",
                "before": raw_count,
                "after": after_filter_count,
                "rejected": len(must_contain_rejected),
            })

            # ── 6. Step B: AI 관련도 스코어링 ────────────────────────────────
            yield sse({
                "phase": "scoring",
                "message": f"AI 관련도 분석 중... ({after_filter_count}건)",
                "count": after_filter_count,
            })
            high_relevance, score_rejected = await ai_score_papers(passing, keywords, db)

            # must_contain으로 걸러진 것 + 점수 낮은 것 합쳐서 low_relevance
            low_relevance = score_rejected + must_contain_rejected

            filter_stats = {
                "raw": raw_count,
                "after_must_contain": after_filter_count,
                "after_scoring": len(high_relevance),
                "low_relevance": len(low_relevance),
            }

            queries_with_counts = [
                {"text": q, "result_count": c}
                for q, c in zip(queries, query_counts)
            ]

            # ── 7. 검색 기록 저장 ─────────────────────────────────────────────
            db.add(SearchHistory(
                keyword=keywords,
                expanded_terms=expanded_terms or None,
                queries_json=json.dumps(queries, ensure_ascii=False),
                result_count=len(high_relevance),
                total_collected=raw_count,
            ))
            db.commit()

            # ── 8. 캐시 저장 ──────────────────────────────────────────────────
            cache_payload = {
                "must_contain_terms": must_contain_terms,
                "results": high_relevance,
                "low_relevance_results": low_relevance,
                "filter_stats": filter_stats,
            }
            existing = db.query(SearchCache).filter(SearchCache.keyword == cache_key).first()
            if existing:
                existing.queries_json = json.dumps(queries_with_counts, ensure_ascii=False)
                existing.results_json = json.dumps(cache_payload, ensure_ascii=False)
                existing.created_at = datetime.utcnow()
            else:
                db.add(SearchCache(
                    keyword=cache_key,
                    queries_json=json.dumps(queries_with_counts, ensure_ascii=False),
                    results_json=json.dumps(cache_payload, ensure_ascii=False),
                ))
            db.commit()

            yield sse({
                "phase": "done",
                "cache_hit": False,
                "queries": queries_with_counts,
                "must_contain_terms": must_contain_terms,
                "expanded_terms": expanded_terms,
                "results": high_relevance,
                "low_relevance_results": low_relevance,
                "filter_stats": filter_stats,
                "total": len(high_relevance),
            })

        except Exception as e:
            yield sse({"phase": "error", "message": str(e)})
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── Search history ───────────────────────────────────────────────────────────

@router.get("/history")
async def get_search_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    records = (
        db.query(SearchHistory)
        .order_by(SearchHistory.searched_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "keyword": r.keyword,
            "expanded_terms": r.expanded_terms,
            "result_count": r.result_count,
            "total_collected": r.total_collected,
            "searched_at": r.searched_at.isoformat(),
        }
        for r in records
    ]


@router.delete("/history/{history_id}")
async def delete_search_history(history_id: int, db: Session = Depends(get_db)):
    record = db.query(SearchHistory).filter(SearchHistory.id == history_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="검색 기록을 찾을 수 없습니다.")
    db.delete(record)
    db.commit()
    return {"ok": True}


@router.delete("/history")
async def clear_search_history(db: Session = Depends(get_db)):
    db.query(SearchHistory).delete()
    db.commit()
    return {"ok": True}


# ─── Paper detail ─────────────────────────────────────────────────────────────

@router.get("/paper/{paper_id}")
async def get_paper_detail(paper_id: str, db: Session = Depends(get_db)):
    s2 = get_s2_client(db)
    try:
        paper_data = await s2.get_paper(paper_id)
        refs_data = await s2.get_references(paper_id, limit=50)
        citations_data = await s2.get_citations(paper_id, limit=50)
        recs_data = await s2.get_recommendations(paper_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Semantic Scholar API 요청 한도 초과.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Semantic Scholar API 응답 시간 초과.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"논문 조회 오류: {str(e)}")

    saved_paper = db.query(Paper).filter(Paper.paper_id == paper_id).first()
    normalized = normalize_paper(paper_data, {paper_id} if saved_paper else set())

    references = [
        normalize_ref_paper(item["citedPaper"])
        for item in (refs_data.get("data") or [])
        if item.get("citedPaper", {}).get("paperId")
    ]
    citations = [
        normalize_ref_paper(item["citingPaper"])
        for item in (citations_data.get("data") or [])
        if item.get("citingPaper", {}).get("paperId")
    ]
    recommendations = [
        normalize_ref_paper(rec)
        for rec in (recs_data.get("recommendedPapers") or [])
        if rec.get("paperId")
    ]

    normalized["references"] = references
    normalized["citations"] = citations
    normalized["recommendations"] = recommendations
    normalized["is_saved"] = saved_paper is not None
    return normalized
