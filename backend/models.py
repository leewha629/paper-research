from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
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
    pdf_url = Column(String, nullable=True)          # open access PDF URL
    local_pdf_path = Column(String, nullable=True)   # path to downloaded/uploaded PDF
    pdf_text = Column(Text, nullable=True)           # extracted text from PDF (first 50000 chars)
    external_ids_json = Column(Text, nullable=True)  # JSON: {"DOI": "...", "ArXiv": "...", ...}
    fields_of_study_json = Column(Text, nullable=True)  # JSON list
    saved_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="unread")        # "unread"/"reading"/"reviewed"
    user_notes = Column(Text, nullable=True)

    analyses = relationship("AIAnalysisResult", back_populates="paper", cascade="all, delete-orphan")
    paper_collections = relationship("PaperCollection", back_populates="paper", cascade="all, delete-orphan")


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, default="#6c63ff")  # hex color for UI
    created_at = Column(DateTime, default=datetime.utcnow)

    paper_collections = relationship("PaperCollection", back_populates="collection", cascade="all, delete-orphan")


class PaperCollection(Base):
    __tablename__ = "paper_collections"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False)

    paper = relationship("Paper", back_populates="paper_collections")
    collection = relationship("Collection", back_populates="paper_collections")


class AIAnalysisResult(Base):
    __tablename__ = "ai_analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    analysis_type = Column(String, nullable=False)  # "synthesis_conditions"/"experiment_summary"/"summary"/"significance"/"keywords"
    result_text = Column(Text, nullable=False)
    ai_backend = Column(String, nullable=False)  # "claude"/"ollama"
    model_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    paper = relationship("Paper", back_populates="analyses")


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=True)


class SearchCache(Base):
    __tablename__ = "search_cache"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, unique=True, index=True, nullable=False)  # normalized user keyword
    queries_json = Column(Text, nullable=False)   # JSON: ["query1", "query2", ...]
    results_json = Column(Text, nullable=False)   # JSON: full results list with query_hit_count
    created_at = Column(DateTime, default=datetime.utcnow)


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, index=True, nullable=False)
    expanded_terms = Column(Text, nullable=True)     # JSON: AI가 확장한 용어 (약어 → 풀네임)
    queries_json = Column(Text, nullable=True)       # JSON: 생성된 쿼리 목록
    result_count = Column(Integer, default=0)        # 고관련도 결과 수
    total_collected = Column(Integer, default=0)     # S2 수집 총 수
    searched_at = Column(DateTime, default=datetime.utcnow)
