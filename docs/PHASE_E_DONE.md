# Phase E — Discovery 안정화 + bootstrap ACID + folder_papers UNIQUE

상태: **구현 완료 + 마이그레이션 003 적용 완료 + 사용자 검증 완료**.
브랜치: `main` (커밋 미수행 — 사용자 검토 후 별도 단계)

## 적용 검증 (사용자 확인)
- ✅ folder_papers 중복 0건
- ✅ UNIQUE 인덱스 4개 (`uq_folder_papers_folder_paper`, `uq_folders_parent_name`, `uq_folders_root_name`, `idx_agent_runs_heartbeat`)
- ✅ `agent_runs.heartbeat_at`, `agent_runs.locked_by` 컬럼 정상
- ✅ 시스템 폴더 카운트 보존: **풀분석 추천 13 / 자동 발견 3 / 검토 대기 1 / 휴지통 33** (총 50건, 마이그레이션 전후 일치)
- ✅ 백업 2종 보존: `papers_pre_003_20260408_165336.db` (수동), `papers_pre_003_20260408_170144.db` (마이그레이션 자동)
- ✅ pytest 28 passed (회귀 없음)

---

## 산출물

| # | 파일 | 변경 | 비고 |
|---|---|---|---|
| 1 | `backend/services/discovery_lock.py` | **신규** | fcntl `flock(LOCK_EX|LOCK_NB)` 컨텍스트 매니저 |
| 2 | `backend/migrations/003_phase_e_lock_heartbeat_unique.py` | **신규** | heartbeat 컬럼 + folder_papers UNIQUE + paper 99 cleanup |
| 3 | `backend/models.py` | 수정 | `AgentRun.heartbeat_at/locked_by`, `FolderPaper` UNIQUE, `Folder` UNIQUE |
| 4 | `backend/routers/dashboard.py` | 수정 | `_discovery_running` dict 제거, `discovery_lock` wrap, asyncio task로 전환 |
| 5 | `backend/services/research_agent/bootstrap.py` | 수정 | `IntegrityError` 폴백 패턴 (savepoint) |
| 6 | `backend/services/research_agent/discovery.py` | 수정 | heartbeat hook + savepoint 저장 + move semantics |
| 7 | `backend/services/run_agent_once.py` | 수정 | CLI 락 wrap + 충돌 시 stderr/exit 1 |
| 8 | `backend/tests/test_discovery_lock.py` | **신규** | 5건 |
| 9 | `backend/tests/test_bootstrap_acid.py` | **신규** | 1건 |
| 10 | `backend/tests/test_discovery_save.py` | **신규** | 1건 |
| 11 | `backend/tests/test_folder_papers_unique.py` | **신규** | 2건 |
| 12 | `backend/tests/test_migration_003.py` | **신규** | 1건 |
| 13 | `backend/tests/test_dashboard_agent.py` | 갱신 | `_discovery_running` 의존 제거, lock 기반 검증 |

---

## 작업별 요약

### 작업 1 — fcntl 파일 락
- `with discovery_lock(collection_id):` 컨텍스트 매니저
- `data/discovery_<collection_id>.lock` (collection별 분리 → 멀티 collection 병렬 가능)
- `LOCK_EX | LOCK_NB`: 잡혀있으면 즉시 `LockedError` (블록 없음)
- 락 파일에 `<hostname>:<pid>` 기록 → 디버깅 용이
- 프로세스 비정상 종료(OS kill)시 fcntl 자동 해제
- `dashboard.py`는 `LockedError → HTTP 409`, CLI는 `stderr + exit 1`

### 작업 2 — heartbeat
- `AgentRun.heartbeat_at`, `AgentRun.locked_by` 컬럼 추가
- discovery 사이클 시작 시 즉시 INSERT (run_id 확보)
- 30s마다 별도 asyncio task가 UPDATE — `HEARTBEAT_INTERVAL_SECONDS` 상수
- 사이클 종료 시 task cancel + 마지막 heartbeat 기록 (정상/예외 모두)
- `agent/status` 엔드포인트에 `heartbeat_at`, `locked_by` 노출 (UI 연결은 Phase F)

### 작업 3 — bootstrap ACID
- `_ensure_collection`, `_ensure_folder`: SELECT → savepoint INSERT → `IntegrityError` 폴백 SELECT
- `Folder` UNIQUE `(parent_id, name)` 의존 — 동시 부트스트랩 시 한 쪽이 IntegrityError를 받고 다른 쪽 row를 복구

### 작업 4 — folder_papers UNIQUE + paper 99 cleanup
- 마이그레이션 003에서:
  1. `agent_runs.heartbeat_at`, `agent_runs.locked_by` 컬럼 추가
  2. `folder_papers` 중복 정리 — `paper_id`별 가장 최근(`fp.id` 최대) 1건만 유지 → paper 99 자동 처리
  3. `(folder_id, paper_id)` 쌍 중복 정리
  4. `folders` 동일 `(parent_id, name)` 중복 정리 (자식 폴더/매핑 재배치 후 삭제)
  5. UNIQUE INDEX 추가:
     - `uq_folder_papers_folder_paper(folder_id, paper_id)`
     - `uq_folders_parent_name(parent_id, name) WHERE parent_id IS NOT NULL`
     - `uq_folders_root_name(name) WHERE parent_id IS NULL`
  6. 적용 직전 `data/backups/papers_pre_003_<ts>.db` 자동 백업
- `discovery.py` 폴더 배치는 **move semantics** — 시스템 폴더 4종 매핑은 INSERT 전 DELETE
  - 사용자 폴더는 보존 (기존 `recalibrate.py` 가정과 일치)

### 작업 5 — Discovery 저장 트랜잭션
- 한 paper의 `Paper` / `PaperCollection` / `FolderPaper` 저장을 `db.begin_nested()` savepoint로 묶음
- 부분 실패 시 그 paper만 롤백 + `report.errors`에 기록 → 사이클 전체는 계속 진행

### 작업 6 — 멀티프로젝트 격리
- collection별 별도 락 파일 — `CF4`와 `CPN0` 동시 진행 가능
- 같은 collection 두 번째 시도는 즉시 `LockedError`

### 작업 7 — 테스트 (10건 추가, 11건 합)
| 파일 | 테스트 | 매핑 |
|---|---|---|
| `test_discovery_lock.py` | `test_concurrent_run_blocked_by_file_lock` | PLAN §A.2 #1 |
| | `test_lock_released_on_exception` | PLAN §A.2 #2 |
| | `test_heartbeat_updated_during_long_run` | PLAN §A.2 #3 |
| | `test_two_collections_run_in_parallel` | v2 #3 |
| | `test_same_collection_blocks_second` | v2 #4 |
| `test_bootstrap_acid.py` | `test_concurrent_collection_creation_idempotent` | PLAN §A.2 #4 |
| `test_discovery_save.py` | `test_partial_failure_rolls_back_paper_collection_folder` | PLAN §A.2 #5 |
| `test_folder_papers_unique.py` | `test_duplicate_paper_in_two_folders_blocked` | v2 #1 |
| | `test_move_semantics_replaces_existing` | v2 #2 |
| `test_migration_003.py` | `test_paper_99_cleaned_up` | v2 #5 |
| `test_dashboard_agent.py` | `test_trigger_agent_run_blocked_when_lock_held` | Phase A #10 갱신 |

```
$ pytest -m "not integration" -q
28 passed, 4 deselected in 0.43s
```
(기존 17 + Phase E 신규 11)

---

## ⚠️ 마이그레이션 003 적용 — 사용자 승인 대기

### 백업
**자동 생성 완료**: `data/backups/papers_pre_003_20260408_165336.db` (2.7 MB)

### 현재 DB 상태 (적용 전)
```
$ sqlite3 data/papers.db
> SELECT paper_id, COUNT(*) FROM folder_papers GROUP BY paper_id HAVING COUNT(*)>1;
(0 rows)                       — 이미 깨끗 (Phase D 작업 잔재로 보임)
> SELECT COUNT(*) FROM folder_papers;
50
> SELECT COUNT(*) FROM folders;
5
```
folder_papers 중복 0건. 마이그레이션 003 cleanup은 no-op으로 끝나고
**컬럼 2개 + 인덱스 4개만 추가**될 예정.

### 적용 명령
```bash
cd /Users/igeonho/paper-research
venv/bin/python backend/migrations/003_phase_e_lock_heartbeat_unique.py
```

### 적용 후 검증
```bash
sqlite3 data/papers.db <<'SQL'
.headers on
PRAGMA table_info(agent_runs);                       -- heartbeat_at/locked_by 존재 확인
SELECT name, sql FROM sqlite_master
  WHERE type='index' AND name LIKE 'uq_%';           -- 4개 index
SELECT paper_id, COUNT(*) c FROM folder_papers
  GROUP BY paper_id HAVING c>1;                       -- 0 rows
SQL
```

### 롤백
```bash
cp data/backups/papers_pre_003_20260408_165336.db data/papers.db
```

---

## 사용자 검증 체크리스트

- [ ] 마이그레이션 003 백업 파일 위치 확인
      → `data/backups/papers_pre_003_20260408_165336.db` (생성 완료)
- [ ] 중복 0건 확인
      → `SELECT paper_id, COUNT(*) FROM folder_papers GROUP BY paper_id HAVING COUNT(*) > 1`
- [ ] 두 collection 동시 recalibrate 시도 → 둘 다 정상
      → `python backend/scripts/recalibrate.py CF4 &` + `python backend/scripts/recalibrate.py CPN0`
- [ ] 같은 collection 두 번째 시도 → 즉시 `LockedError`
- [ ] HTTP `POST /api/dashboard/agent/run` 두 번 → 두 번째 409
- [ ] `kill -9`로 강제 종료 후 `lsof | grep discovery_` 0건 (락 자동 해제)
- [ ] `agent_runs.heartbeat_at` 갱신 SQL 확인
      → `SELECT id, started_at, heartbeat_at, locked_by FROM agent_runs ORDER BY id DESC LIMIT 5`

---

## 금지 사항 준수
- ✅ APScheduler / cron 미도입
- ✅ collection auto-creation 미도입 (bootstrap만 ACID 보강)
- ✅ Phase D 산출물 (`RELEVANCE_SYSTEM`, `recalibrate.py`) 변경 없음
- ✅ 마이그레이션 자동 적용 안 함 — 본 문서로 사용자 승인 요청
- ✅ Phase F 작업 (죽은 API 정리) 미수행
- ✅ 자동으로 다음 Phase 진입 안 함

## 다음 단계 (사용자 결정)
1. 본 문서 검토
2. 마이그레이션 003 실행 명령 수동 트리거 (또는 Claude에게 "003 적용해" 지시)
3. 검증 체크리스트 확인 후 Phase E 종료 / Phase F 진입 결정
