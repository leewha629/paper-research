import io
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, PlainTextResponse
from sqlalchemy.orm import Session
from typing import List

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from database import get_db
from models import Paper, AIAnalysisResult

router = APIRouter(prefix="/export", tags=["export"])


def get_analysis_text(db: Session, paper_id: int, analysis_type: str) -> str:
    a = db.query(AIAnalysisResult).filter(
        AIAnalysisResult.paper_id == paper_id,
        AIAnalysisResult.analysis_type == analysis_type,
    ).order_by(AIAnalysisResult.created_at.desc()).first()
    return a.result_text if a else ""


@router.get("/csv")
async def export_csv(
    paper_ids: str = Query(..., description="Comma-separated paper IDs"),
    db: Session = Depends(get_db),
):
    try:
        ids = [int(x.strip()) for x in paper_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="유효하지 않은 논문 ID 형식입니다.")

    papers = db.query(Paper).filter(Paper.id.in_(ids)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    rows = []
    for paper in papers:
        authors_list = []
        if paper.authors_json:
            try:
                authors_data = json.loads(paper.authors_json)
                authors_list = [a.get("name", "") for a in authors_data]
            except Exception:
                pass

        rows.append({
            "paper_id": paper.paper_id,
            "title": paper.title,
            "authors": "; ".join(authors_list),
            "year": paper.year or "",
            "journal": paper.venue or "",
            "citation_count": paper.citation_count,
            "doi": paper.doi or "",
            "status": paper.status,
            "synthesis_conditions": get_analysis_text(db, paper.id, "synthesis_conditions"),
            "experiment_summary": get_analysis_text(db, paper.id, "experiment_summary"),
            "summary": get_analysis_text(db, paper.id, "summary"),
            "significance": get_analysis_text(db, paper.id, "significance"),
            "keywords": get_analysis_text(db, paper.id, "keywords"),
        })

    df = pd.DataFrame(rows)
    output = io.StringIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=papers_export.csv"},
    )


@router.post("/report")
async def export_report(body: dict, db: Session = Depends(get_db)):
    paper_ids = body.get("paper_ids", [])
    include_ai = body.get("include_ai", True)

    if not paper_ids:
        raise HTTPException(status_code=400, detail="논문 ID가 필요합니다.")

    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1d27"),
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=4,
        textColor=colors.HexColor("#6c63ff"),
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=9,
        spaceAfter=4,
        leading=14,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#8892a4"),
        spaceAfter=2,
    )
    analysis_style = ParagraphStyle(
        "Analysis",
        parent=styles["Normal"],
        fontSize=9,
        leading=14,
        spaceAfter=6,
        backColor=colors.HexColor("#f8f9fa"),
    )

    story = []

    # Report header
    story.append(Paragraph("논문 연구 보고서", title_style))
    story.append(Paragraph(f"총 {len(papers)}편의 논문", label_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#6c63ff")))
    story.append(Spacer(1, 0.5 * cm))

    analysis_type_labels = {
        "synthesis_conditions": "합성 조건",
        "experiment_summary": "실험 요약",
        "summary": "요약",
        "significance": "중요성 및 한계",
        "keywords": "키워드",
    }

    for i, paper in enumerate(papers):
        if i > 0:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
            story.append(Spacer(1, 0.3 * cm))

        # Paper title
        safe_title = paper.title.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        story.append(Paragraph(f"{i+1}. {safe_title}", heading_style))

        # Authors
        authors_list = []
        if paper.authors_json:
            try:
                authors_data = json.loads(paper.authors_json)
                authors_list = [a.get("name", "") for a in authors_data[:5]]
                if len(authors_data) > 5:
                    authors_list.append("et al.")
            except Exception:
                pass
        if authors_list:
            story.append(Paragraph(f"저자: {', '.join(authors_list)}", label_style))

        # Metadata
        meta_parts = []
        if paper.year:
            meta_parts.append(f"연도: {paper.year}")
        if paper.venue:
            meta_parts.append(f"저널: {paper.venue}")
        if paper.citation_count:
            meta_parts.append(f"피인용수: {paper.citation_count}")
        if paper.doi:
            meta_parts.append(f"DOI: {paper.doi}")
        if meta_parts:
            story.append(Paragraph(" | ".join(meta_parts), label_style))

        story.append(Spacer(1, 0.2 * cm))

        # Abstract
        if paper.abstract:
            story.append(Paragraph("초록", ParagraphStyle("SmallHeading", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", spaceAfter=3)))
            safe_abstract = paper.abstract.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            story.append(Paragraph(safe_abstract, body_style))

        # AI analyses
        if include_ai:
            for analysis_type, label in analysis_type_labels.items():
                text = get_analysis_text(db, paper.id, analysis_type)
                if text:
                    story.append(Paragraph(label, ParagraphStyle("SmallHeading", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", spaceAfter=3, spaceBefore=6)))
                    safe_text = text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
                    story.append(Paragraph(safe_text, body_style))

        story.append(Spacer(1, 0.4 * cm))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=paper_report.pdf"},
    )


# --- 헬퍼 함수 ---

def _parse_authors(authors_json: str) -> list:
    """authors_json에서 저자명 리스트 추출"""
    if not authors_json:
        return []
    try:
        data = json.loads(authors_json)
        return [a.get("name", "") for a in data if a.get("name")]
    except Exception:
        return []


def _make_cite_key(paper: Paper) -> str:
    """BibTeX cite key 생성: AuthorYear"""
    authors = _parse_authors(paper.authors_json)
    first_author = authors[0] if authors else "Unknown"
    # 성(last name) 추출
    last_name = first_author.split()[-1] if first_author else "Unknown"
    # 알파벳/숫자만 남기기
    last_name = re.sub(r"[^a-zA-Z0-9]", "", last_name)
    year = paper.year or "XXXX"
    return f"{last_name}{year}"


def _fetch_papers(paper_ids_str: str, db: Session) -> list:
    """쉼표 구분 ID 문자열로 논문 목록 조회"""
    try:
        ids = [int(x.strip()) for x in paper_ids_str.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="유효하지 않은 논문 ID 형식입니다.")
    papers = db.query(Paper).filter(Paper.id.in_(ids)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")
    return papers


# --- BibTeX 내보내기 ---

@router.get("/bibtex")
async def export_bibtex(
    paper_ids: str = Query(..., description="Comma-separated paper IDs"),
    db: Session = Depends(get_db),
):
    """BibTeX 형식으로 논문 내보내기"""
    papers = _fetch_papers(paper_ids, db)

    entries = []
    used_keys = {}
    for paper in papers:
        key = _make_cite_key(paper)
        # 중복 키 방지
        if key in used_keys:
            used_keys[key] += 1
            key = f"{key}{chr(96 + used_keys[key])}"  # a, b, c...
        else:
            used_keys[key] = 1

        authors = _parse_authors(paper.authors_json)
        author_str = " and ".join(authors) if authors else "Unknown"

        lines = [f"@article{{{key},"]
        lines.append(f"  title = {{{paper.title}}},")
        lines.append(f"  author = {{{author_str}}},")
        if paper.year:
            lines.append(f"  year = {{{paper.year}}},")
        if paper.venue:
            lines.append(f"  journal = {{{paper.venue}}},")
        if paper.doi:
            lines.append(f"  doi = {{{paper.doi}}},")
        lines.append("}")
        entries.append("\n".join(lines))

    content = "\n\n".join(entries)
    return PlainTextResponse(
        content,
        media_type="application/x-bibtex",
        headers={"Content-Disposition": "attachment; filename=papers.bib"},
    )


# --- RIS 내보내기 ---

@router.get("/ris")
async def export_ris(
    paper_ids: str = Query(..., description="Comma-separated paper IDs"),
    db: Session = Depends(get_db),
):
    """RIS 형식으로 논문 내보내기 (EndNote/Zotero 호환)"""
    papers = _fetch_papers(paper_ids, db)

    entries = []
    for paper in papers:
        lines = ["TY  - JOUR"]
        lines.append(f"TI  - {paper.title}")

        authors = _parse_authors(paper.authors_json)
        for author in authors:
            lines.append(f"AU  - {author}")

        if paper.year:
            lines.append(f"PY  - {paper.year}")
        if paper.venue:
            lines.append(f"JO  - {paper.venue}")
        if paper.doi:
            lines.append(f"DO  - {paper.doi}")
        if paper.abstract:
            lines.append(f"AB  - {paper.abstract}")
        if paper.paper_id:
            lines.append(f"ID  - {paper.paper_id}")

        lines.append("ER  - ")
        entries.append("\n".join(lines))

    content = "\n\n".join(entries)
    return PlainTextResponse(
        content,
        media_type="application/x-research-info-systems",
        headers={"Content-Disposition": "attachment; filename=papers.ris"},
    )


# --- Markdown 내보내기 ---

@router.get("/markdown")
async def export_markdown(
    paper_ids: str = Query(..., description="Comma-separated paper IDs"),
    db: Session = Depends(get_db),
):
    """Markdown 테이블 형식으로 논문 내보내기 (노트 포함)"""
    papers = _fetch_papers(paper_ids, db)

    lines = ["# 논문 목록", ""]
    lines.append("| # | 제목 | 저자 | 연도 | 학술지 | 인용수 | DOI | 상태 |")
    lines.append("|---|------|------|------|--------|--------|-----|------|")

    for i, paper in enumerate(papers, 1):
        authors = _parse_authors(paper.authors_json)
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."
        doi_str = paper.doi or ""
        lines.append(
            f"| {i} | {paper.title} | {author_str} | {paper.year or ''} "
            f"| {paper.venue or ''} | {paper.citation_count or 0} | {doi_str} | {paper.status} |"
        )

    # 노트가 있는 논문 추가
    notes_section = []
    for paper in papers:
        if paper.user_notes:
            notes_section.append(f"### {paper.title}")
            notes_section.append(f"{paper.user_notes}")
            notes_section.append("")

    if notes_section:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 논문 노트")
        lines.append("")
        lines.extend(notes_section)

    content = "\n".join(lines)
    return PlainTextResponse(
        content,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=papers.md"},
    )


# --- 서지 목록 내보내기 ---

@router.post("/bibliography")
async def export_bibliography(body: dict, db: Session = Depends(get_db)):
    """포맷된 참고문헌 목록 생성"""
    paper_ids = body.get("paper_ids", [])
    style = body.get("style", "acs")

    if not paper_ids:
        raise HTTPException(status_code=400, detail="논문 ID가 필요합니다.")

    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")

    references = []
    for i, paper in enumerate(papers, 1):
        authors = _parse_authors(paper.authors_json)
        ref = _format_reference(paper, authors, style, i)
        references.append(ref)

    return {
        "style": style,
        "references": references,
        "text": "\n\n".join(references),
    }


def _format_reference(paper: Paper, authors: list, style: str, index: int) -> str:
    """스타일에 따라 참고문헌 포맷"""
    year = paper.year or "n.d."
    venue = paper.venue or ""
    doi = paper.doi or ""

    if style == "acs":
        # ACS 스타일: 저자. 제목. 학술지 연도, DOI.
        author_str = _format_authors_acs(authors)
        ref = f"({index}) {author_str} {paper.title}. "
        if venue:
            ref += f"*{venue}* "
        ref += f"**{year}**."
        if doi:
            ref += f" DOI: {doi}."
        return ref

    elif style == "rsc":
        # RSC 스타일: 저자, 학술지, 연도, DOI.
        author_str = _format_authors_rsc(authors)
        ref = f"{index}. {author_str}, "
        if venue:
            ref += f"*{venue}*, "
        ref += f"{year}."
        if doi:
            ref += f" DOI: {doi}."
        return ref

    elif style == "elsevier":
        # Elsevier 스타일: 저자, 제목, 학술지 (연도) DOI.
        author_str = _format_authors_elsevier(authors)
        ref = f"[{index}] {author_str}, {paper.title}, "
        if venue:
            ref += f"{venue} "
        ref += f"({year})."
        if doi:
            ref += f" https://doi.org/{doi}"
        return ref

    else:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 스타일입니다: {style}. acs, rsc, elsevier 중 선택하세요.")


def _format_authors_acs(authors: list) -> str:
    """ACS 스타일 저자 포맷: Last, F. I.; Last, F. I."""
    if not authors:
        return "Unknown"
    formatted = []
    for name in authors:
        parts = name.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = " ".join(p[0] + "." for p in parts[:-1])
            formatted.append(f"{last}, {initials}")
        else:
            formatted.append(name)
    return "; ".join(formatted)


def _format_authors_rsc(authors: list) -> str:
    """RSC 스타일 저자 포맷: F. I. Last, F. I. Last"""
    if not authors:
        return "Unknown"
    formatted = []
    for name in authors:
        parts = name.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = " ".join(p[0] + "." for p in parts[:-1])
            formatted.append(f"{initials} {last}")
        else:
            formatted.append(name)
    if len(formatted) > 2:
        return ", ".join(formatted[:-1]) + " and " + formatted[-1]
    elif len(formatted) == 2:
        return " and ".join(formatted)
    return formatted[0]


def _format_authors_elsevier(authors: list) -> str:
    """Elsevier 스타일 저자 포맷: F.I. Last, F.I. Last"""
    if not authors:
        return "Unknown"
    formatted = []
    for name in authors:
        parts = name.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = "".join(p[0] + "." for p in parts[:-1])
            formatted.append(f"{initials} {last}")
        else:
            formatted.append(name)
    if len(formatted) > 5:
        return ", ".join(formatted[:5]) + ", et al."
    return ", ".join(formatted)
