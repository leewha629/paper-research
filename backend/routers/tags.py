from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import Tag, PaperTag, Paper

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
async def list_tags(db: Session = Depends(get_db)):
    """모든 태그 목록 (논문 수 포함)"""
    tags = db.query(Tag).order_by(Tag.created_at.desc()).all()
    result = []
    for tag in tags:
        count = db.query(PaperTag).filter(PaperTag.tag_id == tag.id).count()
        result.append({
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
            "created_at": tag.created_at.isoformat(),
            "paper_count": count,
        })
    return result


@router.post("")
async def create_tag(body: dict, db: Session = Depends(get_db)):
    """태그 생성"""
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="태그 이름이 필요합니다.")

    existing = db.query(Tag).filter(Tag.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="같은 이름의 태그가 이미 존재합니다.")

    tag = Tag(name=name, color=body.get("color", "#6c63ff"))
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "created_at": tag.created_at.isoformat(),
        "paper_count": 0,
    }


@router.put("/{id}")
async def update_tag(id: int, body: dict, db: Session = Depends(get_db)):
    """태그 수정"""
    tag = db.query(Tag).filter(Tag.id == id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다.")

    if "name" in body and body["name"]:
        # 중복 이름 확인
        dup = db.query(Tag).filter(Tag.name == body["name"], Tag.id != id).first()
        if dup:
            raise HTTPException(status_code=400, detail="같은 이름의 태그가 이미 존재합니다.")
        tag.name = body["name"]
    if "color" in body:
        tag.color = body["color"]

    db.commit()
    db.refresh(tag)
    count = db.query(PaperTag).filter(PaperTag.tag_id == tag.id).count()
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "created_at": tag.created_at.isoformat(),
        "paper_count": count,
    }


@router.delete("/{id}")
async def delete_tag(id: int, db: Session = Depends(get_db)):
    """태그 삭제"""
    tag = db.query(Tag).filter(Tag.id == id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다.")
    db.delete(tag)
    db.commit()
    return {"success": True}


@router.post("/{id}/papers")
async def add_paper_to_tag(id: int, body: dict, db: Session = Depends(get_db)):
    """태그에 논문 추가"""
    tag = db.query(Tag).filter(Tag.id == id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다.")

    paper_id = body.get("paper_id")
    if not paper_id:
        raise HTTPException(status_code=400, detail="paper_id가 필요합니다.")

    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    existing = db.query(PaperTag).filter(
        PaperTag.paper_id == paper_id,
        PaperTag.tag_id == id,
    ).first()
    if existing:
        return {"success": True, "message": "이미 태그에 포함되어 있습니다."}

    pt = PaperTag(paper_id=paper_id, tag_id=id)
    db.add(pt)
    db.commit()
    return {"success": True}


@router.delete("/{id}/papers/{paper_id}")
async def remove_paper_from_tag(id: int, paper_id: int, db: Session = Depends(get_db)):
    """태그에서 논문 제거"""
    pt = db.query(PaperTag).filter(
        PaperTag.tag_id == id,
        PaperTag.paper_id == paper_id,
    ).first()
    if not pt:
        raise HTTPException(status_code=404, detail="해당 논문이 태그에 없습니다.")
    db.delete(pt)
    db.commit()
    return {"success": True}


@router.get("/{id}/papers")
async def list_papers_by_tag(id: int, db: Session = Depends(get_db)):
    """태그에 속한 논문 목록"""
    tag = db.query(Tag).filter(Tag.id == id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다.")

    pt_records = db.query(PaperTag).filter(PaperTag.tag_id == id).all()
    papers = []
    for pt in pt_records:
        paper = db.query(Paper).filter(Paper.id == pt.paper_id).first()
        if paper:
            papers.append({
                "id": paper.id,
                "paper_id": paper.paper_id,
                "title": paper.title,
                "authors_json": paper.authors_json,
                "year": paper.year,
                "venue": paper.venue,
                "citation_count": paper.citation_count,
                "status": paper.status,
                "saved_at": paper.saved_at.isoformat(),
            })
    return papers
