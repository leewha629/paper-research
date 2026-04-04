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
}


PDF_TEXT_LIMIT = 30000


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
        parts.append("\n(PDF 본문 없음 — 초록만으로 분석해 주세요. 정보가 부족한 항목은 '초록만으로 확인 불가'로 표시하세요.)")

    return "\n\n".join(parts)


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
