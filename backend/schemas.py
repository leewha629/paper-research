from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


# --- Paper ---

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


class TagInfo(BaseModel):
    id: int
    name: str
    color: str

    class Config:
        from_attributes = True


class FolderInfo(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class AIAnalysisResultOut(BaseModel):
    id: int
    paper_id: int
    analysis_type: str
    result_text: str
    result_json: Optional[str] = None
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
    tags: List[TagInfo] = []
    folders: List[FolderInfo] = []
    analyses: List[AIAnalysisResultOut] = []

    class Config:
        from_attributes = True


# --- Collection ---

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


# --- Tag ---

class TagCreate(BaseModel):
    name: str
    color: str = "#6c63ff"


class TagUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class TagOut(BaseModel):
    id: int
    name: str
    color: str
    created_at: datetime
    paper_count: int = 0

    class Config:
        from_attributes = True


# --- Folder ---

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class FolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None


class FolderOut(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    created_at: datetime
    paper_count: int = 0
    children: List["FolderOut"] = []

    class Config:
        from_attributes = True


# --- AI ---

class AIAnalyzeRequest(BaseModel):
    analysis_type: str


class BatchAnalyzeRequest(BaseModel):
    paper_ids: List[int]
    analysis_types: List[str] = ["summary", "synthesis_conditions", "experiment_summary"]


class ReviewDraftRequest(BaseModel):
    paper_ids: List[int]


class TrendAnalysisRequest(BaseModel):
    paper_ids: List[int]


# --- Subscription / Alert ---

class SubscriptionCreate(BaseModel):
    sub_type: str  # "keyword" / "author" / "citation"
    query: str
    label: Optional[str] = None


class SubscriptionOut(BaseModel):
    id: int
    sub_type: str
    query: str
    label: Optional[str] = None
    is_active: bool
    last_checked: Optional[datetime] = None
    created_at: datetime
    unread_count: int = 0

    class Config:
        from_attributes = True


class AlertOut(BaseModel):
    id: int
    subscription_id: int
    paper_id_s2: str
    title: str
    authors_json: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    relevance_score: Optional[float] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- BatchJob ---

class BatchJobOut(BaseModel):
    id: int
    job_type: str
    status: str
    progress: int
    total_items: int
    completed_items: int
    result_text: Optional[str] = None
    result_json: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Prompt Template ---

class PromptTemplateCreate(BaseModel):
    name: str
    label: str
    category: str
    system_prompt: str


class PromptTemplateUpdate(BaseModel):
    label: Optional[str] = None
    system_prompt: Optional[str] = None


class PromptTemplateOut(BaseModel):
    id: int
    name: str
    label: str
    category: str
    system_prompt: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Filter Preset ---

class FilterPresetCreate(BaseModel):
    name: str
    filters_json: str


class FilterPresetUpdate(BaseModel):
    name: Optional[str] = None
    filters_json: Optional[str] = None


class FilterPresetOut(BaseModel):
    id: int
    name: str
    filters_json: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Settings ---

class SettingUpdate(BaseModel):
    ai_backend: Optional[str] = None
    claude_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    semantic_scholar_api_key: Optional[str] = None
    unpaywall_email: Optional[str] = None


# --- Dashboard ---

class DashboardStats(BaseModel):
    total_papers: int = 0
    total_collections: int = 0
    total_tags: int = 0
    total_folders: int = 0
    unread_papers: int = 0
    reading_papers: int = 0
    read_papers: int = 0
    important_papers: int = 0
    unread_alerts: int = 0
    papers_by_year: dict = {}
    papers_by_venue: dict = {}
    papers_by_tag: dict = {}
    recent_papers: List[dict] = []
    recent_searches: List[dict] = []
