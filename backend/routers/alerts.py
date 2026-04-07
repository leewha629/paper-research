import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import datetime

from database import get_db
from models import Subscription, Alert, AppSetting
from s2_client import S2Client
from ai_client import AIClient

router = APIRouter(tags=["alerts"])


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
    db: Session = Depends(get_db),
):
    """알림 목록 (미읽은 것 우선)"""
    query = db.query(Alert)

    if subscription_id is not None:
        query = query.filter(Alert.subscription_id == subscription_id)
    if is_read is not None:
        query = query.filter(Alert.is_read == is_read)

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
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@router.get("/alerts/count")
async def alert_count(db: Session = Depends(get_db)):
    """미읽은 알림 수"""
    unread = db.query(Alert).filter(Alert.is_read == False).count()
    return {"unread": unread}


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
    ai = AIClient(db)

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
            for p in new_papers[:10]:  # 한 번에 최대 10개
                try:
                    score = await _score_relevance(ai, sub, p)
                    if score >= threshold:
                        authors_json = json.dumps(p.get("authors") or [], ensure_ascii=False)
                        alert = Alert(
                            subscription_id=sub.id,
                            paper_id_s2=p["paperId"],
                            title=p.get("title", "제목 없음"),
                            authors_json=authors_json,
                            year=p.get("year"),
                            venue=p.get("venue"),
                            relevance_score=score,
                        )
                        db.add(alert)
                        total_new += 1
                except Exception:
                    # AI 스코어링 실패 시 기본 점수로 추가
                    authors_json = json.dumps(p.get("authors") or [], ensure_ascii=False)
                    alert = Alert(
                        subscription_id=sub.id,
                        paper_id_s2=p["paperId"],
                        title=p.get("title", "제목 없음"),
                        authors_json=authors_json,
                        year=p.get("year"),
                        venue=p.get("venue"),
                        relevance_score=5.0,
                    )
                    db.add(alert)
                    total_new += 1

            sub.last_checked = datetime.utcnow()

        except Exception:
            # 개별 구독 실패 시 계속 진행
            continue

    db.commit()
    return {"success": True, "new_alerts": total_new}


async def _score_relevance(ai: AIClient, sub: Subscription, paper: dict) -> float:
    """AI를 사용하여 논문의 구독 관련성 점수 계산 (1~10)"""
    system = "당신은 학술 논문 관련성 평가 전문가입니다. 구독 조건과 논문 정보를 비교하여 1~10 점수를 매기세요. 숫자만 답하세요."
    user_msg = f"""구독 유형: {sub.sub_type}
구독 쿼리: {sub.query}
{f'구독 레이블: {sub.label}' if sub.label else ''}

논문 제목: {paper.get('title', '')}
저자: {json.dumps(paper.get('authors', []), ensure_ascii=False)}
연도: {paper.get('year', '')}
학술지: {paper.get('venue', '')}
초록: {(paper.get('abstract') or '')[:500]}

이 논문이 구독 조건에 얼마나 관련이 있나요? (1~10 점수만 답하세요)"""

    result_text, _, _ = await ai.complete(system, user_msg)
    # 숫자만 추출
    import re
    match = re.search(r"(\d+\.?\d*)", result_text.strip())
    if match:
        return min(float(match.group(1)), 10.0)
    return 5.0
