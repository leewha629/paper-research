from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import Paper, AIAnalysisResult
from ai_client import AIClient

router = APIRouter(prefix="/ai", tags=["ai"])

ANALYSIS_TYPES = [
    "synthesis_conditions",
    "experiment_summary",
    "summary",
    "significance",
    "keywords",
]

SYSTEM_PROMPTS = {
    "synthesis_conditions": (
        "당신은 촉매 및 재료 과학 전문가입니다. "
        "논문에서 촉매 조성, 합성 방법, 전구체, pH, 숙성 조건, 소성 프로파일을 추출하여 "
        "한국어로 구조화된 표 형태로 정리해 주세요. "
        "정보가 없는 항목은 '정보 없음'으로 표시하세요."
    ),
    "experiment_summary": (
        "당신은 화학공학 및 촉매 반응 전문가입니다. "
        "논문에서 반응 조건(온도, 공간속도, 공급 조성)과 성능 지표(전환율, 선택도, TOF)를 추출하여 "
        "한국어로 구조화된 표 형태로 정리해 주세요. "
        "정보가 없는 항목은 '정보 없음'으로 표시하세요."
    ),
    "summary": (
        "당신은 학술 논문 분석 전문가입니다. "
        "논문의 핵심 발견사항을 3-5문장의 한국어 요약문으로 작성해 주세요. "
        "명확하고 간결하게, 비전문가도 이해할 수 있도록 작성하세요."
    ),
    "significance": (
        "당신은 과학 연구 평가 전문가입니다. "
        "이 논문의 학술적 기여와 한계점을 한국어로 2-3단락으로 분석해 주세요. "
        "해당 분야에서의 중요성, 새로운 기여, 방법론적 강점과 약점, 향후 연구 방향을 포함하세요."
    ),
    "keywords": (
        "당신은 학술 논문 분류 전문가입니다. "
        "논문의 핵심 주제를 나타내는 8-12개의 키워드를 추출해 주세요. "
        "한국어와 영어 기술 용어를 혼합하여 쉼표로 구분된 목록으로 반환하세요. "
        "형식: 키워드1, 키워드2, keyword3, ..."
    ),
}


def build_user_prompt(paper: Paper) -> str:
    title = paper.title or ""
    abstract = paper.abstract or ""
    pdf_text = paper.pdf_text or ""

    if pdf_text:
        return (
            f"제목: {title}\n\n"
            f"초록:\n{abstract}\n\n"
            f"본문 (일부):\n{pdf_text[:10000]}"
        )
    else:
        return f"제목: {title}\n\n초록:\n{abstract}"


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

    system_prompt = SYSTEM_PROMPTS[analysis_type]
    user_prompt = build_user_prompt(paper)

    ai = AIClient(db)
    try:
        result_text, backend, model_name = await ai.complete(system_prompt, user_prompt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 분석 오류: {str(e)}")

    # Remove existing analysis of same type for this paper
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
        ai_backend=backend,
        model_name=model_name,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return {
        "id": analysis.id,
        "paper_id": analysis.paper_id,
        "analysis_type": analysis.analysis_type,
        "result_text": analysis.result_text,
        "ai_backend": analysis.ai_backend,
        "model_name": analysis.model_name,
        "created_at": analysis.created_at.isoformat(),
    }


@router.post("/analyze-all/{paper_id}")
async def analyze_all(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    ai = AIClient(db)
    results = []

    for analysis_type in ANALYSIS_TYPES:
        system_prompt = SYSTEM_PROMPTS[analysis_type]
        user_prompt = build_user_prompt(paper)

        try:
            result_text, backend, model_name = await ai.complete(system_prompt, user_prompt)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 분석 오류 ({analysis_type}): {str(e)}")

        # Remove existing
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
            ai_backend=backend,
            model_name=model_name,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        results.append({
            "id": analysis.id,
            "paper_id": analysis.paper_id,
            "analysis_type": analysis.analysis_type,
            "result_text": analysis.result_text,
            "ai_backend": analysis.ai_backend,
            "model_name": analysis.model_name,
            "created_at": analysis.created_at.isoformat(),
        })

    return results


@router.post("/test-connection")
async def test_connection(db: Session = Depends(get_db)):
    ai = AIClient(db)
    return await ai.test_connection()


@router.get("/history")
async def get_history(
    paper_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(AIAnalysisResult)
    if paper_id is not None:
        query = query.filter(AIAnalysisResult.paper_id == paper_id)
    analyses = query.order_by(AIAnalysisResult.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "paper_id": a.paper_id,
            "analysis_type": a.analysis_type,
            "result_text": a.result_text,
            "ai_backend": a.ai_backend,
            "model_name": a.model_name,
            "created_at": a.created_at.isoformat(),
        }
        for a in analyses
    ]
