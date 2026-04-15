from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models import Folder, FolderPaper, Paper
from schemas import FolderCreate, FolderUpdate, FolderPaperAdd, PaperMove

router = APIRouter(prefix="/folders", tags=["folders"])


def folder_to_tree(folder: Folder, db: Session) -> dict:
    """폴더를 트리 구조 dict로 변환 (재귀)"""
    paper_count = db.query(FolderPaper).filter(FolderPaper.folder_id == folder.id).count()
    children = db.query(Folder).filter(Folder.parent_id == folder.id).order_by(Folder.name).all()
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_at": folder.created_at.isoformat() if folder.created_at else None,
        "paper_count": paper_count,
        "children": [folder_to_tree(child, db) for child in children],
    }


@router.get("")
async def list_folders(db: Session = Depends(get_db)):
    """모든 폴더를 flat 리스트로 반환 (parent_id 포함, 프론트가 트리 구성)."""
    all_folders = db.query(Folder).order_by(Folder.name).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "parent_id": f.parent_id,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "paper_count": db.query(FolderPaper).filter(FolderPaper.folder_id == f.id).count(),
            "is_system_folder": bool(f.is_system_folder),
        }
        for f in all_folders
    ]


@router.post("")
async def create_folder(body: FolderCreate, db: Session = Depends(get_db)):
    """폴더 생성"""
    if body.parent_id is not None:
        parent = db.query(Folder).filter(Folder.id == body.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="부모 폴더를 찾을 수 없습니다.")

    folder = Folder(name=body.name, parent_id=body.parent_id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_at": folder.created_at.isoformat() if folder.created_at else None,
        "paper_count": 0,
        "children": [],
    }


@router.put("/{id}")
async def update_folder(id: int, body: FolderUpdate, db: Session = Depends(get_db)):
    """폴더 이름 또는 부모 변경"""
    folder = db.query(Folder).filter(Folder.id == id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")

    if "name" in body.model_fields_set and body.name:
        folder.name = body.name

    if "parent_id" in body.model_fields_set:
        new_parent_id = body.parent_id
        # 자기 자신을 부모로 설정 방지
        if new_parent_id == id:
            raise HTTPException(status_code=400, detail="폴더를 자기 자신의 하위로 이동할 수 없습니다.")
        # 순환 참조 방지: 자식 폴더를 부모로 설정하는 것 방지
        if new_parent_id is not None:
            parent = db.query(Folder).filter(Folder.id == new_parent_id).first()
            if not parent:
                raise HTTPException(status_code=404, detail="부모 폴더를 찾을 수 없습니다.")
            # 순환 참조 확인
            check_id = new_parent_id
            while check_id is not None:
                check_folder = db.query(Folder).filter(Folder.id == check_id).first()
                if not check_folder:
                    break
                if check_folder.parent_id == id:
                    raise HTTPException(status_code=400, detail="순환 참조가 발생합니다.")
                check_id = check_folder.parent_id
        folder.parent_id = new_parent_id  # type: ignore[assignment]

    db.commit()
    db.refresh(folder)
    return folder_to_tree(folder, db)


@router.delete("/{id}")
async def delete_folder(id: int, db: Session = Depends(get_db)):
    """폴더 삭제 (하위 폴더도 함께 삭제)"""
    folder = db.query(Folder).filter(Folder.id == id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
    db.delete(folder)
    db.commit()
    return {"success": True}


@router.post("/{id}/papers")
async def add_paper_to_folder(id: int, body: FolderPaperAdd, db: Session = Depends(get_db)):
    """폴더에 논문 추가 (move semantics).

    DB 레벨에 UNIQUE(paper_id) 인덱스(uq_folder_papers_paper)가 걸려 있으므로
    한 paper는 동시에 한 폴더에만 속할 수 있다. 기존 다른 폴더 매핑이 있으면
    DELETE 후 INSERT 하는 단일 트랜잭션으로 처리한다.
    """
    folder = db.query(Folder).filter(Folder.id == id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")

    paper_id = body.paper_id
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    # 이미 같은 폴더에 있으면 no-op (멱등).
    existing_same = db.query(FolderPaper).filter(
        FolderPaper.paper_id == paper_id,
        FolderPaper.folder_id == id,
    ).first()
    if existing_same:
        return {"success": True, "message": "이미 폴더에 포함되어 있습니다."}

    # move semantics: paper_id에 대한 모든 기존 매핑 DELETE → 새 매핑 INSERT.
    # DELETE + INSERT는 같은 세션(단일 트랜잭션)에서 수행되어 원자성 보장.
    db.query(FolderPaper).filter(
        FolderPaper.paper_id == paper_id,
    ).delete(synchronize_session=False)
    db.add(FolderPaper(paper_id=paper_id, folder_id=id))
    db.commit()
    return {"success": True}


@router.delete("/{id}/papers/{paper_id}")
async def remove_paper_from_folder(id: int, paper_id: int, db: Session = Depends(get_db)):
    """폴더에서 논문 제거"""
    fp = db.query(FolderPaper).filter(
        FolderPaper.folder_id == id,
        FolderPaper.paper_id == paper_id,
    ).first()
    if not fp:
        raise HTTPException(status_code=404, detail="해당 논문이 폴더에 없습니다.")
    db.delete(fp)
    db.commit()
    return {"success": True}


@router.get("/{id}/papers")
async def list_papers_in_folder(id: int, db: Session = Depends(get_db)):
    """폴더에 속한 논문 목록"""
    folder = db.query(Folder).filter(Folder.id == id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")

    fp_records = db.query(FolderPaper).filter(FolderPaper.folder_id == id).all()
    papers = []
    for fp in fp_records:
        paper = db.query(Paper).filter(Paper.id == fp.paper_id).first()
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


@router.put("/{id}/move")
async def move_paper_between_folders(id: int, body: PaperMove, db: Session = Depends(get_db)):
    """논문을 다른 폴더로 이동 (move semantics).

    UNIQUE(paper_id) 제약을 유지하기 위해 paper_id 에 대한 모든 기존 매핑을
    제거한 뒤 target 폴더에 새로 INSERT 한다. source==target 인 경우 no-op.
    """
    paper_id = body.paper_id
    target_folder_id = body.target_folder_id

    # 원본 폴더 유효성 (사용자 에러 메시지 유지)
    fp = db.query(FolderPaper).filter(
        FolderPaper.folder_id == id,
        FolderPaper.paper_id == paper_id,
    ).first()
    if not fp:
        raise HTTPException(status_code=404, detail="원본 폴더에 해당 논문이 없습니다.")

    # 대상 폴더 확인
    target = db.query(Folder).filter(Folder.id == target_folder_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="대상 폴더를 찾을 수 없습니다.")

    # source == target: 할 일 없음
    if id == target_folder_id:
        return {"success": True, "message": "이미 대상 폴더에 있습니다."}

    # move semantics: 단일 트랜잭션으로 DELETE(paper_id 전체) + INSERT(target).
    db.query(FolderPaper).filter(
        FolderPaper.paper_id == paper_id,
    ).delete(synchronize_session=False)
    db.add(FolderPaper(folder_id=target_folder_id, paper_id=paper_id))
    db.commit()
    return {"success": True}
