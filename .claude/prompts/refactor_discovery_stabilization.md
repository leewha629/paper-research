역할: paper-research Phase E — Discovery 안정화 + bootstrap ACID + folder_papers UNIQUE.

## 단일 진실원
- docs/REFACTOR_PLAN.md §"Phase E — Discovery 안정화 + bootstrap ACID"
- 본 프롬프트의 §"v2 추가 항목"

## 사용자 환경 (확정)
- multi-project 운영: CF4, CPN0, 미래 AI/3D 등 여러 collection 동시 운영 예정
- 단일 호스트, 단일 워커 (uvicorn --reload), Mac Mini 16GB
- iCloud 동기화 아님 → data/ 하위 락 파일 OK
- pydantic 2.5+, fcntl 사용 가능 (macOS)
- 기존 paper 99 사고: folder_papers에 같은 paper_id가 두 폴더 동시 존재. UNIQUE 제약 없음.

## 제약
- Phase D 산출물 변경 금지 (RELEVANCE_SYSTEM, recalibrate.py)
- Phase F 작업 금지 (죽은 API 정리)
- APScheduler / cron 등 자동 스케줄러 도입 금지 (Phase 2 별도)
- Multi-collection auto-routing 금지 (별도 Phase)
- 자동으로 다음 Phase 진입 금지
- 마이그레이션 003 자동 적용 금지 — 사용자 승인 후

## 작업 1 — fcntl 파일 락 (collection별)

### 설계
- 신규 모듈: backend/services/discovery_lock.py
- 컨텍스트 매니저: with discovery_lock(collection_id): ...
- 락 파일: data/discovery_<collection_id>.lock
- fcntl.flock(LOCK_EX | LOCK_NB) — 즉시 차단, 블록 없음
- 락 잡힌 상태 재호출 → LockedError raise → 호출부가 409 Conflict로 변환

### 변경
- backend/routers/dashboard.py: _discovery_running dict 제거. _run_discovery_async를 discovery_lock으로 wrap. collection_id 인자 필수.
- backend/services/run_agent_once.py: CLI도 동일 락. collection_id 명시 필수. 락 실패 시 stderr 에러 + exit 1.

## 작업 2 — heartbeat

### 설계
- AgentRun에 컬럼 추가: heartbeat_at (DateTime), locked_by (String "<hostname>:<pid>")
- discovery 사이클 시작 시 INSERT, 30s마다 asyncio task로 UPDATE
- 사이클 종료 시 task 취소 + 마지막 heartbeat 기록

### 변경
- backend/models.py: AgentRun에 heartbeat_at, locked_by 추가
- backend/services/research_agent/discovery.py: 사이클 시작/종료 hook
- backend/routers/dashboard.py agent/status 엔드포인트: heartbeat_at 반환 (UI 연결은 Phase F)

## 작업 3 — bootstrap ACID

### 설계
- Collection/Folder upsert에 IntegrityError 폴백 패턴
- UNIQUE 제약 의존: Collection.name 기존 사용, Folder (parent_id, name) 추가 검토 후 적용
- 단일 트랜잭션 또는 savepoint

### 변경
- backend/services/research_agent/bootstrap.py:43-69: try INSERT / except IntegrityError → SELECT 복구
- backend/models.py: Folder에 (parent_id, name) UNIQUE 추가 (필요시)

## 작업 4 — folder_papers UNIQUE 제약 + paper 99 cleanup

### 설계
- folder_papers에 UNIQUE(folder_id, paper_id) 인덱스 추가
- 마이그레이션 003에서 순서:
  (a) 기존 중복 row 제거 — 각 paper_id마다 가장 최근 folder_id만 유지
  (b) UNIQUE INDEX 추가
- 폴더 배치 로직 변경 — INSERT 전 기존 매핑 DELETE (move semantics) 또는 INSERT OR REPLACE

### 변경
- backend/migrations/003_phase_e_lock_heartbeat_unique.py 신규:
  * AgentRun.heartbeat_at, locked_by ADD COLUMN
  * folder_papers 중복 제거 (paper 99 자동 처리됨)
  * folder_papers UNIQUE INDEX (folder_id, paper_id)
  * Folder (parent_id, name) UNIQUE 검토 후 추가
  * 적용 전 data/backups/papers_pre_003_<ts>.db 자동 백업
- backend/services/research_agent/discovery.py:243-283: 폴더 배치 move semantics
- backend/models.py: FolderPaper.__table_args__에 UNIQUE 추가

## 작업 5 — Discovery 저장 트랜잭션

### 설계
- Paper / PaperCollection / FolderPaper 저장을 단일 트랜잭션
- 부분 실패 시 rollback + logger.error + (선택) AgentRun 실패 기록

### 변경
- backend/services/research_agent/discovery.py 저장 블록을 with db.begin(): 또는 savepoint로 wrap

## 작업 6 — 멀티프로젝트 격리 검증

- discovery_lock(collection_id) 호출 시 collection_id별 별도 락 파일
- 두 collection 동시 → 둘 다 진행 가능
- 같은 collection 두 번째 → 즉시 거부

## 작업 7 — 테스트

PLAN §A.2 Phase E 5건:
- test_discovery_lock::test_concurrent_run_blocked_by_file_lock
- test_discovery_lock::test_lock_released_on_exception
- test_discovery_lock::test_heartbeat_updated_during_long_run
- test_bootstrap_acid::test_concurrent_collection_creation_idempotent
- test_discovery_save::test_partial_failure_rolls_back_paper_collection_folder

Phase E v2 추가 5건:
- test_folder_papers_unique::test_duplicate_paper_in_two_folders_blocked
- test_folder_papers_unique::test_move_semantics_replaces_existing
- test_discovery_lock::test_two_collections_run_in_parallel
- test_discovery_lock::test_same_collection_blocks_second
- test_migration_003::test_paper_99_cleaned_up

총 22 (기존) + 10 (Phase E) = 32건 목표. 통합 마커 분리 가능.

## 산출물
1. backend/services/discovery_lock.py 신규
2. backend/migrations/003_phase_e_lock_heartbeat_unique.py 신규
3. backend/models.py 수정 (AgentRun, FolderPaper, Folder)
4. backend/routers/dashboard.py 수정
5. backend/services/research_agent/{bootstrap.py, discovery.py} 수정
6. backend/services/run_agent_once.py 수정
7. tests 10건 추가
8. docs/PHASE_E_DONE.md

## 작성 방식
- 마이그레이션 003 적용 직전 사용자에게 명시 알림 + 백업 자동 생성 + 사용자 응답 대기
- 파일 단위 즉시 Write
- 각 작업 끝날 때마다 pytest 실행

## 사용자 검증 체크포인트 (PHASE_E_DONE.md 끝에 체크리스트)
- [ ] 마이그레이션 003 백업 파일 위치 확인
- [ ] 중복 0건: SELECT paper_id, COUNT(*) FROM folder_papers GROUP BY paper_id HAVING COUNT(*) > 1
- [ ] 두 collection 동시 recalibrate 시도 → 둘 다 정상
- [ ] 같은 collection 두 번째 시도 → 즉시 LockedError
- [ ] HTTP POST /api/dashboard/agent/run 두 번 → 두 번째 409
- [ ] kill -9로 강제 종료 후 lsof 0건 (락 자동 해제)
- [ ] agent_runs.heartbeat_at 갱신 SQL 확인

## 금지
- APScheduler / cron 금지
- collection auto-creation 금지
- Phase D 산출물 변경 금지
- 마이그레이션 자동 적용 금지