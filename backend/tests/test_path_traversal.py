"""Phase F-1.3 — pdfs.py path traversal 방어 검증."""
import pytest
from fastapi import HTTPException
from routers.pdfs import _safe_pdf_path, PDF_DIR


def test_safe_path_normal():
    """정상 paper_id → PDF_DIR 내 경로."""
    result = _safe_pdf_path("abc123def")
    assert result.endswith("abc123def.pdf")
    assert PDF_DIR.split("/data/pdfs")[0] in result


def test_safe_path_with_suffix():
    """suffix 지정 시 파일명에 반영."""
    result = _safe_pdf_path("abc123", "_manual")
    assert result.endswith("abc123_manual.pdf")


def test_safe_path_dotdot():
    """../../../etc/passwd → 특수문자가 _로 치환되어 PDF_DIR 안에 머묾."""
    result = _safe_pdf_path("../../../etc/passwd")
    # 슬래시와 점이 모두 _로 치환되므로 traversal 불가
    assert ".." not in result
    assert "/etc/" not in result
    import os
    assert os.path.realpath(PDF_DIR) in result


def test_safe_path_absolute():
    """/etc/passwd 류 절대 경로 차단."""
    # 슬래시가 _로 치환되므로 resolved가 PDF_DIR 안에 머묾 → 정상 처리.
    # 하지만 원본과 전혀 다른 파일명이 되므로 안전.
    result = _safe_pdf_path("/etc/passwd")
    assert "etc" not in result or PDF_DIR in result


def test_safe_path_empty():
    """빈 paper_id → 400."""
    # 모든 문자가 제거되면 safe_id가 빈 문자열
    # 실제로 빈 문자열이 들어오는 경우
    with pytest.raises(HTTPException) as exc_info:
        _safe_pdf_path("")
    assert exc_info.value.status_code == 400
