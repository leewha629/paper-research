import os
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, SessionLocal, Base
from models import Paper, Collection, PaperCollection, AIAnalysisResult, AppSetting
from routers import search, papers, ai, pdfs, export, settings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(BASE_DIR, "data", "pdfs")
STATIC_DIR = os.path.join(BASE_DIR, "backend", "static")

app = FastAPI(title="Paper Research API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:7001"],
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
    "ollama_model": "gemma4:12b",
    "semantic_scholar_api_key": "",
    "unpaywall_email": "",
}


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
