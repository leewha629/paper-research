from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class PaperBase(BaseModel):
    paper_id: str
    title: str
    authors_json: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    citation_count: int = 0
    reference_count: int = 0
    is_open_access: bool = False
    pdf_url: Optional[str] = None
    external_ids_json: Optional[str] = None
    fields_of_study_json: Optional[str] = None


class PaperCreate(PaperBase):
    pass


class PaperUpdate(BaseModel):
    status: Optional[str] = None
    user_notes: Optional[str] = None


class CollectionInfo(BaseModel):
    id: int
    name: str
    color: str

    class Config:
        from_attributes = True


class AIAnalysisResultOut(BaseModel):
    id: int
    paper_id: int
    analysis_type: str
    result_text: str
    ai_backend: str
    model_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class PaperOut(BaseModel):
    id: int
    paper_id: str
    title: str
    authors_json: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    citation_count: int = 0
    reference_count: int = 0
    is_open_access: bool = False
    pdf_url: Optional[str] = None
    local_pdf_path: Optional[str] = None
    pdf_text: Optional[str] = None
    external_ids_json: Optional[str] = None
    fields_of_study_json: Optional[str] = None
    saved_at: datetime
    status: str
    user_notes: Optional[str] = None
    collections: List[CollectionInfo] = []
    analyses: List[AIAnalysisResultOut] = []

    class Config:
        from_attributes = True


class CollectionBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#6c63ff"


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class CollectionOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    color: str
    created_at: datetime
    paper_count: int = 0

    class Config:
        from_attributes = True


class AIAnalyzeRequest(BaseModel):
    analysis_type: str


class SettingUpdate(BaseModel):
    ai_backend: Optional[str] = None
    claude_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    semantic_scholar_api_key: Optional[str] = None
    unpaywall_email: Optional[str] = None
