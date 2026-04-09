import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import datetime, timezone

from database import get_db
from models import Subscription, Alert, AppSetting
from s2_client import S2Client
from services.llm.exceptions import (
    LLMError,
    LLMTimeoutError,
    LLMSchemaError,
    LLMUpstreamError,
)

logger = logging.getLogger("paper_research.alerts")

router = APIRouter(tags=["alerts"])


def _classify_llm_error(exc: BaseException) -> str:
    """LLMError 계열을 enum-like 짧은 reason 코드로 분류 (집계용)."""
    if isinstance(exc, LLMTimeoutError):
        return "timeout"
    if isinstance(exc, LLMSchemaError):
        return "schema_invalid"
    if isinstance(exc, LLMUpstreamError):
        # Ollama 미기동(ConnectError) → upstream으로 매핑되지만, 메시지에 connect가
        # 보이면 "ollama_down"으로 더 구체화.
        msg = (str(exc) or "").lower()
        if "connect" in msg or "connection" in msg or "11434" in msg:
            return "ollama_down"
        return "upstream_5xx"
    if isinstance(exc, LLMError):
        return "unknown"
    return "unknown"


# --- 구독 ---

@router.get("/subscriptions")
async def list_subscriptions(db: Session = Depends(get_db)):
    """모든 구독 목록 (미읽은 알림 수 포함)"""
    subs = db.query(Subscription).order_by(Subscription.created_at.desc()).all()
    result = []
    for sub in subs:
        unread = db.query(Alert).filter(
            Alert.subscription_id == sub.id,
            Alert.is_read == False,
        ).count()
        result.append({
            "id": sub.id,
            "sub_type": sub.sub_type,
            "query": sub.query,
            "label": sub.label,
            "is_active": sub.is_active,
            "last_checked": sub.last_checked.isoformat() if sub.last_checked else None,
            "created_at": sub.created_at.isoformat(),
            "unread_count": unread,
        })
    return result


@router.post("/subscriptions")
async def create_subscription(body: dict, db: Session = Depends(get_db)):
    """구독 생성"""
    sub_type = body.get("sub_type")
    query = body.get("query")

    if not sub_type or not query:
        raise HTTPException(status_code=400, detail="sub_type과 query가 필요합니다.")

    if sub_type not in ("keyword", "author", "citation"):
        raise HTTPException(status_code=400, detail="sub_type은 keyword, author, citation 중 하나여야 합니다.")

    sub = Subscription(
        sub_type=sub_type,
        query=query,
        label=body.get("label"),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {
        "id": sub.id,
        "sub_type": sub.sub_type,
        "query": sub.query,
        "label": sub.label,
        "is_active": sub.is_active,
        "last_checked": None,
        "created_at": sub.created_at.isoformat(),
        "unread_count": 0,
    }


@router.delete("/subscriptions/{id}")
async def delete_subscription(id: int, db: Session = Depends(get_db)):
    """구독 삭제"""
    sub = db.query(Subscription).filter(Subscription.id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="구독을 찾을 수 없습니다.")
    # 관련 알림도 삭제
    db.query(Alert).filter(Alert.subscription_id == id).delete()
    db.delete(sub)
    db.commit()
    return {"success": True}


@router.put("/subscriptions/{id}/toggle")
async def toggle_subscription(id: int, db: Session = Depends(get_db)):
    """구독 활성/비활성 토글"""
    sub = db.query(Subscription).filter(Subscription.id == id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="구독을 찾을 수 없습니다.")
    sub.is_active = not sub.is_active
    db.commit()
    db.refresh(sub)
    return {
        "id": sub.id,
        "sub_type": sub.sub_type,
        "query": sub.query,
        "label": sub.label,
        "is_active": sub.is_active,
        "last_checked": sub.last_checked.isoformat() if sub.last_checked else None,
        "created_at": sub.created_at.isoformat(),
    }


# --- 알림 ---

@router.get("/alerts")
async def list_alerts(
    subscription_id: Optional[int] = None,
    is_read: Optional[bool] = None,
    is_ai_failed: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """알림 목록 (미읽은 것 우선).

    Phase C: is_ai_failed 필터 추가. UI '전체' / 'AI 실패' 탭 분리에 사용.
    기본값(None)은 전체. is_ai_failed=False면 정상 알림만, True면 실패만.
    """
    query = db.query(Alert)

    if subscription_id is not None:
        query = query.filter(Alert.subscription_id == subscription_id)
    if is_read is not None:
        query = query.filter(Alert.is_read == is_read)
    if is_ai_failed is not None:
        query = query.filter(Alert.is_ai_failed == is_ai_failed)

    # 미읽은 것 우선, 최신순
    alerts = query.order_by(Alert.is_read.asc(), Alert.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "subscription_id": a.subscription_id,
            "paper_id_s2": a.paper_id_s2,
            "title": a.title,
            "authors_json": a.authors_json,
            "year": a.year,
            "venue": a.venue,
            "relevance_score": a.relevance_score,
            "is_read": a.is_read,
            "is_ai_failed": a.is_ai_failed,
            "ai_failure_reason": a.ai_failure_reason,
            "ai_failure_detail": a.ai_failure_detail,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@router.get("/alerts/count")
async def alert_count(db: Session = Depends(get_db)):
    """미읽은 알림 수 + AI 실패 카운터.

    Phase C: 'AI 실패' 탭 카운터를 위해 ai_failed 필드 추가.
    """
    unread = db.query(Alert).filter(Alert.is_read == False).count()
    ai_failed = db.query(Alert).filter(Alert.is_ai_failed == True).count()
    ai_failed_unread = (
        db.query(Alert)
        .filter(Alert.is_ai_failed == True, Alert.is_read == False)
        .count()
    )
    return {
        "unread": unread,
        "ai_failed": ai_failed,
        "ai_failed_unread": ai_failed_unread,
    }


@router.put("/alerts/{id}/read")
async def mark_alert_read(id: int, db: Session = Depends(get_db)):
    """알림 읽음 처리"""
    alert = db.query(Alert).filter(Alert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    alert.is_read = True
    db.commit()
    return {"success": True}


@router.put("/alerts/read-all")
async def mark_all_alerts_read(db: Session = Depends(get_db)):
    """모든 알림 읽음 처리"""
    db.query(Alert).filter(Alert.is_read == False).update({"is_read": True})
    db.commit()
    return {"success": True}


@router.post("/alerts/check")
async def check_alerts(db: Session = Depends(get_db)):
    """수동으로 새 논문 확인 (각 활성 구독에 대해 S2 API 호출)"""
    # S2 API 키 조회
    s2_key_record = db.query(AppSetting).filter(AppSetting.key == "semantic_scholar_api_key").first()
    s2_key = s2_key_record.value if s2_key_record and s2_key_record.value else None

    # 관련성 임계값
    threshold_record = db.query(AppSetting).filter(AppSetting.key == "relevance_threshold").first()
    threshold = float(threshold_record.value) if threshold_record and threshold_record.value else 6.0

    s2 = S2Client(api_key=s2_key)

    active_subs = db.query(Subscription).filter(Subscription.is_active == True).all()
    total_new = 0

    for sub in active_subs:
        try:
            papers = []

            if sub.sub_type == "keyword":
                result = await s2.search(query=sub.query, limit=20)
                papers = result.get("data") or []
            elif sub.sub_type == "author":
                result = await s2.search_by_author(sub.query, limit=10)
                authors = result.get("data") or []
                for author in authors[:3]:
                    for p in (author.get("papers") or []):
                        if p.get("paperId"):
                            papers.append(p)
            elif sub.sub_type == "citation":
                result = await s2.get_citations(sub.query, limit=20)
                citations = result.get("data") or []
                papers = [c.get("citingPaper", c) for c in citations if c.get("citingPaper") or c.get("paperId")]

            # last_checked 이후 논문만 필터링
            if sub.last_checked:
                filtered = []
                for p in papers:
                    p_year = p.get("year")
                    if p_year and p_year >= sub.last_checked.year:
                        filtered.append(p)
                papers = filtered

            # 이미 알림이 존재하는 논문 제외
            existing_s2_ids = set()
            if papers:
                paper_ids_s2 = [p.get("paperId") for p in papers if p.get("paperId")]
                existing_alerts = db.query(Alert.paper_id_s2).filter(
                    Alert.subscription_id == sub.id,
                    Alert.paper_id_s2.in_(paper_ids_s2),
                ).all()
                existing_s2_ids = {a[0] for a in existing_alerts}

            new_papers = [p for p in papers if p.get("paperId") and p["paperId"] not in existing_s2_ids]

            # AI로 관련성 점수 매기기 & 알림 생성
            # Phase C: 5.0 하드코딩 폴백 제거. AI 실패 시 별도 실패 레코드(is_ai_failed=True)로
            # 저장 → 사용자가 "AI 실패" 탭에서 즉시 인지.
            for p in new_papers[:10]:  # 한 번에 최대 10개
                authors_json = json.dumps(p.get("authors") or [], ensure_ascii=False)
                try:
                    score = await _score_relevance(db, sub, p)
                except LLMError as llm_err:
                    reason = _classify_llm_error(llm_err)
                    detail = str(llm_err)[:500]
                    logger.error(
                        "Alert score failed sub_id=%s paper=%s reason=%s detail=%s",
                        sub.id,
                        p.get("paperId"),
                        reason,
                        detail,
                    )
                    failure_alert = Alert(
                        subscription_id=sub.id,
                        paper_id_s2=p["paperId"],
                        title=p.get("title", "제목 없음"),
                        authors_json=authors_json,
                        year=p.get("year"),
                        venue=p.get("venue"),
                        relevance_score=None,
                        is_ai_failed=True,
                        ai_failure_reason=reason,
                        ai_failure_detail=detail,
                    )
                    db.add(failure_alert)
                    total_new += 1
                    continue

                if score >= threshold:
                    alert = Alert(
                        subscription_id=sub.id,
                        paper_id_s2=p["paperId"],
                        title=p.get("title", "제목 없음"),
                        authors_json=authors_json,
                        year=p.get("year"),
                        venue=p.get("venue"),
                        relevance_score=score,
                        is_ai_failed=False,
                    )
                    db.add(alert)
                    total_new += 1

            sub.last_checked = datetime.now(timezone.utc)

        except Exception:
            # 개별 구독 실패 시 계속 진행
            continue

    db.commit()
    return {"success": True, "new_alerts": total_new}


async def _score_relevance(db, sub: Subscription, paper: dict) -> float:
    """AI를 사용하여 논문의 구독 관련성 점수 계산 (0~10).

    Phase C: strict_call(expect="schema", schema=RelevanceScore)로 전환.
    정규식 폴백 제거. 실패 시 LLMError가 그대로 raise되며, 호출자는 Alert을
    만들지 않고 별도 실패 레코드(is_ai_failed=True)를 저장한다.
    """
    system = (
        "당신은 학술 논문 관련성 평가 전문가입니다. "
        "구독 조건과 논문 정보를 비교하여 0~10 점수와 한 줄 이유를 JSON으로 반환하세요. "
        '응답 형식 예: {"score": 8, "reason": "구독 키워드와 직접 일치"}.'
    )
    user_msg = f"""구독 유형: {sub.sub_type}
구독 쿼리: {sub.query}
{f'구독 레이블: {sub.label}' if sub.label else ''}

논문 제목: {paper.get('title', '')}
저자: {json.dumps(paper.get('authors', []), ensure_ascii=False)}
연도: {paper.get('year', '')}
학술지: {paper.get('venue', '')}
초록: {(paper.get('abstract') or '')[:500]}

이 논문이 구독 조건에 얼마나 관련이 있나요? JSON으로만 답하세요."""

    from services.llm import RelevanceScore
    from services.llm.router import call_llm

    rs, _, _ = await call_llm(
        db,
        system=system,
        user=user_msg,
        expect="schema",
        schema=RelevanceScore,
    )
    return min(float(rs.score), 10.0)
