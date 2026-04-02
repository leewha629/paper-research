from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
import json
from datetime import datetime

from database import get_db
from models import Paper, Collection, PaperCollection, AIAnalysisResult
from schemas import (
    PaperCreate, PaperUpdate, PaperOut,
    CollectionCreate, CollectionUpdate, CollectionOut,
    AIAnalysisResultOut,
)

router = APIRouter(tags=["papers"])


def paper_to_dict(paper: Paper, db: Session) -> dict:
    """Convert Paper model to dict with collections and analyses"""
    # Get collections
    pc_records = db.query(PaperCollection).filter(PaperCollection.paper_id == paper.id).all()
    collections = []
    for pc in pc_records:
        col = db.query(Collection).filter(Collection.id == pc.collection_id).first()
        if col:
            collections.append({"id": col.id, "name": col.name, "color": col.color})

    # Get analyses
    analyses = db.query(AIAnalysisResult).filter(AIAnalysisResult.paper_id == paper.id).all()
    analyses_list = [
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

    return {
        "id": paper.id,
        "paper_id": paper.paper_id,
        "title": paper.title,
        "authors_json": paper.authors_json,
        "year": paper.year,
        "venue": paper.venue,
        "abstract": paper.abstract,
        "doi": paper.doi,
        "citation_count": paper.citation_count,
        "reference_count": paper.reference_count,
        "is_open_access": paper.is_open_access,
        "pdf_url": paper.pdf_url,
        "local_pdf_path": paper.local_pdf_path,
        "pdf_text": paper.pdf_text,
        "external_ids_json": paper.external_ids_json,
        "fields_of_study_json": paper.fields_of_study_json,
        "saved_at": paper.saved_at.isoformat(),
        "status": paper.status,
        "user_notes": paper.user_notes,
        "collections": collections,
        "analyses": analyses_list,
    }


# --- Papers ---

@router.post("/papers")
async def save_paper(data: PaperCreate, db: Session = Depends(get_db)):
    """Save a paper to DB. Upsert if already exists."""
    existing = db.query(Paper).filter(Paper.paper_id == data.paper_id).first()
    if existing:
        return paper_to_dict(existing, db)

    paper = Paper(
        paper_id=data.paper_id,
        title=data.title,
        authors_json=data.authors_json,
        year=data.year,
        venue=data.venue,
        abstract=data.abstract,
        doi=data.doi,
        citation_count=data.citation_count,
        reference_count=data.reference_count,
        is_open_access=data.is_open_access,
        pdf_url=data.pdf_url,
        external_ids_json=data.external_ids_json,
        fields_of_study_json=data.fields_of_study_json,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper_to_dict(paper, db)


@router.get("/papers")
async def list_papers(
    collection_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query("saved_at", description="saved_at/year/citation_count"),
    sort_order: str = Query("desc", description="asc/desc"),
    db: Session = Depends(get_db),
):
    query = db.query(Paper)

    if collection_id is not None:
        query = query.join(PaperCollection, PaperCollection.paper_id == Paper.id).filter(
            PaperCollection.collection_id == collection_id
        )

    if status:
        query = query.filter(Paper.status == status)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Paper.title.ilike(search_term),
                Paper.authors_json.ilike(search_term),
            )
        )

    # Sorting
    sort_col = getattr(Paper, sort_by, Paper.saved_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    papers = query.all()
    return [paper_to_dict(p, db) for p in papers]


@router.get("/papers/by-s2id/{paper_id}")
async def get_paper_by_s2id(paper_id: str, db: Session = Depends(get_db)):
    """Get saved paper by Semantic Scholar paper ID"""
    paper = db.query(Paper).filter(Paper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="저장된 논문을 찾을 수 없습니다.")
    return paper_to_dict(paper, db)


@router.get("/papers/{id}")
async def get_paper(id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")
    return paper_to_dict(paper, db)


@router.patch("/papers/{id}")
async def update_paper(id: int, data: PaperUpdate, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    if data.status is not None:
        paper.status = data.status
    if data.user_notes is not None:
        paper.user_notes = data.user_notes

    db.commit()
    db.refresh(paper)
    return paper_to_dict(paper, db)


@router.delete("/papers/{id}")
async def delete_paper(id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")
    db.delete(paper)
    db.commit()
    return {"success": True}


@router.get("/papers/{id}/analyses")
async def get_paper_analyses(id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")
    analyses = db.query(AIAnalysisResult).filter(AIAnalysisResult.paper_id == id).all()
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


# --- Collections ---

@router.get("/collections")
async def list_collections(db: Session = Depends(get_db)):
    collections = db.query(Collection).all()
    result = []
    for col in collections:
        count = db.query(PaperCollection).filter(PaperCollection.collection_id == col.id).count()
        result.append({
            "id": col.id,
            "name": col.name,
            "description": col.description,
            "color": col.color,
            "created_at": col.created_at.isoformat(),
            "paper_count": count,
        })
    return result


@router.post("/collections")
async def create_collection(data: CollectionCreate, db: Session = Depends(get_db)):
    existing = db.query(Collection).filter(Collection.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="같은 이름의 컬렉션이 이미 존재합니다.")

    col = Collection(name=data.name, description=data.description, color=data.color)
    db.add(col)
    db.commit()
    db.refresh(col)
    return {
        "id": col.id,
        "name": col.name,
        "description": col.description,
        "color": col.color,
        "created_at": col.created_at.isoformat(),
        "paper_count": 0,
    }


@router.put("/collections/{id}")
async def update_collection(id: int, data: CollectionUpdate, db: Session = Depends(get_db)):
    col = db.query(Collection).filter(Collection.id == id).first()
    if not col:
        raise HTTPException(status_code=404, detail="컬렉션을 찾을 수 없습니다.")

    if data.name is not None:
        col.name = data.name
    if data.description is not None:
        col.description = data.description
    if data.color is not None:
        col.color = data.color

    db.commit()
    db.refresh(col)
    count = db.query(PaperCollection).filter(PaperCollection.collection_id == col.id).count()
    return {
        "id": col.id,
        "name": col.name,
        "description": col.description,
        "color": col.color,
        "created_at": col.created_at.isoformat(),
        "paper_count": count,
    }


@router.delete("/collections/{id}")
async def delete_collection(id: int, db: Session = Depends(get_db)):
    col = db.query(Collection).filter(Collection.id == id).first()
    if not col:
        raise HTTPException(status_code=404, detail="컬렉션을 찾을 수 없습니다.")
    db.delete(col)
    db.commit()
    return {"success": True}


@router.post("/collections/{id}/papers")
async def add_paper_to_collection(id: int, body: dict, db: Session = Depends(get_db)):
    col = db.query(Collection).filter(Collection.id == id).first()
    if not col:
        raise HTTPException(status_code=404, detail="컬렉션을 찾을 수 없습니다.")

    paper_id = body.get("paper_id")
    if not paper_id:
        raise HTTPException(status_code=400, detail="paper_id가 필요합니다.")

    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    existing = db.query(PaperCollection).filter(
        PaperCollection.paper_id == paper_id,
        PaperCollection.collection_id == id,
    ).first()
    if existing:
        return {"success": True, "message": "이미 컬렉션에 포함되어 있습니다."}

    pc = PaperCollection(paper_id=paper_id, collection_id=id)
    db.add(pc)
    db.commit()
    return {"success": True}


@router.delete("/collections/{id}/papers/{paper_id}")
async def remove_paper_from_collection(id: int, paper_id: int, db: Session = Depends(get_db)):
    pc = db.query(PaperCollection).filter(
        PaperCollection.collection_id == id,
        PaperCollection.paper_id == paper_id,
    ).first()
    if not pc:
        raise HTTPException(status_code=404, detail="해당 논문이 컬렉션에 없습니다.")
    db.delete(pc)
    db.commit()
    return {"success": True}
