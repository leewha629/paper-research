import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List

from database import get_db
from models import Paper, AIAnalysisResult, BatchJob, PromptTemplate
from ai_client import AIClient, parse_json_response

router = APIRouter(prefix="/ai", tags=["ai"])

# ---------------------------------------------------------------------------
# 촉매 전문 기본 컨텍스트 (모든 분석 프롬프트 앞에 삽입)
# ---------------------------------------------------------------------------
BASE_CONTEXT = (
    "당신은 환경 촉매 연구 전문 논문 분석 AI입니다.\n"
    "전문 분야: SCR, CO/VOC 산화, CO₂ 환원, WGS 등\n"
    "합성법: 공침법, 습식함침법, sol-gel, 수열합성\n"
    "분석법: XRD, BET, TPR/TPD, XPS, TEM/SEM, FTIR, ICP\n"
    "성능지표: 전환율, 선택도, TOF, T50, GHSV, 안정성\n"
    "응답은 JSON. 추측 금지, 논문 명시 정보만 추출. 불확실하면 null.\n\n"
)

# ---------------------------------------------------------------------------
# 분석 유형 목록
# ---------------------------------------------------------------------------
ANALYSIS_TYPES = [
    "synthesis_conditions",
    "experiment_summary",
    "summary",
    "significance",
    "keywords",
    "structured",
    "trend",
    "review_draft",
]

# ---------------------------------------------------------------------------
# 기본 시스템 프롬프트 (DB에 없으면 사용)
# ---------------------------------------------------------------------------
SYSTEM_PROMPTS = {
    "synthesis_conditions": (
        "당신은 촉매 및 재료 과학 전문가입니다. "
        "논문 전체를 분석하여 촉매/재료의 합성 조건을 빠짐없이 추출하세요.\n\n"
        "**반드시 아래 항목들을 마크다운 표로 정리하세요:**\n"
        "| 항목 | 내용 |\n|---|---|\n"
        "| 촉매/재료명 | (조성, 화학식 포함) |\n"
        "| 합성 방법 | (공침법, 함침법, 졸-겔, 수열합성 등) |\n"
        "| 전구체 | (각 전구체의 정확한 화학명과 양) |\n"
        "| 용매/용액 | (사용된 용매, 농도) |\n"
        "| pH 조건 | (조절 범위, 사용된 산/염기) |\n"
        "| 숙성/건조 | (온도, 시간, 분위기) |\n"
        "| 소성 프로파일 | (승온 속도, 최종 온도, 유지 시간, 분위기) |\n"
        "| 후처리 | (환원, 활성화 등 추가 처리) |\n\n"
        "논문에 여러 샘플이 있으면 각각 별도 표로 작성하세요. "
        "정보가 없는 항목은 '정보 없음'으로 표시하세요. "
        "수치 데이터는 단위를 반드시 포함하세요. 한국어로 작성하세요."
    ),
    "experiment_summary": (
        "당신은 화학공학 및 촉매 반응 전문가입니다. "
        "논문의 실험 조건과 성능 데이터를 체계적으로 추출하세요.\n\n"
        "**1. 반응 조건 (마크다운 표):**\n"
        "| 항목 | 내용 |\n|---|---|\n"
        "| 반응 유형 | (어떤 반응인지) |\n"
        "| 반응기 종류 | (고정층, 유동층, 배치 등) |\n"
        "| 반응 온도 | (범위 또는 최적값, °C) |\n"
        "| 반응 압력 | (atm, bar 등) |\n"
        "| 공간속도 | (GHSV, WHSV 값과 단위) |\n"
        "| 공급 조성 | (반응물 비율, 캐리어 가스) |\n"
        "| 촉매량 | (질량, 입자 크기) |\n"
        "| 반응 시간 | (안정성 테스트 시간 포함) |\n\n"
        "**2. 성능 지표 (마크다운 표):**\n"
        "| 촉매 | 전환율(%) | 선택도(%) | 수율(%) | TOF | 안정성 |\n"
        "|---|---|---|---|---|---|\n\n"
        "논문에 나온 모든 촉매의 비교 데이터를 포함하세요. "
        "최적 조건과 최고 성능을 별도로 강조하세요. "
        "수치 데이터는 단위를 반드시 포함하세요. 한국어로 작성하세요."
    ),
    "summary": (
        "당신은 학술 논문 분석 전문가입니다. "
        "논문의 핵심 내용을 한국어로 요약하세요.\n\n"
        "**아래 구조로 작성하세요:**\n"
        "1. **연구 목적**: 이 연구가 해결하려는 문제와 동기 (1-2문장)\n"
        "2. **핵심 방법**: 사용된 주요 방법론과 접근법 (1-2문장)\n"
        "3. **주요 결과**: 가장 중요한 실험 결과와 수치 (2-3문장)\n"
        "4. **결론**: 연구의 핵심 결론 (1문장)\n\n"
        "구체적인 수치(전환율, 선택도, 수율 등)를 반드시 포함하세요. "
        "전문 용어는 유지하되 맥락을 통해 이해할 수 있도록 작성하세요."
    ),
    "significance": (
        "당신은 과학 연구 평가 전문가입니다. "
        "이 논문의 학술적 가치를 다음 관점에서 한국어로 분석하세요.\n\n"
        "**1. 학술적 기여:**\n"
        "- 이 분야에서 어떤 새로운 발견/관점을 제시하는가?\n"
        "- 기존 연구 대비 어떤 개선을 달성했는가? (구체적 수치 비교)\n\n"
        "**2. 방법론 평가:**\n"
        "- 실험 설계의 강점과 약점\n"
        "- 재현성, 통계적 유의성, 대조 실험의 적절성\n\n"
        "**3. 한계점:**\n"
        "- 논문에서 다루지 못한 조건이나 변수\n"
        "- 실용화를 위해 해결해야 할 과제\n\n"
        "**4. 향후 연구 방향:**\n"
        "- 이 연구를 기반으로 가능한 후속 연구 제안\n\n"
        "비판적이되 건설적으로 분석하세요."
    ),
    "keywords": (
        "당신은 학술 논문 분류 전문가입니다. "
        "논문의 핵심 주제를 나타내는 키워드를 추출하세요.\n\n"
        "**규칙:**\n"
        "- 8-12개의 키워드를 추출\n"
        "- 영어 기술 용어는 영어로, 일반 분야명은 한국어로 작성\n"
        "- 구체적인 것부터 일반적인 것 순서로 나열\n"
        "  (예: 촉매 물질명 → 반응명 → 합성법 → 분석법 → 연구 분야)\n"
        "- 쉼표로 구분: keyword1, 키워드2, keyword3, ...\n\n"
        "논문에 명시된 키워드가 있다면 우선 포함하고, "
        "추가로 논문 내용에서 도출된 키워드를 보충하세요."
    ),
    "structured": (
        "논문을 분석하여 아래 JSON 형식으로 구조화된 정보를 추출하세요.\n"
        "반드시 아래 키를 가진 JSON 객체 하나만 반환하세요. 마크다운이나 설명 텍스트는 포함하지 마세요.\n\n"
        "{\n"
        '  "purpose": "연구 목적 (1-2문장, 한국어)",\n'
        '  "catalysts": ["촉매1 (화학식)", "촉매2"],\n'
        '  "synthesis_methods": ["합성법1", "합성법2"],\n'
        '  "characterization_techniques": ["XRD", "BET", ...],\n'
        '  "key_results": ["핵심 결과1", "핵심 결과2", ...],\n'
        '  "relevance_to_environmental_catalysis": "환경 촉매 분야와의 관련성 (1-2문장)"\n'
        "}\n\n"
        "불확실한 항목은 null로, 빈 목록은 []로 표시하세요."
    ),
    "trend": (
        "주어진 여러 논문의 분석 결과를 종합하여 연구 동향을 파악하세요.\n\n"
        "아래 섹션으로 구성된 마크다운을 작성하세요:\n"
        "## 1. 주요 촉매 계열\n"
        "## 2. 합성 방법 동향\n"
        "## 3. 분석 기법 활용 현황\n"
        "## 4. 성능 지표 비교\n"
        "## 5. 연도별 연구 동향\n"
        "## 6. 종합 정리 및 시사점\n\n"
        "구체적 수치와 논문 제목을 인용하며 한국어로 작성하세요."
    ),
    "review_draft": (
        "주어진 논문들을 종합하여 문헌 리뷰 초안을 작성하세요.\n\n"
        "아래 구조의 학술 리뷰 형식 마크다운을 작성하세요:\n"
        "## 1. Introduction\n"
        "- 연구 배경 및 필요성\n"
        "## 2. Catalyst Types\n"
        "- 사용된 촉매 유형 분류 및 설명\n"
        "## 3. Synthesis Methods\n"
        "- 합성 방법 비교 분석\n"
        "## 4. Characterization\n"
        "- 분석 기법 및 결과 종합\n"
        "## 5. Performance Comparison\n"
        "- 성능 비교표 포함\n"
        "## 6. Conclusions\n"
        "- 종합 결론 및 향후 전망\n\n"
        "각 논문의 기여를 명확히 인용(저자, 연도)하며, 한국어로 작성하세요."
    ),
}

# 기본 프롬프트 레이블/카테고리 매핑 (시딩용)
DEFAULT_PROMPT_META = {
    "synthesis_conditions": {"label": "합성 조건 추출", "category": "analysis"},
    "experiment_summary": {"label": "실험 요약", "category": "analysis"},
    "summary": {"label": "논문 요약", "category": "analysis"},
    "significance": {"label": "학술적 의의", "category": "analysis"},
    "keywords": {"label": "키워드 추출", "category": "analysis"},
    "structured": {"label": "구조화 분석", "category": "analysis"},
    "trend": {"label": "연구 동향 분석", "category": "batch"},
    "review_draft": {"label": "문헌 리뷰 초안", "category": "batch"},
}

PDF_TEXT_LIMIT = 30000


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------

def _seed_default_prompts(db: Session):
    """DB에 기본 프롬프트가 없으면 시딩"""
    existing = {pt.name for pt in db.query(PromptTemplate.name).all()}
    for name, prompt_text in SYSTEM_PROMPTS.items():
        if name not in existing:
            meta = DEFAULT_PROMPT_META.get(name, {"label": name, "category": "analysis"})
            db.add(PromptTemplate(
                name=name,
                label=meta["label"],
                category=meta["category"],
                system_prompt=prompt_text,
                is_default=True,
            ))
    db.commit()


def get_system_prompt(db: Session, analysis_type: str) -> str:
    """DB 커스텀 프롬프트 우선, 없으면 하드코딩 기본값 사용. BASE_CONTEXT를 항상 앞에 붙임."""
    pt = db.query(PromptTemplate).filter(PromptTemplate.name == analysis_type).first()
    if pt:
        prompt_body = pt.system_prompt
    elif analysis_type in SYSTEM_PROMPTS:
        prompt_body = SYSTEM_PROMPTS[analysis_type]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"'{analysis_type}'에 대한 프롬프트를 찾을 수 없습니다.",
        )
    return BASE_CONTEXT + prompt_body


def build_user_prompt(paper: Paper) -> str:
    title = paper.title or ""
    abstract = paper.abstract or ""
    pdf_text = paper.pdf_text or ""

    parts = [f"# 제목\n{title}"]

    if abstract:
        parts.append(f"# 초록\n{abstract}")

    if pdf_text:
        text = pdf_text[:PDF_TEXT_LIMIT]
        parts.append(f"# 본문\n{text}")
    else:
        parts.append(
            "\n(PDF 본문 없음 — 초록만으로 분석해 주세요. "
            "정보가 부족한 항목은 '초록만으로 확인 불가'로 표시하세요.)"
        )

    return "\n\n".join(parts)


def build_multi_paper_prompt(papers: List[Paper]) -> str:
    """여러 논문을 하나의 유저 프롬프트로 결합"""
    sections = []
    for i, paper in enumerate(papers, 1):
        title = paper.title or "(제목 없음)"
        abstract = paper.abstract or "(초록 없음)"
        year = paper.year or "N/A"
        # 저자 정보
        authors_str = ""
        if paper.authors_json:
            try:
                authors = json.loads(paper.authors_json)
                author_names = [a.get("name", "") for a in authors[:3]]
                authors_str = ", ".join(author_names)
                if len(authors) > 3:
                    authors_str += " et al."
            except (json.JSONDecodeError, TypeError):
                pass

        section = f"## 논문 {i}: {title}\n- 저자: {authors_str}\n- 연도: {year}\n- 초록: {abstract}"

        # 기존 분석 결과가 있으면 포함
        if paper.analyses:
            for a in paper.analyses:
                section += f"\n\n### [{a.analysis_type}] 분석 결과:\n{a.result_text[:3000]}"

        pdf_text = paper.pdf_text or ""
        if pdf_text:
            # 여러 논문이라 각각 텍스트를 줄임
            limit = max(5000, PDF_TEXT_LIMIT // len(papers)) if papers else PDF_TEXT_LIMIT
            section += f"\n\n### 본문 (발췌):\n{pdf_text[:limit]}"

        sections.append(section)

    return "\n\n---\n\n".join(sections)


def _serialize_analysis(a: AIAnalysisResult) -> dict:
    return {
        "id": a.id,
        "paper_id": a.paper_id,
        "analysis_type": a.analysis_type,
        "result_text": a.result_text,
        "result_json": a.result_json,
        "ai_backend": a.ai_backend,
        "model_name": a.model_name,
        "created_at": a.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# 단일 논문 분석
# ---------------------------------------------------------------------------

@router.post("/analyze/{paper_id}")
async def analyze_paper(
    paper_id: int,
    body: dict,
    db: Session = Depends(get_db),
):
    analysis_type = body.get("analysis_type")
    if not analysis_type or analysis_type not in ANALYSIS_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 분석 유형입니다. 가능한 유형: {', '.join(ANALYSIS_TYPES)}",
        )

    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    # DB 우선 프롬프트
    system_prompt = get_system_prompt(db, analysis_type)
    user_prompt = build_user_prompt(paper)

    # Phase B 마이그레이션 #2: analyze_paper. structured면 expect="json", 아니면 "text".
    from services.llm import LLMError
    from services.llm.router import call_llm

    expect_mode = "json" if analysis_type == "structured" else "text"

    try:
        value, backend, model_name = await call_llm(
            db,
            system=system_prompt,
            user=user_prompt,
            expect=expect_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=500, detail=f"AI 분석 오류: {str(e)[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 분석 오류: {str(e)}")

    # structured면 dict가 들어오므로 다시 직렬화 (legacy 컬럼 호환)
    result_json_str = None
    if expect_mode == "json":
        result_text = json.dumps(value, ensure_ascii=False)
        result_json_str = result_text
    else:
        result_text = value

    # 기존 동일 분석 삭제
    existing = db.query(AIAnalysisResult).filter(
        AIAnalysisResult.paper_id == paper_id,
        AIAnalysisResult.analysis_type == analysis_type,
    ).first()
    if existing:
        db.delete(existing)
        db.flush()

    analysis = AIAnalysisResult(
        paper_id=paper_id,
        analysis_type=analysis_type,
        result_text=result_text,
        result_json=result_json_str,
        ai_backend=backend,
        model_name=model_name,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return _serialize_analysis(analysis)


# ---------------------------------------------------------------------------
# 전체 분석 (기본 5가지 + structured)
# ---------------------------------------------------------------------------

@router.post("/analyze-all/{paper_id}")
async def analyze_all(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    # 단일 논문 대상 분석 유형만 (trend, review_draft 제외)
    single_types = [t for t in ANALYSIS_TYPES if t not in ("trend", "review_draft")]

    # Phase B 마이그레이션 #3: analyze_all
    from services.llm import LLMError as _LLMError_AA
    from services.llm.router import call_llm as _call_llm_AA

    results = []

    for analysis_type in single_types:
        system_prompt = get_system_prompt(db, analysis_type)
        user_prompt = build_user_prompt(paper)
        expect_mode = "json" if analysis_type == "structured" else "text"

        try:
            value, backend, model_name = await _call_llm_AA(
                db,
                system=system_prompt,
                user=user_prompt,
                expect=expect_mode,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except _LLMError_AA as e:
            raise HTTPException(status_code=500, detail=f"AI 분석 오류 ({analysis_type}): {str(e)[:200]}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 분석 오류 ({analysis_type}): {str(e)}")

        result_json_str = None
        if expect_mode == "json":
            result_text = json.dumps(value, ensure_ascii=False)
            result_json_str = result_text
        else:
            result_text = value

        existing = db.query(AIAnalysisResult).filter(
            AIAnalysisResult.paper_id == paper_id,
            AIAnalysisResult.analysis_type == analysis_type,
        ).first()
        if existing:
            db.delete(existing)
            db.flush()

        analysis = AIAnalysisResult(
            paper_id=paper_id,
            analysis_type=analysis_type,
            result_text=result_text,
            result_json=result_json_str,
            ai_backend=backend,
            model_name=model_name,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        results.append(_serialize_analysis(analysis))

    return results


# ---------------------------------------------------------------------------
# 배치 분석 (SSE 스트리밍)
# ---------------------------------------------------------------------------

@router.post("/batch-analyze")
async def batch_analyze(body: dict, db: Session = Depends(get_db)):
    paper_ids: list = body.get("paper_ids", [])
    analysis_types: list = body.get("analysis_types", ["summary"])

    if not paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids가 비어 있습니다.")

    # 유효성 검사
    invalid_types = [t for t in analysis_types if t not in ANALYSIS_TYPES]
    if invalid_types:
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 분석 유형: {', '.join(invalid_types)}",
        )

    # 배치 작업이므로 trend/review_draft 제외
    analysis_types = [t for t in analysis_types if t not in ("trend", "review_draft")]
    if not analysis_types:
        raise HTTPException(status_code=400, detail="유효한 분석 유형이 없습니다.")

    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    paper_map = {p.id: p for p in papers}
    total_tasks = len(paper_ids) * len(analysis_types)

    # BatchJob 생성
    batch_job = BatchJob(
        job_type="analysis",
        status="running",
        paper_ids_json=json.dumps(paper_ids),
        total_items=total_tasks,
        completed_items=0,
        progress=0,
    )
    db.add(batch_job)
    db.commit()
    db.refresh(batch_job)
    job_id = batch_job.id

    # Phase B 마이그레이션 #4: batch_analyze (SSE 스트림 — 에러 이벤트는 그대로)
    from services.llm.router import call_llm as _call_llm_BA

    async def event_stream():
        completed = 0

        yield f"data: {json.dumps({'type': 'start', 'job_id': job_id, 'total': total_tasks}, ensure_ascii=False)}\n\n"

        for pid in paper_ids:
            paper = paper_map.get(pid)
            if not paper:
                yield f"data: {json.dumps({'type': 'skip', 'paper_id': pid, 'reason': '논문을 찾을 수 없음'}, ensure_ascii=False)}\n\n"
                completed += len(analysis_types)
                continue

            for atype in analysis_types:
                try:
                    system_prompt = get_system_prompt(db, atype)
                    user_prompt = build_user_prompt(paper)
                    expect_mode = "json" if atype == "structured" else "text"

                    value, backend, model_name = await _call_llm_BA(
                        db,
                        system=system_prompt,
                        user=user_prompt,
                        expect=expect_mode,
                    )

                    result_json_str = None
                    if expect_mode == "json":
                        result_text = json.dumps(value, ensure_ascii=False)
                        result_json_str = result_text
                    else:
                        result_text = value

                    # 기존 분석 삭제
                    existing = db.query(AIAnalysisResult).filter(
                        AIAnalysisResult.paper_id == pid,
                        AIAnalysisResult.analysis_type == atype,
                    ).first()
                    if existing:
                        db.delete(existing)
                        db.flush()

                    analysis = AIAnalysisResult(
                        paper_id=pid,
                        analysis_type=atype,
                        result_text=result_text,
                        result_json=result_json_str,
                        ai_backend=backend,
                        model_name=model_name,
                    )
                    db.add(analysis)
                    db.commit()
                    db.refresh(analysis)

                    completed += 1
                    progress = int((completed / total_tasks) * 100)

                    # BatchJob 업데이트
                    job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
                    if job:
                        job.completed_items = completed
                        job.progress = progress
                        db.commit()

                    yield f"data: {json.dumps({'type': 'progress', 'paper_id': pid, 'paper_title': paper.title, 'analysis_type': atype, 'completed': completed, 'total': total_tasks, 'progress': progress, 'result': _serialize_analysis(analysis)}, ensure_ascii=False)}\n\n"

                except Exception as e:
                    completed += 1
                    yield f"data: {json.dumps({'type': 'error', 'paper_id': pid, 'analysis_type': atype, 'error': str(e), 'completed': completed, 'total': total_tasks}, ensure_ascii=False)}\n\n"

        # 완료 처리
        job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
        if job:
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()

        yield f"data: {json.dumps({'type': 'done', 'job_id': job_id, 'completed': completed, 'total': total_tasks}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# 트렌드 분석
# ---------------------------------------------------------------------------

@router.post("/trend-analyze")
async def trend_analyze(body: dict, db: Session = Depends(get_db)):
    paper_ids: list = body.get("paper_ids", [])
    if not paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids가 비어 있습니다.")

    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    system_prompt = get_system_prompt(db, "trend")
    user_prompt = build_multi_paper_prompt(papers)

    # Phase B 마이그레이션 #5: trend_analyze (expect="text")
    from services.llm import LLMError as _LLMError_T
    from services.llm.router import call_llm as _call_llm_T

    try:
        result_text, backend, model_name = await _call_llm_T(
            db,
            system=system_prompt,
            user=user_prompt,
            expect="text",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except _LLMError_T as e:
        raise HTTPException(status_code=500, detail=f"트렌드 분석 오류: {str(e)[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"트렌드 분석 오류: {str(e)}")

    # BatchJob 기록
    job = BatchJob(
        job_type="trend",
        status="completed",
        paper_ids_json=json.dumps(paper_ids),
        total_items=len(papers),
        completed_items=len(papers),
        progress=100,
        result_text=result_text,
        completed_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "job_id": job.id,
        "result_text": result_text,
        "ai_backend": backend,
        "model_name": model_name,
        "paper_count": len(papers),
    }


# ---------------------------------------------------------------------------
# 문헌 리뷰 초안 생성
# ---------------------------------------------------------------------------

@router.post("/review-draft")
async def review_draft(body: dict, db: Session = Depends(get_db)):
    paper_ids: list = body.get("paper_ids", [])
    if not paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids가 비어 있습니다.")

    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    system_prompt = get_system_prompt(db, "review_draft")
    user_prompt = build_multi_paper_prompt(papers)

    # Phase B 마이그레이션 #6: review_draft (expect="text")
    from services.llm import LLMError as _LLMError_R
    from services.llm.router import call_llm as _call_llm_R

    try:
        result_text, backend, model_name = await _call_llm_R(
            db,
            system=system_prompt,
            user=user_prompt,
            expect="text",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except _LLMError_R as e:
        raise HTTPException(status_code=500, detail=f"리뷰 초안 생성 오류: {str(e)[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리뷰 초안 생성 오류: {str(e)}")

    # BatchJob 기록
    job = BatchJob(
        job_type="review_draft",
        status="completed",
        paper_ids_json=json.dumps(paper_ids),
        total_items=len(papers),
        completed_items=len(papers),
        progress=100,
        result_text=result_text,
        completed_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "job_id": job.id,
        "result_text": result_text,
        "ai_backend": backend,
        "model_name": model_name,
        "paper_count": len(papers),
    }


# ---------------------------------------------------------------------------
# 태그 자동 추천
# ---------------------------------------------------------------------------

@router.post("/suggest-tags/{paper_id}")
async def suggest_tags(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    system_prompt = (
        BASE_CONTEXT
        + "논문의 초록과 제목을 읽고, 이 논문을 분류하기에 적합한 태그 3~5개를 추천하세요.\n"
        "반드시 아래 JSON 형식으로만 응답하세요:\n"
        '{"tags": ["태그1", "태그2", "태그3"]}\n\n'
        "규칙:\n"
        "- 구체적인 촉매 물질, 반응 유형, 합성법, 분석법 위주\n"
        "- 영어 기술 용어는 영어로, 분야명은 한국어 가능\n"
        "- 너무 일반적인 태그(예: '논문', '연구') 금지"
    )

    title = paper.title or ""
    abstract = paper.abstract or ""
    user_prompt = f"# 제목\n{title}\n\n# 초록\n{abstract}"

    # Phase B 마이그레이션 #1: strict_call(expect="schema", schema=TagSuggestion)
    from services.llm import TagSuggestion, LLMError
    from services.llm.router import call_llm

    try:
        suggestion, backend, model_name = await call_llm(
            db,
            system=system_prompt,
            user=user_prompt,
            expect="schema",
            schema=TagSuggestion,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LLMError as e:
        return {
            "paper_id": paper_id,
            "suggested_tags": [],
            "ai_backend": "",
            "model_name": "",
            "error": f"AI 호출 실패: {str(e)[:120]}",
            "raw": (e.last_raw or "")[:300],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"태그 추천 오류: {str(e)}")

    # 검증된 schema 인스턴스 → 그대로 반환 (정규화는 TagSuggestion validator에서 이미 수행)
    return {
        "paper_id": paper_id,
        "suggested_tags": suggestion.tags,
        "ai_backend": backend,
        "model_name": model_name,
    }


# ---------------------------------------------------------------------------
# 프롬프트 템플릿 CRUD
# ---------------------------------------------------------------------------

@router.get("/prompts")
async def list_prompts(db: Session = Depends(get_db)):
    """모든 프롬프트 템플릿 목록. 없으면 기본값 시딩."""
    count = db.query(PromptTemplate).count()
    if count == 0:
        _seed_default_prompts(db)

    prompts = db.query(PromptTemplate).order_by(PromptTemplate.category, PromptTemplate.name).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "label": p.label,
            "category": p.category,
            "system_prompt": p.system_prompt,
            "is_default": p.is_default,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in prompts
    ]


@router.get("/prompts/{name}")
async def get_prompt(name: str, db: Session = Depends(get_db)):
    pt = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
    if not pt:
        raise HTTPException(status_code=404, detail=f"프롬프트 '{name}'을 찾을 수 없습니다.")
    return {
        "id": pt.id,
        "name": pt.name,
        "label": pt.label,
        "category": pt.category,
        "system_prompt": pt.system_prompt,
        "is_default": pt.is_default,
        "created_at": pt.created_at.isoformat() if pt.created_at else None,
        "updated_at": pt.updated_at.isoformat() if pt.updated_at else None,
    }


@router.post("/prompts")
async def create_prompt(body: dict, db: Session = Depends(get_db)):
    name = body.get("name")
    label = body.get("label", name)
    category = body.get("category", "analysis")
    system_prompt = body.get("system_prompt")

    if not name or not system_prompt:
        raise HTTPException(status_code=400, detail="name과 system_prompt는 필수입니다.")

    existing = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"프롬프트 '{name}'이 이미 존재합니다.")

    pt = PromptTemplate(
        name=name,
        label=label,
        category=category,
        system_prompt=system_prompt,
        is_default=False,
    )
    db.add(pt)
    db.commit()
    db.refresh(pt)

    return {
        "id": pt.id,
        "name": pt.name,
        "label": pt.label,
        "category": pt.category,
        "system_prompt": pt.system_prompt,
        "is_default": pt.is_default,
    }


@router.put("/prompts/{name}")
async def update_prompt(name: str, body: dict, db: Session = Depends(get_db)):
    pt = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
    if not pt:
        raise HTTPException(status_code=404, detail=f"프롬프트 '{name}'을 찾을 수 없습니다.")

    if "label" in body:
        pt.label = body["label"]
    if "category" in body:
        pt.category = body["category"]
    if "system_prompt" in body:
        pt.system_prompt = body["system_prompt"]

    pt.is_default = False  # 수정하면 커스텀으로 전환
    pt.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(pt)

    return {
        "id": pt.id,
        "name": pt.name,
        "label": pt.label,
        "category": pt.category,
        "system_prompt": pt.system_prompt,
        "is_default": pt.is_default,
    }


@router.post("/prompts/reset")
async def reset_prompts(db: Session = Depends(get_db)):
    """모든 프롬프트를 기본값으로 초기화"""
    # 기본 프롬프트만 삭제 후 재생성 (커스텀 프롬프트는 유지)
    db.query(PromptTemplate).filter(
        PromptTemplate.name.in_(list(SYSTEM_PROMPTS.keys()))
    ).delete(synchronize_session=False)
    db.commit()

    _seed_default_prompts(db)

    return {"message": "기본 프롬프트가 초기화되었습니다.", "count": len(SYSTEM_PROMPTS)}


# ---------------------------------------------------------------------------
# 연결 테스트
# ---------------------------------------------------------------------------

@router.post("/test-connection")
async def test_connection(db: Session = Depends(get_db)):
    ai = AIClient(db)
    return await ai.test_connection()


# ---------------------------------------------------------------------------
# 분석 히스토리
# ---------------------------------------------------------------------------

@router.get("/history")
async def get_history(
    paper_id: Optional[int] = Query(None),
    analysis_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(AIAnalysisResult)
    if paper_id is not None:
        query = query.filter(AIAnalysisResult.paper_id == paper_id)
    if analysis_type is not None:
        query = query.filter(AIAnalysisResult.analysis_type == analysis_type)
    analyses = query.order_by(AIAnalysisResult.created_at.desc()).all()
    return [_serialize_analysis(a) for a in analyses]
