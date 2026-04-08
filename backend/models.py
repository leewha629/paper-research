from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(String, unique=True, index=True, nullable=False)  # Semantic Scholar paper ID
    title = Column(String, nullable=False)
    authors_json = Column(Text, nullable=True)  # JSON: [{"name": "...", "affiliations": [...]}]
    year = Column(Integer, nullable=True)
    venue = Column(String, nullable=True)  # journal/conference
    abstract = Column(Text, nullable=True)
    doi = Column(String, nullable=True)
    citation_count = Column(Integer, default=0)
    reference_count = Column(Integer, default=0)
    is_open_access = Column(Boolean, default=False)
    pdf_url = Column(String, nullable=True)
    local_pdf_path = Column(String, nullable=True)
    pdf_text = Column(Text, nullable=True)
    external_ids_json = Column(Text, nullable=True)
    fields_of_study_json = Column(Text, nullable=True)
    saved_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="unread")  # "unread"/"reading"/"read"/"important"
    user_notes = Column(Text, nullable=True)

    # --- 자율 연구 에이전트용 (Migration 001) ---
    discovered_by = Column(String, default="manual")  # "manual" | "agent"
    relevance_score = Column(Integer, nullable=True)  # 0~9
    relevance_reason = Column(Text, nullable=True)
    relevance_checked_at = Column(DateTime, nullable=True)
    auto_summary = Column(Text, nullable=True)
    is_trashed = Column(Boolean, default=False, index=True)
    trashed_at = Column(DateTime, nullable=True)
    trash_reason = Column(String, nullable=True)  # "low_relevance" | "manual" | "duplicate"

    analyses = relationship("AIAnalysisResult", back_populates="paper", cascade="all, delete-orphan")
    paper_collections = relationship("PaperCollection", back_populates="paper", cascade="all, delete-orphan")
    paper_tags = relationship("PaperTag", back_populates="paper", cascade="all, delete-orphan")
    paper_folders = relationship("FolderPaper", back_populates="paper", cascade="all, delete-orphan")


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, default="#6c63ff")
    created_at = Column(DateTime, default=datetime.utcnow)

    paper_collections = relationship("PaperCollection", back_populates="collection", cascade="all, delete-orphan")


class PaperCollection(Base):
    __tablename__ = "paper_collections"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False)

    paper = relationship("Paper", back_populates="paper_collections")
    collection = relationship("Collection", back_populates="paper_collections")


# --- 태그 시스템 ---

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, default="#6c63ff")  # 6색 컬러 코딩
    created_at = Column(DateTime, default=datetime.utcnow)

    paper_tags = relationship("PaperTag", back_populates="tag", cascade="all, delete-orphan")


class PaperTag(Base):
    __tablename__ = "paper_tags"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)

    paper = relationship("Paper", back_populates="paper_tags")
    tag = relationship("Tag", back_populates="paper_tags")


# --- 폴더 시스템 (계층적) ---

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_system_folder = Column(Boolean, default=False)  # Migration 001 — 자동 시드 폴더 보호

    children = relationship("Folder", backref="parent", remote_side="Folder.id", cascade="all, delete-orphan",
                            single_parent=True, lazy="joined")
    folder_papers = relationship("FolderPaper", back_populates="folder", cascade="all, delete-orphan")


class FolderPaper(Base):
    __tablename__ = "folder_papers"

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)

    folder = relationship("Folder", back_populates="folder_papers")
    paper = relationship("Paper", back_populates="paper_folders")


# --- AI 분석 결과 ---

class AIAnalysisResult(Base):
    __tablename__ = "ai_analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    analysis_type = Column(String, nullable=False)
    result_text = Column(Text, nullable=False)
    result_json = Column(Text, nullable=True)  # 구조화된 JSON 결과
    ai_backend = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    paper = relationship("Paper", back_populates="analyses")


# --- 설정 ---

class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=True)


# --- 검색 캐시/히스토리 ---

class SearchCache(Base):
    __tablename__ = "search_cache"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, unique=True, index=True, nullable=False)
    queries_json = Column(Text, nullable=False)
    results_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, index=True, nullable=False)
    expanded_terms = Column(Text, nullable=True)
    queries_json = Column(Text, nullable=True)
    result_count = Column(Integer, default=0)
    total_collected = Column(Integer, default=0)
    searched_at = Column(DateTime, default=datetime.utcnow)


# --- 알림 구독 ---

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    sub_type = Column(String, nullable=False)  # "keyword" / "author" / "citation"
    query = Column(String, nullable=False)      # 검색어 또는 저자명 또는 paper_id
    label = Column(String, nullable=True)       # 표시용 레이블
    is_active = Column(Boolean, default=True)
    last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    paper_id_s2 = Column(String, nullable=False)  # S2 paper ID
    title = Column(String, nullable=False)
    authors_json = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    venue = Column(String, nullable=True)
    relevance_score = Column(Float, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # --- Phase C (Migration 002): AI 점수 실패 표면화 ---
    # is_ai_failed=True인 행은 relevance_score=NULL.
    # ai_failure_reason은 enum-like 짧은 코드로, GROUP BY 집계를 위해 분리.
    # 가능한 값: "timeout" | "schema_invalid" | "upstream_5xx" | "ollama_down" | "unknown"
    is_ai_failed = Column(Boolean, default=False, nullable=False, index=True)
    ai_failure_reason = Column(String, nullable=True)
    ai_failure_detail = Column(Text, nullable=True)  # raw 메시지 (디버깅용)

    subscription = relationship("Subscription")


# --- 배치 분석 ---

class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String, nullable=False)  # "analysis" / "review_draft" / "trend"
    status = Column(String, default="pending")  # "pending"/"running"/"completed"/"failed"
    paper_ids_json = Column(Text, nullable=False)  # JSON 배열
    progress = Column(Integer, default=0)  # 0~100
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    result_text = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# --- 프롬프트 템플릿 ---

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # 시스템 내부 이름
    label = Column(String, nullable=False)               # 표시용 레이블
    category = Column(String, nullable=False)             # "analysis" / "search" / "batch"
    system_prompt = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# --- 필터 프리셋 ---

class FilterPreset(Base):
    __tablename__ = "filter_presets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    filters_json = Column(Text, nullable=False)  # JSON: {journals, fields, year_from, year_to, ...}
    created_at = Column(DateTime, default=datetime.utcnow)


# --- 자율 연구 에이전트 (Migration 001) ---

class AgentRun(Base):
    """Discovery 사이클 1회 실행의 감사 로그."""
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    topic_snapshot = Column(Text, nullable=True)         # 실행 시점의 주제
    keywords_used = Column(Text, nullable=True)          # JSON 배열
    candidates_fetched = Column(Integer, default=0)      # S2에서 가져온 후보 수
    new_papers = Column(Integer, default=0)              # 중복 제거 후 신규
    saved_papers = Column(Integer, default=0)            # 실제 저장한 수
    trashed_papers = Column(Integer, default=0)          # 휴지통으로 보낸 수
    recommended_papers = Column(Integer, default=0)      # 풀분석 추천 폴더로 보낸 수
    is_dry_run = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    decisions_json = Column(Text, nullable=True)         # 결정 상세 (JSON)


class SearchedKeyword(Base):
    """키워드 쿨타임 추적 — 7일 이내 재사용 방지."""
    __tablename__ = "searched_keywords"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, unique=True, nullable=False)
    first_searched_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_searched_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    hit_count = Column(Integer, default=1)
