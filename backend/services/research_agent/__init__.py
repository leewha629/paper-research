"""
자율 연구 에이전트.

Phase 2~6 lean 구현:
- bootstrap: 프로젝트 등록 + 시스템 폴더 시드
- discovery: 1 사이클 (키워드 → S2 검색 → 중복제거 → 관련도 → 분류 → 로그)
"""
from .bootstrap import bootstrap_project, ProjectHandles, SYSTEM_FOLDER_NAMES
from .discovery import run_discovery_cycle, DiscoveryReport

__all__ = [
    "bootstrap_project",
    "ProjectHandles",
    "SYSTEM_FOLDER_NAMES",
    "run_discovery_cycle",
    "DiscoveryReport",
]
