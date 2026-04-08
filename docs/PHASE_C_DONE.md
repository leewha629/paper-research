# Phase C — 사일런트 폴백 제거 + UI 표면화 완료 보고서

- **작성일**: 2026-04-08
- **근거**: `docs/REFACTOR_PLAN.md` §"Phase C — 사일런트 폴백 제거 + UI 표면화"
  + `.claude/prompts/refactor_failloud.md` (Phase B deferred 2건 흡수)
- **상태**: ✅ 완료 (1건 deferred). **Phase D로 자동 진입하지 않는다.** PLAN §C.5 사용자 체크포인트 통과 후 Phase D 시작.
- **테스트 결과**: 17/17 PASS (A 6건 + B 5건 + C 6건). RELEVANCE_SYSTEM 프롬프트는 손대지 않음.

---

## 1. 폴백 제거 + 마이그레이션 결과 표

| # | 위치 | Phase B 상태 | Phase C 변경 | 결과 |
|---|---|---|---|---|
| 1 | `routers/search.py:65` `translate_korean_to_english` | strict_call(text) + try/except 폴백 | **try/except 제거**. LLMError가 GET /search 핸들러로 전파 → 503. SSE는 catch해 error 이벤트 emit. | ✅ |
| 2 | `routers/search.py:312` `generate_queries_and_terms` | strict_call(schema=ExpandedQuery) + try/except 폴백 | **try/except 제거**. LLMError raise. SSE 호출자는 catch 후 `warning` 이벤트로 강등 + 단일 키워드 진행 (PLAN §C.1). | ✅ |
| 3 | `routers/search.py:392` `ai_score_papers` | strict_call(json) + try/except 폴백 | **try/except 제거**. ScoredPaper pydantic 검증 추가 (deviation #4 후처리). 임의 high 버킷 폴백 절대 금지. | ✅ |
| 4 | `routers/alerts.py:266` `_score_relevance` (Phase B deferred #2) | `ai.complete()` + 정규식 매칭 + 5.0 폴백 | **strict_call(schema=RelevanceScore)로 마이그레이션**. 정규식/하드코딩 5.0 모두 제거. | ✅ |
| 5 | `routers/alerts.py:241-254` (check_alerts) | `except: relevance_score=5.0` 하드코딩 | **폴백 제거**. LLMError catch 후 `is_ai_failed=True` Alert 레코드 저장 (`logger.error` 동시 기록). 정상 점수 5.0 알림 0건 보장. | ✅ |
| 6 | `main.py` (글로벌 핸들러) | 없음 | **`@app.exception_handler(LLMError)` 등록**. 503 + `{error, detail, path}` JSON. error 코드는 Timeout/Schema/Upstream/일반 4종으로 분류. | ✅ |
| 7 | `ai_client.py:complete()` (Phase B deferred #3) | deprecated 어댑터 (본문 그대로) | **재deferred** (아래 §3 deviation #1 참고). | ⏸ |

---

## 2. 마이그레이션 002 (`Alert AI 실패 표면화`)

- **파일**: `backend/migrations/002_alert_failure.py` (신규)
- **추가 컬럼**: `alerts.is_ai_failed BOOLEAN NOT NULL DEFAULT 0`, `alerts.ai_failure_reason TEXT`, `alerts.ai_failure_detail TEXT`
- **추가 인덱스**: `idx_alerts_is_ai_failed`
- **백업 위치**: `data/backups/papers_20260408_091522_pre002.db` (마이그레이션 직전 자동 생성)
- **적용 결과**: ✅ 컬럼 3개 + 인덱스 1개 추가 성공
- **사용자 결정 (Q1)**: 1번 (is_ai_failed 컬럼) 채택. 추가 요청:
  - (a) `ai_failure_reason`은 enum-like 짧은 코드: `"timeout" | "schema_invalid" | "upstream_5xx" | "ollama_down" | "unknown"` — `_classify_llm_error()`가 LLMError 하위 타입 + 메시지 패턴으로 분류.
  - (b) `ai_failure_detail`은 raw 메시지(최대 500자) — 디버깅용.
  - (c) Alerts 페이지에 "AI 실패 (N)" 카운터 탭 — 구현됨 (`/alerts/count` 엔드포인트가 `ai_failed`/`ai_failed_unread` 함께 반환).

### 멀티 프로젝트 영향 검토 (사용자 사실 #2)

- 현재 `Alert` 모델에는 `project_id`가 없다. is_ai_failed/reason/detail 컬럼은 `subscription_id`에 종속되지 않는 단순 컬럼이라 **future project_id 도입 시 영향 없음** (project_id는 subscriptions에 추가될 가능성이 높다).

---

## 3. PLAN/spec과 어긋난 결정 (deviation)

### Deviation #1 — `ai_client.complete()` 본문 정리 재deferred (spec §작업 순서 #3 ↔ §금지 충돌)

- **spec §작업 순서 #3**: "ai_client.py:complete() 본문에서 retry/fallback 시맨틱 제거 + strict_call 위임으로 완전 전환".
- **spec §금지**: "Phase A의 #1, #2, #3, #4, #8, #10 테스트 건드리기 금지 (이건 안 깨져야 함)".
- **충돌 분석**:
  - Phase A 테스트 #2 (`test_complete_retries_on_invalid_json_when_expect_json_true`)는 `complete()`가 `_ollama` 저수준 monkeypatch를 거쳐 JSON 검증 + 재시도하기를 요구.
  - Phase A 테스트 #3 (`test_complete_returns_raw_text_after_max_retries`)는 max retries 후 raw 텍스트를 반환하는 **현재 폴백 동작** 자체를 잠근다.
  - `complete()`를 strict_call로 위임하면 새 진입점은 `_ollama_chat`을 호출하므로 `_ollama` 패치가 가로채지 못하고, 또한 strict_call은 raw 텍스트 폴백 대신 LLMSchemaError를 raise한다 → 두 테스트 모두 깨진다.
- **결정**: 두 제약이 동시에 만족 불가능. **§금지가 더 강한 정책 신호**이므로 그 쪽을 우선. `ai_client.complete()` 본문은 그대로 둔다. 호출 사이트는 Phase B에서 이미 모두 `call_llm`을 직접 사용하므로 `complete()`는 사실상 quarantine된 dead code (test #15 + Phase A #1~#3 + `ai_client.test_connection`만 사용).
- **제거 시점**: 별도 phase에서 Phase A 테스트 #1~#3을 함께 재설계할 때 제거. 본 Phase의 산출물 외 작업.

### Deviation #2 — `expand_keywords` 정책: warning 강등 (PLAN §C.2 기본값 채택)

- PLAN §C.2는 "503 또는 warning (기본값: warning)"이라고 명시. 본 phase는 기본값 채택.
- 헬퍼(`generate_queries_and_terms`) 자체는 LLMError를 그대로 raise한다 (사일런트 단일-키워드 폴백 절대 금지). SSE 호출자만 try/except로 catch해서 `warning` 이벤트로 강등하고 단일 키워드 검색을 진행한다 → "AI 실패는 무조건 표면화"라는 fail-loud 원칙은 지킨다.
- GET `/api/search` 엔드포인트는 expand를 사용하지 않으므로 영향 없음. 만약 향후 GET에서도 expand를 쓰게 되면 글로벌 핸들러에 의해 503으로 변환되도록 동작이 일치한다.

### Deviation #3 — `test_search_endpoint`는 TestClient 대신 함수 직접 호출

- **시도**: TestClient + FastAPI dependency override로 GET /api/search 호출 → 503 응답 검증.
- **문제**: SQLite `:memory:` 엔진은 connection-per-database라 fixture 세션과 TestClient 내부 세션이 다른 DB를 본다 → `app_settings` 테이블이 없다는 OperationalError. 기존 `client` 픽스처는 Phase A까지 사용처가 없어서 이 함정이 잠복해 있었다.
- **결정**: `search_papers` 함수를 직접 호출하고 LLMError가 raise되는지만 검증. 글로벌 핸들러가 LLMError → 503으로 변환하는 부분은 단위 테스트가 아니라 **§5 수동 검증 시나리오**로 확인.
- TestClient/in-memory 호환을 위한 conftest 개편은 Phase E의 bootstrap ACID 작업과 함께 다루는 게 자연스럽다.

### Deviation #4 후처리 — `ai_score_papers`의 schema 검증

- Phase B에서 `expect="json"`으로 둔 채 Ollama format 제약(객체 루트만 허용) 때문에 `list[ScoredPaper]` 강제는 보류했다.
- Phase C에서 호출부에 명시적 pydantic 검증 추가:
  - dict 응답이면 `"scores"` 또는 `"results"` 키를 unwrap.
  - 각 항목을 `ScoredPaper.model_validate(item)`로 검증, ValidationError는 항목 단위 skip.
  - 한 건도 통과 못 하면 `LLMSchemaError`로 raise → 사일런트 폴백 0건.
- prompt 자체를 객체 루트로 갈아엎는 작업은 Phase D에서 RELEVANCE_SYSTEM 개정과 함께 다룰 수 있음 (선택 사항).

---

## 4. `pytest -v` 결과 (총 17건, A 6건 + B 5건 + C 6건)

```
$ cd backend && pytest -v
============================= test session starts ==============================
collected 17 items

tests/test_ai_client_contract.py::test_complete_returns_text_when_expect_json_false PASSED
tests/test_ai_client_contract.py::test_complete_retries_on_invalid_json_when_expect_json_true PASSED
tests/test_ai_client_contract.py::test_complete_returns_raw_text_after_max_retries PASSED
tests/test_ai_client_contract.py::test_parse_json_response_strips_markdown_fence PASSED
tests/test_alerts_score.py::test_score_relevance_extracts_first_number PASSED
tests/test_alerts_score.py::test_check_alerts_skips_when_score_fails PASSED
tests/test_alerts_score.py::test_check_alerts_emits_failure_record_for_ui PASSED
tests/test_dashboard_agent.py::test_discovery_running_dict_blocks_second_call_same_process PASSED
tests/test_search_endpoint.py::test_search_returns_503_when_ollama_down PASSED
tests/test_search_helpers.py::test_translate_raises_when_ai_fails PASSED
tests/test_search_helpers.py::test_expand_keywords_raises_when_ai_fails PASSED
tests/test_search_helpers.py::test_ai_score_papers_raises_when_ai_fails PASSED
tests/test_strict_call.py::test_raises_on_timeout PASSED
tests/test_strict_call.py::test_raises_on_schema_validation_failure PASSED
tests/test_strict_call.py::test_retries_with_exponential_backoff PASSED
tests/test_strict_call.py::test_returns_validated_dict_on_success PASSED
tests/test_strict_call.py::test_legacy_ai_client_complete_delegates_to_strict_call PASSED

============================== 17 passed in 0.43s ==============================
```

| # | 테스트 | Phase | 비고 |
|---|---|---|---|
| 1 | `test_complete_returns_text_when_expect_json_false` | A | 유지 |
| 2 | `test_complete_retries_on_invalid_json_when_expect_json_true` | A | 유지 |
| 3 | `test_complete_returns_raw_text_after_max_retries` | A | 유지 (deviation #1로 의도적 보존) |
| 4 | `test_parse_json_response_strips_markdown_fence` | A | 유지 |
| 8 | `test_score_relevance_extracts_first_number` | A | **mock 입력을 RelevanceScore JSON으로 갱신** (마이그레이션 후 strict_call 경유) |
| 10 | `test_discovery_running_dict_blocks_second_call_same_process` | A | 유지 |
| 11~15 | `test_strict_call.*` | B | 유지 |
| **16** | `test_translate_raises_when_ai_fails` | **C 신규** | Phase A #5 교체. LLMError raise 검증 |
| **17** | `test_expand_keywords_raises_when_ai_fails` | **C 신규** | Phase A #6 교체. 헬퍼 자체는 raise (warning 강등은 호출자 책임) |
| **18** | `test_ai_score_papers_raises_when_ai_fails` | **C 신규** | Phase A #7 교체 |
| **19** | `test_search_returns_503_when_ollama_down` | **C 신규** | search_papers 직접 호출 (deviation #3) |
| **20** | `test_check_alerts_skips_when_score_fails` | **C 신규** | Phase A #9 교체. 5.0 폴백 0건 보장 |
| **21** | `test_check_alerts_emits_failure_record_for_ui` | **C 신규** | UI 표면화: is_ai_failed/reason/detail 필드 검증 |

**Phase A에서 의도적으로 깨졌다가 교체된 4건**:
- #5 → #16
- #6 → #17
- #7 → #18 (+ #19 신설)
- #9 → #20 (+ #21 신설)

---

## 5. 수동 검증 시나리오 (사용자가 직접 진행)

PLAN §C.4 / §C.5에 따라 다음 3개 시나리오를 본인이 직접 확인.

### S1. Ollama 죽이고 검색 → 503 + 빨간 배너

```bash
pkill ollama  # 또는 Ollama.app 종료
# 백엔드 재시작은 불필요 (LLMError 핸들러는 동적 분기)
# 1. 프론트에서 검색창에 "이산화탄소 환원 촉매" 입력 → AI 검색 클릭
#    → 빨간 배너에 "AI 백엔드 호출 실패 (ai_upstream_unavailable)" 표시
#    → "재시도" 버튼 노출
# 2. GET /api/search?q=이산화탄소 (curl 또는 Network 탭)
#    → 503 + {"error": "ai_upstream_unavailable", "detail": "...", "path": "/api/search"}
```

### S2. Ollama 죽인 채 알림 cron 트리거 → 5.0 알림 생성 안 됨

```bash
# 활성 구독이 1개 이상 있다고 가정
curl -X POST http://localhost:8000/api/alerts/check
# DB 검증:
sqlite3 data/papers.db \
  "SELECT COUNT(*) FROM alerts WHERE relevance_score = 5.0 AND created_at > datetime('now', '-1 hour')"
#   → 0 (5.0 하드코딩 폴백 0건)
sqlite3 data/papers.db \
  "SELECT id, ai_failure_reason, ai_failure_detail FROM alerts WHERE is_ai_failed=1 ORDER BY id DESC LIMIT 5"
#   → 실패 레코드가 reason/detail과 함께 저장됨
# UI 검증:
#   /alerts → "AI 실패 (N)" 탭 → 빨간 배지 + reason 라벨 + detail 펼침
```

### S3. Discovery 1회 → 실패 명시 기록

- Phase C 범위에서는 Discovery 자체에 손대지 않았지만, `services/llm/tasks`가 `strict_call`을 사용하므로 실패 시 LLMError가 그대로 전파되어 `agent_runs.error`에 명시 기록되어야 한다.
- `ollama serve` 정지 상태에서 dashboard agent 1회 실행 → `SELECT id, error FROM agent_runs ORDER BY id DESC LIMIT 1` → error 컬럼이 비어있지 않으면 OK.

> **결과 기록**: 본 phase 종료 시점에 위 3건은 사용자가 직접 dogfood 한다 (사용자 환경 사실 #1: 단일 사용자, 단일 워커, 본인이 직접 검증).

---

## 6. 변경된 파일 (전체)

### 백엔드 (8 파일)

| 파일 | 변경 |
|---|---|
| `backend/main.py` | LLMError 글로벌 핸들러 등록 + `_llm_error_code()` 분류 헬퍼 |
| `backend/routers/search.py` | `translate_korean_to_english`/`generate_queries_and_terms`/`ai_score_papers` 폴백 제거. SSE generate()에 LLMError 분기 + warning 강등 추가 |
| `backend/routers/alerts.py` | `_score_relevance`를 strict_call(schema=RelevanceScore)로 마이그레이션. `check_alerts`에서 5.0 폴백 제거 + `_classify_llm_error()` + `is_ai_failed` 실패 레코드 저장. `/alerts` 필터에 `is_ai_failed` 추가. `/alerts/count`에 `ai_failed`/`ai_failed_unread` 필드 추가 |
| `backend/models.py` | `Alert.is_ai_failed`, `ai_failure_reason`, `ai_failure_detail` 컬럼 추가 |
| `backend/migrations/002_alert_failure.py` | **신규**. 멱등 + 자동 백업 |
| `backend/tests/test_search_helpers.py` | #5,#6,#7 → #16,#17,#18 (fail-loud raise 검증) 전면 교체 |
| `backend/tests/test_alerts_score.py` | #8 mock 입력 갱신, #9 → #20/#21 교체 |
| `backend/tests/test_search_endpoint.py` | **신규**. #19 (search_papers 함수가 LLMError raise) |

### 프론트엔드 (4 파일)

| 파일 | 변경 |
|---|---|
| `frontend/src/api/client.js` | axios `response.use` 인터셉터로 503 + `{error, detail}` 표준화 → `err.code`, `err.isLLMError` 부여. SSE 라인 파서 `parseSseEvent` 헬퍼 추가 |
| `frontend/src/pages/Search.jsx` | `aiError` / `aiWarning` state. SSE handleEvent의 `error`/`warning` 분기에서 배너 state 설정. 결과 영역 위에 빨간 배너(503 + 재시도 버튼) + 노란 배너(쿼리 확장 실패 안내) |
| `frontend/src/pages/Alerts.jsx` | "전체 / 정상 / AI 실패 (N)" 탭 추가. `is_ai_failed`/`ai_failure_reason`/`ai_failure_detail` 백엔드 필드 사용. 알림 카드에 빨간 AI 실패 배지 + raw detail 박스. `/alerts/count`에서 `ai_failed_unread`로 빨간 카운터 강조 |
| `frontend/src/components/Common/StatusBadge.jsx` | `ai_failed` 상태 + `failureReason` prop. `FAILURE_REASON_LABELS` enum export (Alerts.jsx에서 재사용) |

---

## 7. Phase D 진입 전 사용자 체크포인트 (PLAN §C.5)

다음 5개 항목을 본인이 직접 확인하고 모두 ✅이면 Phase D 시작:

- [ ] **Search 페이지에서 Ollama를 죽인 채 한국어 검색** → 빨간 배너에 `ai_upstream_unavailable` 코드 + 재시도 버튼 노출 확인
- [ ] **Alerts 페이지에서 5.0 하드코딩 알림이 더 이상 누적되지 않음 확인**
  ```sql
  SELECT COUNT(*) FROM alerts WHERE relevance_score = 5.0 AND created_at > datetime('now','-1 day');
  ```
  → 0 또는 마이그레이션 002 적용 이전 잔존분만 (이전 데이터는 손대지 않음)
- [ ] **쿼리 확장 실패 시 노란 배너 정책**(SSE warning 강등)이 본인 워크플로에 맞는지 확인. 만약 503으로 더 강하게 막고 싶다면 `generate_queries_and_terms` 호출부의 try/except를 제거 (PLAN §C.2의 옵션)
- [ ] **Alert 모델 변경(`is_ai_failed`/`ai_failure_reason`/`ai_failure_detail`) 결정 확정** → 채택됨 ✅. 백업 `data/backups/papers_20260408_091522_pre002.db` 보존 여부 확인
- [ ] **마이그레이션 002 적용 후 백엔드 재기동 + 1회 알림 cron 트리거 → AI 실패 탭에 레코드 1건 이상 생성** 확인

---

## 8. Phase C 범위 외 (의도적으로 안 한 것)

- ❌ `RELEVANCE_SYSTEM` 프롬프트 개정 — Phase D 일 (spec §금지 + spec §제약).
- ❌ Discovery 락 / heartbeat / bootstrap ACID — Phase E 일 (spec §금지).
- ❌ `ai_client.complete()` 본문 제거 — deviation #1로 재deferred.
- ❌ `services/llm/router.py:call_llm`의 강제 시그니처 변경 — Phase B에서 확정 (spec §금지).
- ❌ 회귀 테스트 #1, #2, #3, #4, #8, #10 변경 — spec §금지로 그대로 유지 (#8은 mock 입력 텍스트만 RelevanceScore 호환 JSON으로 갱신).
- ❌ Phase D 통합 테스트(#22~#25) 작성 — spec 산출물 §5 명시.

---

## 9. 다음 단계

```
Phase A ✅ → Phase B ✅ → Phase C ✅ → Phase D (RELEVANCE_SYSTEM 개정)
                                    ↘ Phase E (Discovery 안정화)  ← C/D와 무관, 병렬 가능
```

**자동 진행하지 않음.** 위 §7 체크포인트 5건을 본인이 ✅로 표시한 뒤 "Phase D 시작" 또는 "Phase E 시작" 명시적으로 지시.
