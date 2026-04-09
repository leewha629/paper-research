from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any, Literal
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


class BulkStatusUpdate(BaseModel):
    paper_ids: List[int]
    status: Literal["unread", "reading", "read", "important"]


class BulkDeleteRequest(BaseModel):
    paper_ids: List[int]


class CollectionPaperAdd(BaseModel):
    paper_id: int


class CollectionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str


class TagInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str


class FolderInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class AIAnalysisResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paper_id: int
    analysis_type: str
    result_text: str
    result_json: Optional[str] = None
    ai_backend: str
    model_name: str
    created_at: datetime


class PaperOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    color: str
    created_at: datetime
    paper_count: int = 0


# --- Tag ---

class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = "#6c63ff"


class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = None


class PaperTagAdd(BaseModel):
    paper_id: int


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    created_at: datetime
    paper_count: int = 0


# --- Folder ---

class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: Optional[int] = None


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    parent_id: Optional[int] = None


class FolderPaperAdd(BaseModel):
    paper_id: int


class PaperMove(BaseModel):
    paper_id: int
    target_folder_id: int


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: Optional[int] = None
    created_at: datetime
    paper_count: int = 0
    children: List["FolderOut"] = []


# --- AI ---

AnalysisTypeLiteral = Literal[
    "synthesis_conditions",
    "experiment_summary",
    "summary",
    "significance",
    "keywords",
    "structured",
    "trend",
    "review_draft",
]


class AnalyzeRequest(BaseModel):
    analysis_type: AnalysisTypeLiteral


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
    sub_type: Literal["keyword", "author", "citation"]
    query: str = Field(min_length=1)
    label: Optional[str] = None


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sub_type: str
    query: str
    label: Optional[str] = None
    is_active: bool
    last_checked: Optional[datetime] = None
    created_at: datetime
    unread_count: int = 0


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


# --- BatchJob ---

class BatchJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


# --- Prompt Template ---

class PromptTemplateCreate(BaseModel):
    name: str
    label: Optional[str] = None  # 미지정 시 라우터에서 name으로 대체
    category: str = "analysis"
    system_prompt: str


class PromptTemplateUpdate(BaseModel):
    label: Optional[str] = None
    category: Optional[str] = None
    system_prompt: Optional[str] = None


class PromptTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    label: str
    category: str
    system_prompt: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


# --- Filter Preset ---

class FilterPresetCreate(BaseModel):
    name: str
    filters_json: str


class FilterPresetUpdate(BaseModel):
    name: Optional[str] = None
    filters_json: Optional[str] = None


class FilterPresetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    filters_json: str
    created_at: datetime


# --- Settings ---

class SettingsUpdate(BaseModel):
    ai_backend: Optional[str] = None
    claude_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    semantic_scholar_api_key: Optional[str] = None
    unpaywall_email: Optional[str] = None
    check_interval: Optional[str] = None
    relevance_threshold: Optional[str] = None


# 하위 호환 alias (기존 코드에서 SettingUpdate로 참조 시)
SettingUpdate = SettingsUpdate


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
