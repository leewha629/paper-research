import io
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
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
