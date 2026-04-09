import os
import re
import httpx
import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import Paper, AppSetting

router = APIRouter(prefix="/pdfs", tags=["pdfs"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF_DIR = os.path.join(BASE_DIR, "data", "pdfs")


def _safe_pdf_path(paper_id: str, suffix: str = "") -> str:
    """paper_id를 sanitize하여 안전한 PDF 파일 경로 반환.

    Phase F-1.3: path traversal 방어.
    """
    safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(paper_id))
    if not safe_id:
        raise HTTPException(status_code=400, detail="잘못된 paper_id")

    filename = f"{safe_id}{suffix}.pdf"
    path = os.path.join(PDF_DIR, filename)

    resolved = os.path.realpath(path)
    pdf_dir_resolved = os.path.realpath(PDF_DIR)
    if not resolved.startswith(pdf_dir_resolved + os.sep):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로")

    return resolved


def extract_pdf_text(path: str, max_chars: int = 50000) -> tuple:
    """Extract text from PDF. Returns (text, page_count)"""
    doc = fitz.open(path)
    text = ""
    page_count = len(doc)
    for page in doc:
        text += page.get_text()
        if len(text) > max_chars:
            break
    doc.close()
    return text[:max_chars], page_count


async def try_unpaywall(doi: str, email: str) -> Optional[str]:
    if not doi or not email:
        return None
    url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                best = data.get("best_oa_location")
                if best:
                    return best.get("url_for_pdf") or best.get("url")
        except Exception:
            pass
    return None


@router.post("/download/{paper_id}")
async def download_pdf(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    pdf_url = paper.pdf_url

    # Try Unpaywall if no PDF URL but has DOI
    if not pdf_url and paper.doi:
        unpaywall_email_setting = db.query(AppSetting).filter(
            AppSetting.key == "unpaywall_email"
        ).first()
        unpaywall_email = unpaywall_email_setting.value if unpaywall_email_setting else ""
        if unpaywall_email:
            pdf_url = await try_unpaywall(paper.doi, unpaywall_email)
            if pdf_url:
                paper.pdf_url = pdf_url

    if not pdf_url:
        raise HTTPException(
            status_code=404,
            detail="다운로드 가능한 PDF URL이 없습니다. PDF를 직접 업로드해 주세요.",
        )

    os.makedirs(PDF_DIR, exist_ok=True)
    save_path = _safe_pdf_path(paper.paper_id)

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(pdf_url, headers={"User-Agent": "paper-research-app/1.0"})
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(resp.content)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"PDF 다운로드 실패: HTTP {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PDF 다운로드 실패: {str(e)}")

    try:
        text, page_count = extract_pdf_text(save_path)
    except Exception as e:
        os.remove(save_path)
        raise HTTPException(status_code=500, detail=f"PDF 텍스트 추출 실패: {str(e)}")

    paper.local_pdf_path = save_path
    paper.pdf_text = text
    db.commit()

    return {
        "success": True,
        "pages": page_count,
        "text_length": len(text),
        "message": f"PDF 다운로드 완료 ({page_count}페이지, {len(text):,}자 추출)",
    }


@router.post("/upload/{paper_id}")
async def upload_pdf(
    paper_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    os.makedirs(PDF_DIR, exist_ok=True)
    save_path = _safe_pdf_path(paper.paper_id, "_manual")

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    try:
        text, page_count = extract_pdf_text(save_path)
    except Exception as e:
        os.remove(save_path)
        raise HTTPException(status_code=500, detail=f"PDF 텍스트 추출 실패: {str(e)}")

    paper.local_pdf_path = save_path
    paper.pdf_text = text
    db.commit()

    return {
        "success": True,
        "pages": page_count,
        "text_length": len(text),
        "message": f"PDF 업로드 완료 ({page_count}페이지, {len(text):,}자 추출)",
    }


@router.get("/{paper_id}")
async def get_pdf_status(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    has_local = paper.local_pdf_path and os.path.exists(paper.local_pdf_path)
    page_count = 0
    if has_local:
        try:
            doc = fitz.open(paper.local_pdf_path)
            page_count = len(doc)
            doc.close()
        except Exception:
            pass

    return {
        "has_local_pdf": has_local,
        "has_url": bool(paper.pdf_url),
        "pdf_url": paper.pdf_url,
        "local_pdf_path": paper.local_pdf_path,
        "pages": page_count,
        "has_text": bool(paper.pdf_text),
        "text_length": len(paper.pdf_text) if paper.pdf_text else 0,
    }
