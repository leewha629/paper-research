import os
import sys
import asyncio
import logging
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, SessionLocal, Base
from models import Paper, Collection, PaperCollection, AIAnalysisResult, AppSetting
from routers import search, papers, ai, pdfs, export, settings, tags, folders, alerts, dashboard
from services.llm.exceptions import (
    LLMError,
    LLMTimeoutError,
    LLMSchemaError,
    LLMUpstreamError,
)

logger = logging.getLogger("paper_research.main")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(BASE_DIR, "data", "pdfs")
STATIC_DIR = os.path.join(BASE_DIR, "backend", "static")

app = FastAPI(title="Paper Research API", version="1.0.0")


# ─── LLMError 글로벌 핸들러 (Phase C — fail-loud) ───────────────────────
# strict_call이 raise하는 LLMError 계열을 사용자 가시 503으로 매핑한다.
# 응답 스키마: {"error": "<error_code>", "detail": "<human-readable>"}
# error_code는 프론트가 분기할 수 있도록 enum-like 짧은 코드.
def _llm_error_code(exc: LLMError) -> str:
    if isinstance(exc, LLMTimeoutError):
        return "ai_timeout"
    if isinstance(exc, LLMSchemaError):
        return "ai_schema_invalid"
    if isinstance(exc, LLMUpstreamError):
        return "ai_upstream_unavailable"
    return "ai_unavailable"


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
    code = _llm_error_code(exc)
    detail = str(exc) or "AI 백엔드 호출이 실패했습니다."
    logger.warning(
        "LLMError on %s %s: code=%s detail=%s",
        request.method,
        request.url.path,
        code,
        detail,
    )
    return JSONResponse(
        status_code=503,
        content={
            "error": code,
            "detail": detail,
            "path": request.url.path,
        },
    )


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:7010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router, prefix="/api")
app.include_router(papers.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(pdfs.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(tags.router, prefix="/api")
app.include_router(folders.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")

# Mount PDF files
os.makedirs(PDF_DIR, exist_ok=True)
app.mount("/pdfs", StaticFiles(directory=PDF_DIR), name="pdfs")

# Mount frontend static files (after build)
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")


DEFAULT_SETTINGS = {
    "ai_backend": "claude",
    "claude_api_key": "",
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "gemma4:e4b",
    "semantic_scholar_api_key": "",
    "unpaywall_email": "",
    "check_interval": "24",
    "relevance_threshold": "6",
}


async def preload_ollama_model():
    """앱 시작 시 Ollama 모델을 RAM/VRAM에 미리 로드 (백엔드가 ollama로 설정된 경우)."""
    db = SessionLocal()
    try:
        backend_setting = db.query(AppSetting).filter(AppSetting.key == "ai_backend").first()
        if not backend_setting or backend_setting.value != "ollama":
            return
        base_url_setting = db.query(AppSetting).filter(AppSetting.key == "ollama_base_url").first()
        model_setting = db.query(AppSetting).filter(AppSetting.key == "ollama_model").first()
        base_url = (base_url_setting.value if base_url_setting else "") or "http://localhost:11434"
        model = (model_setting.value if model_setting else "") or "gemma4:e4b"
    finally:
        db.close()

    try:
        # 빈 prompt + keep_alive=30m 으로 모델만 메모리에 적재 (생성 안 함)
        async with httpx.AsyncClient(timeout=600.0) as client:
            await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": "30m"},
            )
        print(f"[startup] Ollama 모델 프리로드 완료: {model} (keep_alive=30m)")
    except Exception as e:
        print(f"[startup] Ollama 프리로드 실패 (무시): {e}")


@app.on_event("startup")
async def startup():
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create directories
    os.makedirs(PDF_DIR, exist_ok=True)

    # Seed default settings
    db = SessionLocal()
    try:
        for key, value in DEFAULT_SETTINGS.items():
            existing = db.query(AppSetting).filter(AppSetting.key == key).first()
            if not existing:
                db.add(AppSetting(key=key, value=value))
        db.commit()
    finally:
        db.close()

    # Ollama 모델 프리로드 (블로킹 방지: 백그라운드 태스크로 실행)
    asyncio.create_task(preload_ollama_model())


# SPA fallback: serve index.html for non-API routes
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str, request: Request):
    # Skip API routes
    if full_path.startswith("api/") or full_path.startswith("pdfs/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(
        status_code=200,
        content={"message": "Paper Research API is running. Build frontend with: cd frontend && npm run build"},
    )
