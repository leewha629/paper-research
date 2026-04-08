import asyncio
import json
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import Paper, AppSetting, SearchCache, SearchHistory, FilterPreset
from s2_client import S2Client, RateLimitError, NotFoundError
from ai_client import AIClient, parse_json_response

router = APIRouter(prefix="/search", tags=["search"])

CACHE_TTL_HOURS = 24
QUERY_DELAY_SECONDS = 1.5
S2_RESULTS_PER_QUERY = 20
RELEVANCE_THRESHOLD = 6      # 이 점수 이상만 메인 결과로 표시
ABSTRACT_PREVIEW_CHARS = 400  # 스코어링 시 초록 앞부분만 사용

# 동의어/약어 사전 (synonym expansion)
SYNONYM_MAP = {
    "scr": ["selective catalytic reduction", "DeNOx", "NOx reduction"],
    "pdh": ["propane dehydrogenation"],
    "wgs": ["water-gas shift", "water gas shift reaction"],
    "ft": ["Fischer-Tropsch", "Fischer Tropsch synthesis"],
    "hds": ["hydrodesulfurization"],
    "orr": ["oxygen reduction reaction"],
    "oer": ["oxygen evolution reaction"],
    "her": ["hydrogen evolution reaction"],
    "cpe": ["cyclopentene"],
    "cpn": ["cyclopentanone"],
    "cpone": ["cyclopentanone"],
    "cpl": ["cyclopentanol"],
    "che": ["cyclohexene"],
    "chn": ["cyclohexanone"],
    "chone": ["cyclohexanone"],
    "chl": ["cyclohexanol"],
    "meoh": ["methanol"],
    "etoh": ["ethanol"],
    "mof": ["metal-organic framework", "metal organic framework"],
    "cof": ["covalent organic framework"],
    "pem": ["proton exchange membrane", "polymer electrolyte membrane"],
    "sofc": ["solid oxide fuel cell"],
    "aemwe": ["anion exchange membrane water electrolysis"],
}


# ─── Korean detection helper ────────────────────────────────────────────────

def contains_korean(text: str) -> bool:
    """텍스트에 한글이 포함되어 있는지 확인"""
    for ch in text:
        if '\uAC00' <= ch <= '\uD7A3' or '\u3131' <= ch <= '\u3163':
            return True
    return False


async def translate_korean_to_english(text: str, db: Session) -> tuple[str, str]:
    """
    한국어 입력을 영어 학술 검색 쿼리로 번역.
    반환: (영문 번역, 원문 한국어)

    Phase C: 폴백 제거. AI 실패 시 LLMError가 그대로 호출자에게 전파된다 →
    GET /search 핸들러는 글로벌 LLMError 핸들러를 통해 503으로 응답.
    SSE 스트림 호출자는 LLMError를 잡아 명시적인 error 이벤트를 emit한다.
    """
    from services.llm.router import call_llm

    system = (
        "You are an academic translator specializing in scientific terminology.\n"
        "Translate the Korean academic query to English.\n"
        "Keep chemical formulas, abbreviations, and technical terms accurate.\n"
        "Return ONLY the English translation, nothing else."
    )
    user = f"Translate to English academic query:\n{text}"

    result_text, _, _ = await call_llm(db, system=system, user=user, expect="text")
    return result_text.strip(), text


# ─── Boolean keyword parser ─────────────────────────────────────────────────

def parse_boolean_keywords(query: str) -> dict:
    """
    AND/OR/NOT 불린 로직 파싱.
    예: "CeO2 AND SCR NOT WGS" -> {and_terms: ["CeO2", "SCR"], or_terms: [], not_terms: ["WGS"]}
    기본은 AND 처리.
    """
    query = query.strip()
    and_terms = []
    or_terms = []
    not_terms = []

    # NOT 처리
    not_pattern = r'\bNOT\s+(\S+)'
    not_matches = re.findall(not_pattern, query, re.IGNORECASE)
    not_terms.extend(not_matches)
    query = re.sub(not_pattern, '', query, flags=re.IGNORECASE).strip()

    # OR 처리: "A OR B"
    parts = re.split(r'\s+OR\s+', query, flags=re.IGNORECASE)
    if len(parts) > 1:
        for part in parts:
            sub_terms = re.split(r'\s+AND\s+', part.strip(), flags=re.IGNORECASE)
            if len(sub_terms) > 1:
                and_terms.extend([t.strip() for t in sub_terms if t.strip()])
            else:
                or_terms.append(part.strip())
    else:
        # AND 처리 (기본)
        sub_terms = re.split(r'\s+AND\s+', query, flags=re.IGNORECASE)
        and_terms.extend([t.strip() for t in sub_terms if t.strip()])

    return {
        "and_terms": [t for t in and_terms if t],
        "or_terms": [t for t in or_terms if t],
        "not_terms": [t.lower() for t in not_terms if t],
    }


def apply_boolean_filter(papers: list, boolean_parsed: dict) -> list:
    """불린 키워드 기반 필터링"""
    not_terms = boolean_parsed.get("not_terms", [])
    if not not_terms:
        return papers

    filtered = []
    for paper in papers:
        haystack = (
            (paper.get("title") or "") + " " + (paper.get("abstract") or "")
        ).lower()
        if not any(t in haystack for t in not_terms):
            filtered.append(paper)
    return filtered


# ─── Synonym expansion ──────────────────────────────────────────────────────

def expand_synonyms(query: str) -> tuple[list[str], dict]:
    """
    쿼리에서 알려진 약어를 찾아 동의어 확장.
    반환: (확장된 추가 쿼리 목록, {약어: [동의어들]} 매핑)
    """
    words = re.findall(r'[A-Za-z0-9]+', query.lower())
    expanded_queries = []
    synonym_matches = {}

    for word in words:
        if word in SYNONYM_MAP:
            synonyms = SYNONYM_MAP[word]
            synonym_matches[word.upper()] = synonyms
            for syn in synonyms[:2]:  # 각 약어당 최대 2개 동의어 쿼리
                new_q = query.lower().replace(word, syn, 1)
                expanded_queries.append(new_q)

    return expanded_queries, synonym_matches


# ─── Normalize helpers ──────────────────────────────────────────────────────

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
        "relevance_reason": None,
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


def sort_papers(papers: list, sort_by: str) -> list:
    """정렬 옵션 적용"""
    if sort_by == "citations":
        return sorted(papers, key=lambda x: x.get("citation_count", 0), reverse=True)
    elif sort_by == "newest":
        return sorted(papers, key=lambda x: x.get("year") or 0, reverse=True)
    elif sort_by == "oldest":
        return sorted(papers, key=lambda x: x.get("year") or 9999)
    elif sort_by == "relevance":
        # AI 관련도 점수 기반 (기본)
        return sorted(
            papers,
            key=lambda x: (x.get("relevance_score") or 0, x.get("citation_count") or 0),
            reverse=True,
        )
    return papers


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


# ─── Advanced filters ───────────────────────────────────────────────────────

def apply_advanced_filters(papers: list, venues: list[str] = None,
                           author_filter: str = None) -> list:
    """저널/venue, 저자 필터 적용"""
    result = papers

    if venues:
        venues_lower = [v.lower() for v in venues]
        result = [
            p for p in result
            if p.get("venue") and any(v in (p["venue"]).lower() for v in venues_lower)
        ]

    if author_filter:
        author_lower = author_filter.lower()
        filtered = []
        for p in result:
            authors = p.get("authors") or []
            if any(author_lower in (a.get("name") or "").lower() for a in authors):
                filtered.append(p)
        result = filtered

    return result


# ─── AI: Query generation + must_contain extraction ─────────────────────────

async def generate_queries_and_terms(
    keywords: str, db: Session, num_queries: int = 6
) -> tuple[list[str], list[str], str]:
    """
    다각도 쿼리 3~8개 + must_contain_terms 3~6개를 동시에 생성.
    반환: (queries, must_contain_terms, expanded_terms_json)
    """
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
        "MULTI-ANGLE STRATEGY:\n"
        "Generate queries from DIFFERENT angles to maximize coverage:\n"
        "- Exact reaction/compound queries\n"
        "- Catalyst/material-focused queries\n"
        "- Mechanism/kinetics queries\n"
        "- Review/survey queries\n"
        "- Application/industrial queries\n\n"
        "The user may provide short keywords OR a natural language question. "
        "Analyze the research intent deeply and produce THREE things:\n"
        "1. 'expanded_terms': A brief string explaining what abbreviations/shorthand you identified "
        "(e.g., 'CPE = cyclopentene, CPN = cyclopentanone'). If none, use empty string.\n"
        f"2. 'queries': {num_queries}-{num_queries + 2} diverse English search query strings for Semantic Scholar. "
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

    # Phase C: 폴백 제거. LLMError를 그대로 raise → 호출자 (SSE 스트림 또는 GET 엔드포인트)가
    # PLAN §C.1에 따라 분기:
    #   - SSE: warning 이벤트 emit + [keywords] 단일 쿼리로 진행
    #   - GET: 글로벌 핸들러 → 503
    from services.llm import ExpandedQuery
    from services.llm.router import call_llm

    eq, _, _ = await call_llm(
        db,
        system=system,
        user=user,
        expect="schema",
        schema=ExpandedQuery,
    )
    queries = eq.queries[:8]
    terms = eq.must_contain_terms[:6]
    expanded = eq.expanded_terms or ""
    if not queries:
        # schema가 min_length=1이지만 만약을 대비
        from services.llm.exceptions import LLMSchemaError

        raise LLMSchemaError("ExpandedQuery.queries 비어있음")
    return queries, terms, expanded


# ─── Step B: AI batch relevance scoring with reasons ─────────────────────────

async def ai_score_papers(
    papers: list, original_query: str, db: Session
) -> tuple[list, list]:
    """
    논문 배치를 AI에게 보내 관련도 0~10 점수 + 이유 평가.
    반환: (high_relevance [score >= THRESHOLD], low_relevance)

    Phase C: 폴백 제거. AI 실패 시 LLMError가 그대로 전파된다 →
    SSE/엔드포인트가 503 에러로 변환. **임의로 high 버킷에 넣지 않는다.**
    """
    if not papers:
        return [], []

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
        "For each paper, also provide a brief one-line reason for the score.\n\n"
        "Return ONLY a valid JSON array — no markdown, no explanation:\n"
        '[{"id": 0, "score": 8, "reason": "Directly studies CeO2-based SCR catalysts with NH3"}, '
        '{"id": 1, "score": 3, "reason": "Discusses unrelated photocatalysis"}, ...]'
    )
    user = (
        f'Research query: "{original_query}"\n\n'
        f"Papers to score:\n{papers_text}\n"
        "Return relevance scores with reasons for each paper."
    )

    # Phase C: 폴백 제거. call_llm이 raise하면 그대로 전파.
    # NOTE: PLAN은 expect="schema", schema=list[ScoredPaper]를 명시했지만, 기존 prompt가
    # 루트 배열을 요구하고 Ollama format은 객체 루트만 받는다. expect="json"으로 받고
    # 호출부에서 명시적으로 ScoredPaper 검증 (deviation #4 후처리).
    from services.llm import ScoredPaper
    from services.llm.router import call_llm
    from services.llm.exceptions import LLMSchemaError
    from pydantic import ValidationError

    scores, _, _ = await call_llm(
        db,
        system=system,
        user=user,
        expect="json",
    )
    # 응답이 dict인 경우 "scores" 키 우선 시도 (Ollama format=json은 dict 루트를 강제)
    if isinstance(scores, dict):
        scores = scores.get("scores", scores.get("results", []))
    if not isinstance(scores, list):
        raise LLMSchemaError(
            f"ai_score_papers: 응답이 list 또는 {{scores:[...]}}가 아님 (type={type(scores).__name__})"
        )

    score_map: dict[int, float] = {}
    reason_map: dict[int, str] = {}
    for raw in scores:
        if not isinstance(raw, dict):
            continue
        try:
            sp = ScoredPaper.model_validate(raw)
        except ValidationError:
            # 개별 항목이 schema에 맞지 않으면 무시 (전체 실패는 아님)
            continue
        score_map[sp.id] = sp.score
        reason_map[sp.id] = sp.reason

    if not score_map:
        # 모든 항목이 검증 실패 → 전체 실패로 간주
        raise LLMSchemaError(
            "ai_score_papers: ScoredPaper 검증을 통과한 항목이 없음"
        )

    for i, paper in enumerate(papers):
        paper["relevance_score"] = score_map.get(i)
        paper["relevance_reason"] = reason_map.get(i, "")

    high = [p for p in papers if (p.get("relevance_score") or 0) >= RELEVANCE_THRESHOLD]
    low = [p for p in papers if (p.get("relevance_score") or 0) < RELEVANCE_THRESHOLD]
    # high 내부도 relevance_score 내림차순 → 같은 점수면 인용수
    high.sort(key=lambda x: (x.get("relevance_score") or 0, x.get("citation_count") or 0), reverse=True)
    return high, low


# ─── Original simple search (with pagination & advanced filters) ─────────────

@router.get("")
async def search_papers(
    q: str = Query(...),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    open_access_only: bool = False,
    sort: str = Query("relevance"),
    venues: Optional[str] = Query(None, description="쉼표로 구분된 저널/venue 목록"),
    fields_of_study: Optional[str] = Query(None, description="쉼표로 구분된 분야"),
    author: Optional[str] = Query(None, description="저자 이름 필터"),
    db: Session = Depends(get_db),
):
    s2 = get_s2_client(db)

    # 한국어 자동 번역
    search_query = q
    korean_original = None
    if contains_korean(q):
        search_query, korean_original = await translate_korean_to_english(q, db)

    # S2 API 필드 파싱
    fos_list = [f.strip() for f in fields_of_study.split(",")] if fields_of_study else None
    venue_list = [v.strip() for v in venues.split(",")] if venues else None

    try:
        result = await s2.search(
            query=search_query, limit=limit, offset=offset,
            year_from=year_from, year_to=year_to,
            open_access_only=open_access_only,
            fields_of_study=fos_list,
            venue=venue_list,
        )
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Semantic Scholar API 요청 한도 초과.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Semantic Scholar API 응답 시간 초과.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 오류: {str(e)}")

    papers_data = result.get("data") or []
    paper_ids = [p.get("paperId", "") for p in papers_data]
    saved_ids = {p.paper_id for p in db.query(Paper).filter(Paper.paper_id.in_(paper_ids)).all()} if paper_ids else set()
    papers = [normalize_paper(p, saved_ids) for p in papers_data]

    # 저자 필터 (S2 API에서 지원하지 않으므로 후처리)
    if author:
        papers = apply_advanced_filters(papers, author_filter=author)

    papers = sort_papers(papers, sort)

    total = result.get("total") or 0
    next_offset = offset + limit if (offset + limit) < total else None

    return {
        "data": papers,
        "total": total,
        "offset": offset,
        "limit": limit,
        "next_offset": next_offset,
        "translated_query": search_query if korean_original else None,
        "korean_original": korean_original,
    }


# ─── AI-mediated search — SSE stream (C = A + B) ───────────────────────────

class AiSearchRequest(BaseModel):
    keywords: str
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    open_access_only: bool = False
    sort_by: str = "relevance"  # relevance, citations, newest, oldest
    venues: Optional[List[str]] = None
    fields_of_study: Optional[List[str]] = None
    author: Optional[str] = None
    offset: int = 0
    limit: int = 50
    # 사용자가 수정한 쿼리로 재검색할 때 사용
    custom_queries: Optional[List[str]] = None


@router.post("/ai-search/stream")
async def ai_search_stream(request: AiSearchRequest):
    keywords = request.keywords.strip()
    cache_key = keywords.lower()

    async def generate():
        db = SessionLocal()
        try:
            # ── 0. 한국어 감지 및 번역 ───────────────────────────────────────
            search_keywords = keywords
            korean_original = None
            if contains_korean(keywords):
                yield sse({"phase": "translating", "message": "한국어 쿼리를 영어로 번역 중..."})
                search_keywords, korean_original = await translate_korean_to_english(keywords, db)
                yield sse({
                    "phase": "translated",
                    "original": korean_original,
                    "translated": search_keywords,
                })

            # ── 1. 캐시 확인 (custom_queries가 없을 때만) ──────────────────
            use_cache = request.custom_queries is None
            if use_cache:
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
                    results = payload.get("results", [])
                    low_results = payload.get("low_relevance_results", [])

                    # 후처리 필터 적용
                    if request.venues:
                        results = apply_advanced_filters(results, venues=request.venues)
                        low_results = apply_advanced_filters(low_results, venues=request.venues)
                    if request.author:
                        results = apply_advanced_filters(results, author_filter=request.author)
                        low_results = apply_advanced_filters(low_results, author_filter=request.author)

                    # 정렬
                    results = sort_papers(results, request.sort_by)

                    # 페이지네이션
                    total_results = len(results)
                    paged_results = results[request.offset:request.offset + request.limit]
                    next_offset = request.offset + request.limit if (request.offset + request.limit) < total_results else None

                    # 검색 기록 저장
                    db.add(SearchHistory(
                        keyword=keywords,
                        expanded_terms=None,
                        queries_json=cached.queries_json,
                        result_count=len(paged_results),
                        total_collected=payload.get("filter_stats", {}).get("raw", 0),
                    ))
                    db.commit()
                    yield sse({
                        "phase": "done",
                        "cache_hit": True,
                        "queries": json.loads(cached.queries_json),
                        "must_contain_terms": payload.get("must_contain_terms", []),
                        "results": paged_results,
                        "low_relevance_results": low_results[:20],
                        "filter_stats": payload.get("filter_stats", {}),
                        "total": total_results,
                        "offset": request.offset,
                        "next_offset": next_offset,
                        "synonym_expansions": payload.get("synonym_expansions", {}),
                        "translated_query": search_keywords if korean_original else None,
                        "korean_original": korean_original,
                    })
                    return

            # ── 2. 동의어 확장 ──────────────────────────────────────────────
            synonym_queries, synonym_matches = expand_synonyms(search_keywords)
            if synonym_matches:
                yield sse({
                    "phase": "synonyms",
                    "message": "동의어 확장 적용 중...",
                    "synonyms": synonym_matches,
                })

            # ── 3. AI 쿼리 + must_contain_terms 생성 (또는 사용자 커스텀 쿼리) ──
            if request.custom_queries:
                queries = request.custom_queries
                must_contain_terms = []
                expanded_terms = ""
                yield sse({
                    "phase": "queries_ready",
                    "queries": queries,
                    "must_contain_terms": [],
                    "expanded_terms": "",
                    "estimated_seconds": round(len(queries) * QUERY_DELAY_SECONDS + 8),
                    "editable": True,
                })
            else:
                yield sse({"phase": "generating", "message": "AI가 다각도 검색 전략 수립 중..."})
                # Phase C: 쿼리 확장 실패는 warning으로 강등 — 단일 키워드로 진행하되
                # 사용자가 노란 배너로 인지할 수 있도록 명시적 warning 이벤트를 emit한다.
                # (PLAN §C.1: 200 + warning yellow banner)
                from services.llm.exceptions import LLMError as _LLMErrorExp

                expand_warning_code: Optional[str] = None
                try:
                    queries, must_contain_terms, expanded_terms = await generate_queries_and_terms(
                        search_keywords, db, num_queries=5
                    )
                except _LLMErrorExp as exp_err:
                    expand_warning_code = "ai_expand_failed"
                    queries = [search_keywords]
                    must_contain_terms = []
                    expanded_terms = ""
                    yield sse({
                        "phase": "warning",
                        "warning": expand_warning_code,
                        "message": (
                            "AI 쿼리 확장 실패. 단일 키워드로만 검색됩니다. "
                            f"({type(exp_err).__name__}: {exp_err})"
                        ),
                    })

                # 동의어 확장 쿼리 추가 (중복 제거)
                existing_lower = {q.lower() for q in queries}
                for sq in synonym_queries:
                    if sq.lower() not in existing_lower:
                        queries.append(sq)
                        existing_lower.add(sq.lower())

                estimated_sec = round(len(queries) * QUERY_DELAY_SECONDS + 8)
                yield sse({
                    "phase": "queries_ready",
                    "queries": queries,
                    "must_contain_terms": must_contain_terms,
                    "expanded_terms": expanded_terms,
                    "estimated_seconds": estimated_sec,
                    "editable": True,  # 프론트엔드에서 수정 가능 표시
                })

            # ── 4. S2 순차 검색 ─────────────────────────────────────────────
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
                        fields_of_study=request.fields_of_study,
                        venue=request.venues,
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

            # ── 5. 중복 제거 + 병합 ─────────────────────────────────────────
            yield sse({"phase": "processing", "message": "결과 통합 중..."})
            saved_ids = {p.paper_id for p in db.query(Paper).all()}
            merged = merge_results(all_papers, saved_ids)
            raw_count = len(merged)

            # ── 5.5. 불린 NOT 필터 ──────────────────────────────────────────
            boolean_parsed = parse_boolean_keywords(search_keywords)
            if boolean_parsed.get("not_terms"):
                merged = apply_boolean_filter(merged, boolean_parsed)
                yield sse({
                    "phase": "boolean_filter",
                    "excluded_terms": boolean_parsed["not_terms"],
                    "before": raw_count,
                    "after": len(merged),
                })

            # ── 5.6. 고급 필터 (venue, author) ──────────────────────────────
            if request.venues or request.author:
                before = len(merged)
                merged = apply_advanced_filters(
                    merged, venues=request.venues, author_filter=request.author
                )
                yield sse({
                    "phase": "advanced_filter",
                    "before": before,
                    "after": len(merged),
                })

            # ── 6. Step A: Must-contain 필터 ─────────────────────────────────
            yield sse({
                "phase": "filtering",
                "message": f"관련 논문 필터링 중... ({len(merged)}건 → 핵심 키워드 포함 논문만)",
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

            # ── 7. Step B: AI 관련도 스코어링 (with reasons) ────────────────
            yield sse({
                "phase": "scoring",
                "message": f"AI 관련도 분석 중... ({after_filter_count}건)",
                "count": after_filter_count,
            })
            high_relevance, score_rejected = await ai_score_papers(passing, search_keywords, db)

            # must_contain으로 걸러진 것 + 점수 낮은 것 합쳐서 low_relevance
            low_relevance = score_rejected + must_contain_rejected

            # ── 7.5. 정렬 적용 ──────────────────────────────────────────────
            high_relevance = sort_papers(high_relevance, request.sort_by)

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

            # ── 7.6. 페이지네이션 ──────────────────────────────────────────
            total_results = len(high_relevance)
            paged_results = high_relevance[request.offset:request.offset + request.limit]
            next_offset = request.offset + request.limit if (request.offset + request.limit) < total_results else None

            # ── 8. 검색 기록 저장 ─────────────────────────────────────────────
            db.add(SearchHistory(
                keyword=keywords,
                expanded_terms=expanded_terms or None,
                queries_json=json.dumps(queries, ensure_ascii=False),
                result_count=len(high_relevance),
                total_collected=raw_count,
            ))
            db.commit()

            # ── 9. 캐시 저장 ──────────────────────────────────────────────────
            cache_payload = {
                "must_contain_terms": must_contain_terms,
                "results": high_relevance,
                "low_relevance_results": low_relevance,
                "filter_stats": filter_stats,
                "synonym_expansions": synonym_matches,
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
                "results": paged_results,
                "low_relevance_results": low_relevance[:20],
                "filter_stats": filter_stats,
                "total": total_results,
                "offset": request.offset,
                "next_offset": next_offset,
                "synonym_expansions": synonym_matches,
                "translated_query": search_keywords if korean_original else None,
                "korean_original": korean_original,
            })

        except Exception as e:
            # Phase C: LLMError는 fail-loud로 사용자 가시 코드를 함께 전달.
            from services.llm.exceptions import (
                LLMError as _LLMError,
                LLMTimeoutError as _LLMTimeout,
                LLMSchemaError as _LLMSchema,
                LLMUpstreamError as _LLMUpstream,
            )

            if isinstance(e, _LLMError):
                if isinstance(e, _LLMTimeout):
                    code = "ai_timeout"
                elif isinstance(e, _LLMSchema):
                    code = "ai_schema_invalid"
                elif isinstance(e, _LLMUpstream):
                    code = "ai_upstream_unavailable"
                else:
                    code = "ai_unavailable"
                yield sse({
                    "phase": "error",
                    "error": code,
                    "status": 503,
                    "message": str(e),
                })
            else:
                yield sse({"phase": "error", "message": str(e)})
        finally:
            db.close()

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── Search history ─────────────────────────────────────────────────────────

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


# ─── Similar paper search (S2 recommendations) ─────────────────────────────

@router.get("/similar/{paper_id}")
async def get_similar_papers(
    paper_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """특정 논문과 유사한 논문 추천 (S2 Recommendations API)"""
    s2 = get_s2_client(db)
    try:
        recs_data = await s2.get_recommendations(paper_id, limit=limit)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")
    except RateLimitError:
        raise HTTPException(status_code=429, detail="API 요청 한도 초과.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"유사 논문 검색 오류: {str(e)}")

    saved_ids = {p.paper_id for p in db.query(Paper).all()}
    recommendations = []
    for rec in (recs_data.get("recommendedPapers") or []):
        if rec.get("paperId"):
            paper = normalize_ref_paper(rec)
            paper["is_saved"] = paper["paper_id"] in saved_ids
            recommendations.append(paper)

    return {
        "paper_id": paper_id,
        "recommendations": recommendations,
        "total": len(recommendations),
    }


# ─── Author search ──────────────────────────────────────────────────────────

@router.get("/author")
async def search_by_author(
    name: str = Query(..., description="저자 이름"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """저자 이름으로 논문 검색"""
    s2 = get_s2_client(db)
    try:
        result = await s2.search_by_author(name, limit=limit)
    except RateLimitError:
        raise HTTPException(status_code=429, detail="API 요청 한도 초과.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저자 검색 오류: {str(e)}")

    authors_data = result.get("data") or []
    return {
        "data": authors_data,
        "total": result.get("total") or 0,
    }


# ─── Filter presets ─────────────────────────────────────────────────────────

class FilterPresetCreate(BaseModel):
    name: str
    filters: dict  # {venues, fields_of_study, year_from, year_to, open_access_only, author, ...}


@router.get("/filter-presets")
async def get_filter_presets(db: Session = Depends(get_db)):
    """저장된 필터 프리셋 목록 조회"""
    presets = db.query(FilterPreset).order_by(FilterPreset.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "filters": json.loads(p.filters_json),
            "created_at": p.created_at.isoformat(),
        }
        for p in presets
    ]


@router.post("/filter-presets")
async def create_filter_preset(preset: FilterPresetCreate, db: Session = Depends(get_db)):
    """필터 프리셋 저장"""
    # 이름 중복 확인
    existing = db.query(FilterPreset).filter(FilterPreset.name == preset.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="같은 이름의 프리셋이 이미 존재합니다.")

    new_preset = FilterPreset(
        name=preset.name,
        filters_json=json.dumps(preset.filters, ensure_ascii=False),
    )
    db.add(new_preset)
    db.commit()
    db.refresh(new_preset)
    return {
        "id": new_preset.id,
        "name": new_preset.name,
        "filters": preset.filters,
        "created_at": new_preset.created_at.isoformat(),
    }


@router.delete("/filter-presets/{preset_id}")
async def delete_filter_preset(preset_id: int, db: Session = Depends(get_db)):
    """필터 프리셋 삭제"""
    preset = db.query(FilterPreset).filter(FilterPreset.id == preset_id).first()
    if not preset:
        raise HTTPException(status_code=404, detail="프리셋을 찾을 수 없습니다.")
    db.delete(preset)
    db.commit()
    return {"ok": True}


# ─── Paper detail ───────────────────────────────────────────────────────────

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
