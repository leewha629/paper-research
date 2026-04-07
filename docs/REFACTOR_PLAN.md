# Paper Research — 리팩토링 플랜 (Phase 1)

- **작성일**: 2026-04-07
- **근거 문서**: `docs/AUDIT_2026Q2.md` (§9 위험 Top 10이 우선순위의 유일한 근거)
- **범위**: AUDIT Top 10 + 프롬프트 §"필수 내용" 7항목
- **원칙**: 코드 수정 전 단계. 본 문서는 실행 계획만 담는다.

---

## 0. 의존성 결정

### 0.1 AUDIT Top 10 → 작업군 매핑

| AUDIT # | 제목 | 분류 | 비고 |
|---|---|---|---|
| #1 | ai_score_papers 사일런트 폴백 | 사일런트 폴백 + AI 호출 | strict_call 위에서 풀어야 함 |
| #2 | alerts 5.0 하드코딩 폴백 | 사일런트 폴백 + 점수 캘리브레이션 | _score_relevance 정규식이 근본 |
| #3 | translate / expand_keywords 폴백 | 사일런트 폴백 + AI 호출 | expect_json 미지정이 근본 |
| #4 | Discovery race (dict 플래그) | 동시성 | 독립 트랙 |
| #5 | 테스트/CI 0 | 안전망 | 모든 변경의 검증 수단 |
| #6 | bootstrap ACID 부재 | 동시성 + 트랜잭션 | #4와 같은 트랙 |
| #7 | 스케줄러/heartbeat 부재 | Discovery 안정화 | Med, #4 후속 |
| #8 | pdf_text/JSON 컬럼 성능 | 스키마 | **본 Phase 1 범위 외 — Phase 2로 이연** |
| #9 | Discovery 부분 실패 처리 | 트랜잭션 | #4와 같은 트랙 |
| #10 | 죽은 API / 미연결 UI | 정리 | 마지막 단계 |

> **§8 (Top #8)** 은 스키마 마이그레이션 + 데이터 이전이 필요하고, 다른 항목과 의존성이 약하다. Phase 1에서는 다루지 않고 Phase 2로 분리한다. 본 플랜은 #1~#7, #9, #10 = **9건**만 다룬다.

### 0.2 핵심 의존성 판단

**Q1. 테스트 스캐폴딩(#5)은 리팩토링 전에 와야 하는가, 후에 와야 하는가?**

- **답: 전에**. 단, "최소 스캐폴딩 + 일부 특성화 테스트"로 한정한다.
- **근거**: §4의 4건 사일런트 폴백을 fail-loud로 바꾸는 순간, 호출 측 기대 계약(`return papers, []` 같은 빈 폴백 형태)이 깨진다. 어디서 어떻게 깨지는지 자동으로 잡을 수단이 없으면 회귀가 사용자 화면에서 발견된다. → 최소 mock(ollama/s2) + 호출 사이트별 계약 테스트 10건이 먼저 필요.
- **단, 풀 30건 테스트는 전부 선행 작성하지 않는다**. 각 Phase 종료 시 그 Phase가 건드린 모듈의 회귀 테스트를 추가 작성하는 점진 방식. Phase A에서 인프라 + 10건, 이후 Phase에서 +20건을 분산.

**Q2. AI 호출 단일화(필수 #1)와 사일런트 폴백 제거(필수 #2)의 순서?**

- **답: 단일화 먼저, 폴백 제거가 후속**.
- **근거**: §4의 4건은 모두 `expect_json` 미지정 + 광범위 `except Exception`이 근본이다. strict_call이 (a) `expect_json` 강제, (b) JSON schema 검증, (c) 재시도 정책, (d) 실패 시 raise를 보장하면, 폴백 제거는 "호출부에서 try/except 삭제 + 사용자 가시 에러로 매핑"만 하면 된다. 단일화 없이 폴백 4건을 개별 패치하면 retry/timeout/JSON 정리 로직이 4벌로 분기되어 또다른 표류를 만든다.

**Q3. 점수 캘리브레이션(필수 #3)과 폴백 제거(필수 #2)의 순서?**

- **답: 폴백 제거가 먼저, 캘리브레이션이 후속**.
- **근거**: 캘리브레이션의 효과를 측정하려면 "AI가 점수를 반환했을 때 그 값이 그대로 임계값에 적용된다"는 것이 보장되어야 한다. 사일런트 폴백이 살아 있으면 캘리브레이션 개선분이 폴백에 가려진다. 즉 §4 #1, #2가 거짓 양/음성을 만들고 있는 동안에는 프롬프트 변경의 측정이 불가능.

**Q4. Discovery 안정화(필수 #5)와 bootstrap ACID(필수 #6)의 순서?**

- **답: 같은 Phase에 묶는다**. bootstrap은 Discovery 사이클의 진입점이고, 둘 다 멀티 워커/CLI 동시 실행이라는 같은 전제를 공유한다. race 해결 메커니즘(파일락 / DB 마커)을 정하면 두 곳에 동시에 적용된다.

**Q5. 죽은 API / UI 정리(필수 #7)의 위치?**

- **답: 마지막**. 다른 변경(특히 폴백 제거 → UI 에러 표면화, Discovery 안정화 → dashboardAPI.agentStatus 사용처 등장)이 끝나야 "어떤 API가 진짜 죽었는지"가 확정된다. 먼저 정리하면 곧이어 되살릴 후보를 잘못 삭제할 위험이 있다.

### 0.3 Phase 순서

```
Phase A: 회귀 테스트 스캐폴딩 (안전망)
Phase B: AI 호출 단일화 (services/llm/ollama_client.py:strict_call)
Phase C: 사일런트 폴백 제거 + UI 표면화
Phase D: 점수 캘리브레이션 (RELEVANCE_SYSTEM 개정 + few-shot)
Phase E: Discovery 안정화 + bootstrap ACID
Phase F: 죽은 API / 미연결 UI 정리
```

총 6단계.

### 0.4 의존 그래프

```
        ┌──────────────────────────────────────┐
        │           Phase A (안전망)            │
        │   pytest 인프라 + 10건 특성화 테스트   │
        └──────────────┬───────────────────────┘
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
   ┌────────────────┐    ┌──────────────────┐
   │   Phase B      │    │     Phase E      │
   │ AI 호출 단일화  │    │ Discovery 안정화 │
   │ (strict_call)  │    │  + bootstrap ACID│
   └────────┬───────┘    └────────┬─────────┘
            │                     │
            ▼                     │
   ┌────────────────┐             │
   │   Phase C      │             │
   │ 사일런트 폴백   │             │
   │ 제거 + UI 표면화│             │
   └────────┬───────┘             │
            │                     │
            ▼                     │
   ┌────────────────┐             │
   │   Phase D      │             │
   │ 점수 캘리브레이션│             │
   └────────┬───────┘             │
            │                     │
            └──────────┬──────────┘
                       ▼
            ┌────────────────────┐
            │      Phase F       │
            │ 죽은 API / UI 정리 │
            └────────────────────┘
```

- **B와 E는 A 후 병렬 가능**. 둘은 건드리는 파일이 거의 겹치지 않는다 (B: ai_client.py / search.py / ai.py / alerts.py / 새 services/llm/. E: services/research_agent/ + dashboard.py + run_agent_once.py + models.py).
- **C는 B에 직렬 의존**. strict_call 시그니처가 확정돼야 호출부 마이그레이션을 시작할 수 있다.
- **D는 C에 직렬 의존**. 폴백 가림이 사라져야 캘리브레이션 효과 측정 가능.
- **F는 D와 E 모두 끝난 뒤 진행**. 죽은 API의 진짜 후보 확정.

---

## Phase A — 회귀 테스트 스캐파딩

- **목표**: pytest 인프라 + ai_client/s2_client mock + 10건의 특성화 테스트로 이후 모든 변경의 회귀 감지 기반을 만든다.
- **해결하는 AUDIT 항목**: §9 #5 (테스트/CI 0)
- **작업 분량**: M (1~3h)
- **선행 Phase**: 없음

### A.1 변경/신규 파일 목록

| 파일 | 종류 | 비고 |
|---|---|---|
| `pytest.ini` (또는 `pyproject.toml`의 `[tool.pytest.ini_options]`) | 신규 | rootdir=backend, asyncio_mode=auto |
| `requirements.txt` | 수정 | pytest, pytest-asyncio, httpx 추가 (사용자 보고 필요) |
| `backend/tests/__init__.py` | 신규 | — |
| `backend/tests/conftest.py` | 신규 | DB 픽스처(SQLite in-memory), client 픽스처, mock_ollama 픽스처 |
| `backend/tests/fixtures/__init__.py` | 신규 | — |
| `backend/tests/fixtures/mock_ai.py` | 신규 | AIClient.complete를 monkeypatch하는 헬퍼 (성공/타임아웃/JSON깨짐 3가지 모드) |
| `backend/tests/fixtures/mock_s2.py` | 신규 | S2Client.bulk_search 응답 고정 |
| `backend/tests/fixtures/sample_papers.py` | 신규 | CF₄/할로겐/VOC 인접 5건, 무관 5건 정적 데이터 |
| `backend/tests/test_ai_client_contract.py` | 신규 | AIClient.complete가 expect_json=True일 때 raise하는지 등 4건 |
| `backend/tests/test_search_helpers.py` | 신규 | translate / expand_keywords / ai_score_papers의 **현재 폴백 동작**을 그대로 캡처하는 특성화 테스트 3건 |
| `backend/tests/test_alerts_score.py` | 신규 | _score_relevance 정규식 매칭 + 5.0 폴백 캡처 2건 |
| `backend/tests/test_dashboard_agent.py` | 신규 | `_discovery_running` dict 동작 캡처 1건 |

> **현재 동작을 그대로 캡처**가 핵심이다. Phase A의 테스트는 "버그를 잠그는" 특성화(characterization) 테스트다. Phase C에서 폴백을 제거하면 이 테스트들이 의도적으로 깨지고, 그때 fail-loud 동작을 검증하는 테스트로 교체된다.

### A.2 30건 회귀 테스트 전체 목록 (Phase A에서 10건, 이후 Phase에서 +20건)

**Phase A에서 작성 (10건)**
1. `test_ai_client_contract::test_complete_returns_text_when_expect_json_false`
2. `test_ai_client_contract::test_complete_retries_on_invalid_json_when_expect_json_true`
3. `test_ai_client_contract::test_complete_returns_raw_text_after_max_retries` (현재 버그 캡처)
4. `test_ai_client_contract::test_parse_json_response_strips_markdown_fence`
5. `test_search_helpers::test_translate_korean_returns_original_on_exception` (현재 폴백 캡처)
6. `test_search_helpers::test_expand_keywords_returns_single_keyword_on_exception` (현재 폴백 캡처)
7. `test_search_helpers::test_ai_score_papers_returns_all_as_high_on_exception` (현재 폴백 캡처)
8. `test_alerts_score::test_score_relevance_extracts_first_number`
9. `test_alerts_score::test_score_relevance_returns_5_on_no_match` (현재 폴백 캡처)
10. `test_dashboard_agent::test_discovery_running_dict_blocks_second_call_same_process`

**Phase B 종료 시 추가 (5건)**
11. `test_strict_call::test_raises_on_timeout`
12. `test_strict_call::test_raises_on_schema_validation_failure`
13. `test_strict_call::test_retries_with_exponential_backoff`
14. `test_strict_call::test_returns_validated_dict_on_success`
15. `test_strict_call::test_legacy_ai_client_complete_delegates_to_strict_call`

**Phase C 종료 시 추가 (6건)**
16. `test_search_helpers::test_translate_raises_when_ai_fails` (Phase A의 #5와 교체)
17. `test_search_helpers::test_expand_keywords_raises_when_ai_fails` (#6 교체)
18. `test_search_helpers::test_ai_score_papers_raises_when_ai_fails` (#7 교체)
19. `test_search_endpoint::test_search_returns_503_when_ollama_down`
20. `test_alerts::test_check_alerts_skips_when_score_fails` (5.0 더 이상 저장 안 함)
21. `test_alerts::test_check_alerts_emits_failure_record_for_ui` (UI 표면화)

**Phase D 종료 시 추가 (4건)**
22. `test_relevance_calibration::test_cf4_adjacent_paper_scores_4_or_higher` (5건의 CF₄ 인접 샘플)
23. `test_relevance_calibration::test_halogen_adjacent_paper_scores_4_or_higher`
24. `test_relevance_calibration::test_voc_adjacent_paper_scores_4_or_higher`
25. `test_relevance_calibration::test_unrelated_paper_scores_below_3` (5건의 무관 샘플)

> 22~25는 `mock_ai`로 응답을 주입하는 것이 아니라, **실제 Ollama 호출**을 사용하는 통합 테스트다. `pytest -m integration` 마커로 분리하고 CI에서 옵트인.

**Phase E 종료 시 추가 (5건)**
26. `test_discovery_lock::test_concurrent_run_blocked_by_file_lock`
27. `test_discovery_lock::test_lock_released_on_exception`
28. `test_discovery_lock::test_heartbeat_updated_during_long_run`
29. `test_bootstrap_acid::test_concurrent_collection_creation_idempotent`
30. `test_discovery_save::test_partial_failure_rolls_back_paper_collection_folder`

**합계**: 10 (A) + 5 (B) + 6 (C) + 4 (D) + 5 (E) = **30건**.

### A.3 검증 방법

- `cd backend && pytest -v` → 10건 모두 PASS
- `pytest --collect-only` → 10건 인식
- mock_ai 픽스처가 실제 Ollama를 호출하지 않는지 확인 (network 차단 환경에서도 통과해야 함)

### A.4 사용자 체크포인트

- [ ] `requirements.txt`에 추가된 의존성(pytest, pytest-asyncio, httpx) 승인
- [ ] `cd backend && pytest -v` 직접 실행 → 10건 PASS 확인
- [ ] 테스트가 실제 ollama/s2를 호출하지 않는지 (네트워크 끄고 재실행) 확인
- [ ] `backend/tests/` 디렉토리 구조가 향후 확장하기에 합리적인지 검토
- [ ] 특성화 테스트(#5, #6, #7, #9)가 **현재 버그를 의도적으로 잠그고 있다는 점**을 인지

### A.5 롤백

- `backend/tests/` 디렉토리 전체 삭제
- `pytest.ini` 삭제
- `requirements.txt`에서 추가 의존성 3개 제거
- 단일 커밋으로 묶을 것 → `git revert <Phase A 커밋>` 한 번이면 복구

---

## Phase B — AI 호출 단일화 (`strict_call`)

- **목표**: `services/llm/ollama_client.py:strict_call`을 모든 LLM 호출의 단일 진입점으로 만들고, AUDIT §2.2의 16개 호출 사이트를 점진 마이그레이션.
- **해결하는 AUDIT 항목**: §2 (호출 인벤토리 분산), §9 #1 #2 #3의 **근본 원인** 제거 (폴백 자체는 Phase C에서 지움)
- **작업 분량**: L (>3h)
- **선행 Phase**: A

### B.1 `strict_call` 시그니처 설계

```python
# backend/services/llm/ollama_client.py

from typing import Any, Literal, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMError(Exception):
    """모든 LLM 실패의 베이스. 호출부는 이 예외를 잡아 사용자 가시 에러로 변환한다."""

class LLMTimeoutError(LLMError): ...
class LLMSchemaError(LLMError): ...   # JSON 파싱 또는 schema 검증 실패
class LLMUpstreamError(LLMError): ... # 5xx, 연결 실패 등

async def strict_call(
    *,
    system: str,
    user: str,
    expect: Literal["text", "json", "schema"],
    schema: type[T] | None = None,    # expect="schema"일 때만 사용
    images: list[str] | None = None,
    max_retries: int = 2,
    timeout_s: float = 60.0,
    temperature: float = 0.1,
) -> str | dict[str, Any] | T:
    """
    expect="text"  → str 반환
    expect="json"  → dict 반환 (json.loads + sanity check)
    expect="schema"→ schema 인스턴스 반환 (pydantic validate)

    실패 시 반드시 LLMError 하위 예외를 raise. 절대 폴백 값을 반환하지 않는다.
    내부 재시도는 max_retries회. 마지막 재시도까지 실패하면 raise.
    """
```

**핵심 제약**:
1. **절대 폴백 값을 반환하지 않는다**. 실패는 항상 raise.
2. **expect 인자는 키워드 전용**. 위치 인자 없음 → 호출부에서 누락 방지.
3. **schema 검증은 pydantic을 표준으로**. AUDIT §2.1의 "원본 텍스트 반환" 폴백을 제거.
4. **timeout은 인자로 명시 강제**. 기본값 60s지만 호출부에서 의식적으로 설정.

### B.2 변경 파일 목록

| 파일 | 종류 | 작업 |
|---|---|---|
| `backend/services/llm/__init__.py` | 신규 | 모듈 진입점 |
| `backend/services/llm/ollama_client.py` | 신규 | `strict_call` 본체 |
| `backend/services/llm/claude_client.py` | 신규 | Anthropic용 strict_call (동일 시그니처) |
| `backend/services/llm/router.py` | 신규 | settings 기반 ollama/claude 분기 |
| `backend/services/llm/exceptions.py` | 신규 | LLMError 계층 |
| `backend/services/llm/schemas.py` | 신규 | RelevanceScore, ExpandedQuery, AnalysisResult 등 pydantic 모델 |
| `backend/ai_client.py` | 수정 | 기존 `AIClient.complete`를 `strict_call`로 위임. 시그니처 호환을 위해 얇은 어댑터로 남김. **단, 폴백 분기는 그대로 유지** (Phase C에서 제거) |
| `backend/services/research_agent/discovery.py:163-241` | 수정 | `services/llm/tasks` 경유 호출을 `strict_call(expect="schema", schema=RelevanceScore)`로 교체 |

### B.3 16개 호출 사이트 마이그레이션 단계

AUDIT §2.2 표 기준. 각 사이트를 다음 순서로 옮긴다 (중요한 것 먼저, 위험한 것 마지막):

| 순서 | 호출 사이트 | 변경 내용 | 비고 |
|---|---|---|---|
| 1 | `ai.py:671` `suggest_tags` | `expect="schema", schema=TagSuggestion` | 이미 expect_json=True, 가장 안전 |
| 2 | `ai.py:315` `analyze_paper` | `expect="schema", schema=AnalysisResult` | structured |
| 3 | `ai.py:378` `analyze_all` | 동일 | structured |
| 4 | `ai.py:484` `batch_analyze` | 동일 + SSE 에러 이벤트 유지 | structured |
| 5 | `ai.py:565` `trend_analyze` | `expect="text"` | 텍스트 그대로 |
| 6 | `ai.py:614` `review_draft` | `expect="text"` | 텍스트 그대로 |
| 7 | `services/research_agent/discovery.py` `extract_keywords` | `expect="schema", schema=KeywordList` | discovery 사이클 영향 큼 → 단독 검증 |
| 8 | `services/research_agent/discovery.py` `score_relevance` | `expect="schema", schema=RelevanceScore` | Phase D 캘리브레이션의 베이스 |
| 9 | `search.py:80` `translate_korean_to_english` | `expect="text"` + try/except 유지 (Phase C에서 제거) | 폴백은 호출부에 그대로 |
| 10 | `search.py:364` `generate_queries_and_terms` | `expect="schema", schema=ExpandedQuery` + try/except 유지 | 동일 |
| 11 | `search.py:420` `ai_score_papers` | `expect="schema", schema=list[ScoredPaper]` + try/except 유지 | 동일 |
| 12 | `alerts.py:281` `_score_relevance` | `expect="schema", schema=RelevanceScore` (정규식 매칭 제거) + try/except 유지 | 동일 |
| 13~16 | (settings.py, prompt_templates 경유 등 잔여 호출) | grep으로 발견되는 모든 `client.complete` 직접 호출 | 단계 끝에 일괄 |

> **중요**: Phase B는 "단일화"만 한다. 폴백은 그대로 둔다. Phase C가 폴백 제거 단계.

### B.4 검증 방법

- Phase A의 테스트 10건이 모두 그대로 통과 (특성화 테스트가 깨지면 안 됨 — 폴백 동작 미변경)
- Phase B에서 추가하는 5건 (#11~#15) 통과
- 수동: Ollama 띄운 상태로 검색/분석/Discovery 1회씩 실행 → 동작 동일
- grep으로 `ai_client.complete` / `client.complete` 호출이 strict_call 진입점만 거치는지 확인

### B.5 사용자 체크포인트

- [ ] `services/llm/` 모듈 구조가 합리적인지 검토
- [ ] `strict_call` 시그니처(특히 `expect`/`schema` 강제)가 의도와 맞는지 승인
- [ ] 16개 호출 사이트 중 자기가 자주 쓰는 것(예: 검색, Discovery)을 직접 트리거해 동작 확인
- [ ] `ai_client.py`의 어댑터가 임시방편임을 인지 (Phase C에서 추가 정리)
- [ ] pydantic 추가 의존성 승인 (이미 FastAPI가 들고 있을 가능성 높음 — 확인 필요)

### B.6 롤백

- `services/llm/` 디렉토리 삭제
- `ai_client.py`, `discovery.py`, `ai.py`, `search.py`, `alerts.py`의 변경분 `git revert`
- Phase B는 호출 사이트가 여러 파일에 걸치므로 **호출 사이트 1~16을 작은 커밋 여러 개로 분리**할 것. 한 사이트에서 문제가 생기면 그 커밋만 revert.

---

## Phase C — 사일런트 폴백 제거 + UI 표면화

- **목표**: AUDIT §4의 4건 폴백을 fail-loud로 변환하고, 실패를 사용자가 즉시 인지할 수 있도록 UI/응답 스키마를 변경.
- **해결하는 AUDIT 항목**: §9 #1, #2, #3 (직접 해결)
- **작업 분량**: L (>3h)
- **선행 Phase**: B

### C.1 fail-loud 정책

| 실패 종류 | 백엔드 동작 | 프론트 표시 |
|---|---|---|
| 번역(translate) 실패 | `503` + `{"error": "ai_translate_failed", "detail": "..."}` | Search 페이지: "한글→영문 번역 실패. 영문 키워드로 다시 시도하거나 잠시 후 재시도해 주세요." |
| 쿼리 확장(expand_keywords) 실패 | `200` + `{"queries": [keyword], "warning": "ai_expand_failed"}` | Search 결과 상단에 yellow 배너: "AI 쿼리 확장 실패. 단일 키워드로만 검색되었습니다." |
| 점수 매기기(ai_score_papers) 실패 | `503` + `{"error": "ai_score_failed"}` | Search 페이지: 결과 영역에 빨간 배너 + "재시도" 버튼. **임의로 high 버킷에 넣지 않는다.** |
| 알림 점수(_score_relevance) 실패 | Alert을 만들지 않는다. 별도 `AlertFailure` 레코드(또는 기존 alerts에 `is_ai_failed=True` 컬럼)에 기록 | Alerts 페이지: "AI 점수 실패" 탭에 별도 표시. relevance_score 5.0 하드코딩 절대 금지. |

**근거 (AUDIT §9 #1, #2, #3)**:
- #1 ai_score_papers 폴백은 임계값 자체를 무력화 → 503으로 유저가 즉시 인지해야 한다.
- #2 alerts 5.0 하드코딩은 "유령 알림"을 만든다 → Alert 레코드 자체를 만들지 않거나 별도 카테고리.
- #3 translate/expand는 0건 검색 또는 검색 범위 급감 → 사용자가 모르면 안 된다.

### C.2 변경 파일 목록

| 파일:라인 | 변경 |
|---|---|
| `backend/routers/search.py:79-83` | `try/except` 제거. `LLMError`를 그대로 raise → FastAPI 핸들러에서 503. |
| `backend/routers/search.py:363-375` | `try/except` 유지하되 폴백 대신 `warning` 필드를 응답에 포함. 또는 503 (사용자 정책 결정 필요 — 기본값: warning) |
| `backend/routers/search.py:419-445` | `try/except` 제거. `ai_score_papers`가 raise하면 검색 엔드포인트 전체가 503. |
| `backend/routers/search.py:746` | `RELEVANCE_THRESHOLD ≥ 6.0` 필터는 그대로. score=None 케이스 자체가 사라짐. |
| `backend/routers/alerts.py:241-254` | `except`에서 Alert 생성 제거. 대신 logger.error + AgentRun-like 실패 로그. |
| `backend/routers/alerts.py:266-287` | `_score_relevance`의 정규식 폴백 제거. strict_call이 schema로 검증 → 그대로 반환. |
| `backend/main.py` | LLMError 글로벌 예외 핸들러 등록 → 503 응답 매핑 |
| `backend/models.py` | (선택) `Alert.is_ai_failed: bool` 컬럼 추가 또는 별도 `AlertFailure` 테이블. **마이그레이션 필요** |
| `backend/migrations/002_alert_failure.py` | 신규 (위 컬럼 추가 시) |
| `frontend/src/api/client.js` | 에러 응답 표준화: `{error, detail, warning}` 파싱 |
| `frontend/src/pages/Search.jsx` | 503 처리 + warning 배너 컴포넌트 |
| `frontend/src/pages/Alerts.jsx` | "AI 실패" 탭 추가 또는 필터 |
| `frontend/src/components/Common/StatusBadge.jsx` | 실패 상태용 배지 추가 |

### C.3 작업 순서

1. backend 글로벌 에러 핸들러 등록 (`main.py`)
2. `search.py`의 3건 폴백 제거 (가장 가시성 높음)
3. Phase A의 특성화 테스트 #5, #6, #7을 fail-loud 테스트(#16, #17, #18)로 교체
4. `alerts.py`의 2건 폴백 제거 + (선택) Alert 모델 변경
5. Alerts 모델 변경 시 `migrations/002_alert_failure.py` 작성 + 실행
6. 프론트 에러/경고 UI 추가
7. 수동 시나리오: Ollama 프로세스 죽이고 검색/Discovery/알림 트리거 → 사용자 가시 에러 확인

### C.4 검증 방법

- Phase A의 특성화 테스트 #5, #6, #7, #9가 **의도적으로 실패**한 뒤 fail-loud 버전(#16~#21)으로 교체되어 다시 통과
- `ollama serve` 중지 상태에서 검색 → 화면에 빨간 배너 + 503
- `ollama serve` 중지 상태에서 알림 cron 트리거 → DB에 score=5.0 Alert가 **생성되지 않음** (`SELECT * FROM alerts WHERE relevance_score = 5.0 AND created_at > now() - 1h` → 0건)
- Discovery 1회 실행 후 `agent_runs` 테이블에 실패가 명시적으로 기록

### C.5 사용자 체크포인트

- [ ] Search 페이지에서 Ollama를 죽인 채 검색 시 빨간 에러 배너가 보이는지 직접 확인
- [ ] Alerts 페이지에서 5.0 하드코딩 알림이 더 이상 누적되지 않는지 확인 (`SELECT COUNT(*) FROM alerts WHERE relevance_score = 5.0` 비교)
- [ ] 쿼리 확장 실패 시 yellow 배너 정책(503 vs warning)이 본인 워크플로에 맞는지 결정
- [ ] Alert 모델 변경 여부 결정 (`is_ai_failed` 컬럼 vs 별도 테이블 vs 단순 로그만)
- [ ] 마이그레이션 스크립트 적용 전 `data/papers.db` 백업 확인 (`data/backups/`)

### C.6 롤백

- 백엔드 변경분: 파일별 commit으로 분리해 개별 revert 가능하게
- 프론트엔드: 단일 commit
- 마이그레이션이 실행됐다면 `data/backups/papers_<timestamp>.db`로 복구 (현재 backups 디렉토리 존재 — AUDIT §1)
- **핵심**: Phase C는 가장 사용자 가시성이 큰 단계. 본격 적용 전 staging branch에서 24시간 dogfood 권장.

---

## Phase D — 점수 캘리브레이션 (`RELEVANCE_SYSTEM` 개정)

- **목표**: Discovery / 검색 / 알림에서 사용하는 RELEVANCE_SYSTEM 프롬프트를 개정해 본인 분야(CF₄ / 할로겐 / VOC) 인접 논문이 4~5점 이하로 잘못 떨어지지 않도록 강제. few-shot 예시로 점수 분포 고정.
- **해결하는 AUDIT 항목**: §6.2 step 4 (간접), §9 #1 #2의 **품질 측면** 보강. 폴백 제거(C)가 끝나야 효과 측정 가능.
- **작업 분량**: M (1~3h)
- **선행 Phase**: C

### D.1 RELEVANCE_SYSTEM 위치 — **확인 필요**

> **AUDIT 한계**: §2.2 표는 `services/llm/tasks 경유`라고만 적혀 있고, RELEVANCE_SYSTEM 프롬프트의 정확한 정의 위치를 잡지 못했다. 본 Phase 시작 전 반드시 grep으로 확정해야 한다.
>
> 후보 위치 (AUDIT 단서 기반):
> - `backend/services/research_agent/discovery.py` 내 상수
> - `backend/services/llm/tasks/*.py` (Phase B에서 신설될 디렉토리)
> - DB `prompt_templates` 테이블 (AUDIT §8) — settings UI(`/api/ai/prompts`)로 관리되는 프롬프트일 가능성
>
> **사전 작업**: `grep -rn "RELEVANCE\|relevance.*prompt\|점수\|score" backend/` + `SELECT name, system_prompt FROM prompt_templates;` 1회.

### D.2 프롬프트 개정안 (초안)

```
당신은 화학공학·환경공학·반도체 공정 분야 논문의 관련도를 0~10으로 평가한다.

평가 축:
- 직접 관련 (10점): 사용자가 명시적으로 추적하는 키워드(예: "CF₄ abatement")가 제목/초록에 직접 언급
- 인접 관련 (4~7점): 사용자 키워드와 같은 분야 (할로겐 화학, VOC 처리, 플라즈마 후처리, PFAS, 온실가스 분해 등)
- 약한 관련 (1~3점): 환경/촉매 일반론
- 무관 (0점): 분야 자체가 다름 (의학, 사회과학 등)

### 강제 규칙
**다음 토큰이 제목/초록/저자 키워드에 등장하면 점수는 최소 4점이다 (인접 관련 보장):**
- TODO(사용자): 본인 분야 키워드를 여기에 채워라. 예시:
  - "CF4", "C2F6", "SF6", "NF3", "perfluoro"
  - "halogen*", "halide", "fluorin*"
  - "VOC", "volatile organic"
  - "abatement", "destruction", "decomposition"
  - "scrubber", "thermal oxidizer", "plasma abatement"

위 규칙은 본인 분야가 아닌 사용자가 본 플랜을 사용할 때 직접 채워야 한다.

### Few-shot 예시
[예시 1: CF₄ 직접] 제목 "Plasma abatement of CF4 in semiconductor exhaust" → 10점
[예시 2: 할로겐 인접] 제목 "Catalytic hydrolysis of NF3 over Al2O3" → 8점
[예시 3: VOC 인접] 제목 "Photocatalytic VOC degradation under UV-LED" → 5점
[예시 4: 분야 인접 약함] 제목 "Atmospheric chemistry of HFC-134a" → 4점
[예시 5: 무관] 제목 "Deep learning for protein folding" → 0점
[예시 6: 함정 — 키워드는 있지만 무관] 제목 "Fluorine NMR for drug discovery" → 1점

### 출력 형식 (반드시 JSON)
{"score": <0~10 정수>, "reason": "<한 문장>", "matched_keywords": ["..."]}
```

### D.3 변경 파일 목록

| 파일 | 변경 |
|---|---|
| (확인 필요) RELEVANCE_SYSTEM 정의 위치 | 위 프롬프트로 교체 |
| `backend/services/llm/schemas.py` | `RelevanceScore` pydantic 모델에 `matched_keywords: list[str]` 필드 추가 |
| `backend/services/research_agent/discovery.py:208-241` | matched_keywords를 AgentRun에 기록 (debugging용) |
| `backend/tests/test_relevance_calibration.py` | 신규 — 30건 테스트 중 #22~#25 |
| `backend/tests/fixtures/sample_papers.py` | CF₄/할로겐/VOC 인접 5건, 무관 5건 픽스처 — Phase A에서 이미 만든 것 사용 |
| `prompt_templates` 테이블 (DB row) | RELEVANCE_SYSTEM이 DB에 있다면 SQL UPDATE + 마이그레이션 작성 |
| `frontend/src/pages/Settings.jsx` | (선택) Settings 페이지에 "본인 분야 키워드" 입력 UI를 추가해 사용자가 강제 규칙 토큰을 채울 수 있게. **이 작업은 선택. Phase F의 죽은 API 정리에 합칠 수도 있음.** |

### D.4 검증 방법

- 통합 테스트(#22~#25) 4건을 실제 Ollama로 실행 → CF₄/할로겐/VOC 5건이 모두 4점 이상, 무관 5건이 모두 3점 이하
- 프롬프트 변경 전후로 같은 fixture 10건에 대해 평균 점수 / 분산 비교 (수동 비교 표 작성)
- Discovery 1회 실행 후 `SELECT keywords_used, decisions_json FROM agent_runs ORDER BY id DESC LIMIT 1` → matched_keywords가 기대대로 채워지는지

### D.5 사용자 체크포인트

- [ ] D.1의 "확인 필요" 작업으로 RELEVANCE_SYSTEM 실제 위치 확정
- [ ] D.2 초안의 강제 규칙 토큰을 본인 분야 키워드로 치환 (TODO 마커 채우기)
- [ ] few-shot 예시 6건이 본인 분야의 경계 케이스를 잘 대표하는지 검토 (모자라면 추가)
- [ ] 통합 테스트 #22~#25를 실제 Ollama로 1회 실행해 PASS 확인
- [ ] Discovery 1 사이클 실행 후 점수 분포가 의도와 맞는지 (특히 4~5점 인접 그룹이 휴지통으로 떨어지지 않는지) 확인

### D.6 롤백

- DB 프롬프트 변경의 경우 변경 전 row를 `prompt_templates_backup` 임시 테이블에 저장 후 변경
- 코드 상수의 경우 단일 commit revert
- 캘리브레이션 효과가 기대보다 나쁘면 D만 revert하고 Phase C까지 상태로 운영 가능

---

## Phase E — Discovery 안정화 + bootstrap ACID

- **목표**: `_discovery_running` dict race 해결, heartbeat 추가, 멀티프로젝트 격리 검증, bootstrap의 Collection/Folder 트랜잭션 경계 확립, Discovery 저장 단계 부분 실패 롤백.
- **해결하는 AUDIT 항목**: §9 #4 (race), §9 #6 (bootstrap ACID), §9 #7 (heartbeat — Med 부분), §9 #9 (부분 실패)
- **작업 분량**: L (>3h)
- **선행 Phase**: A (B/C와 병렬 가능)

### E.1 race 해결 메커니즘 — 직접 결정

**선택지 비교** (paper-research 규모 = 단일 호스트, SQLite, 사용자 1명, 멀티 워커는 잠재 가능성):

| 옵션 | 장점 | 단점 | 적합성 |
|---|---|---|---|
| Redis 분산락 | 멀티 호스트 OK | 인프라 추가, paper-research 규모에 과함 | ❌ 과잉 |
| DB 행 락 (`UPDATE agent_runs SET locked_by=...`) | 추가 인프라 0, SQLite에 그대로 동작 | SQLite는 advisory lock 없음, 행락도 제한적 | △ 가능 |
| **파일 락 (`fcntl.flock`)** | 표준 라이브러리, 멀티 워커/CLI 모두 보호, 즉시 검증 가능 | 멀티 호스트 불가 (paper-research 비요구사항) | ✅ **채택** |
| 메모리 dict (현재) | 단순 | 단일 프로세스 한정 → 현재 결함 | ❌ 폐기 |

**결정: 파일 락 (fcntl.flock) + DB 마커 병행**.
- 파일 락(`data/discovery.lock`)으로 즉시 차단
- 병행해 `agent_runs` 테이블에 `started_at`, `heartbeat_at`, `locked_by` (PID + hostname) 컬럼 추가 → 디버깅용
- **근거**: paper-research는 SQLite 단일 호스트 단일 사용자 기준 (AUDIT §1: data/papers.db, §6.3: 단일 프로세스 가정). Redis는 운영 부담 대비 이득 없음. fcntl는 macOS/Linux에서 확정 동작하고 stale lock(프로세스 죽음) 시 OS가 자동 해제.

### E.2 변경 파일 목록

| 파일:라인 | 변경 |
|---|---|
| `backend/services/discovery_lock.py` | 신규 — `with discovery_lock(project_id):` 컨텍스트 매니저 (fcntl) |
| `backend/routers/dashboard.py:21` | `_discovery_running: dict` 제거 |
| `backend/routers/dashboard.py:155-186` | `_run_discovery_async`를 `discovery_lock` 경유로 교체. 이미 락이 잡혀 있으면 409 Conflict 반환 |
| `backend/services/run_agent_once.py` | CLI 진입점도 동일 락 사용. 락 실패 시 명시적 에러 + exit code 1 |
| `backend/services/research_agent/discovery.py:155-162` | 사이클 시작 시 heartbeat 시작, 사이클 동안 30s마다 `agent_runs.heartbeat_at` 업데이트 |
| `backend/services/research_agent/discovery.py:243-283` | Paper / PaperCollection / FolderPaper 저장을 단일 트랜잭션 + savepoint로 묶기. 실패 시 명시적 rollback + ReviewQueue 기록 (또는 단순 logger.error) |
| `backend/services/research_agent/bootstrap.py:43-69` | Collection/Folder upsert를 `IntegrityError` 폴백 패턴으로 변경. UNIQUE 제약 의존. |
| `backend/models.py` | `Collection.name` UNIQUE 제약 확인 (AUDIT §8에서 이미 UNIQUE) / `Folder`에 `(parent_id, name) UNIQUE` 추가 검토. `AgentRun`에 `heartbeat_at`, `locked_by` 컬럼 추가 |
| `backend/migrations/003_agent_lock_columns.py` | 신규 — heartbeat_at, locked_by 추가. Folder unique 인덱스 추가 (필요 시) |
| `backend/routers/dashboard.py` `agent/status` | `agentStatus()`가 heartbeat를 반환하도록. **이때 죽은 API였던 `dashboardAPI.agentStatus()` (AUDIT §7.2) 부활 결정** → Phase F 입력 |
| `frontend/src/pages/Dashboard.jsx` | (선택) heartbeat 표시. Phase F에서 본격 연결 |

### E.3 멀티프로젝트 격리 검증

- 현재 `_discovery_running: dict[str, bool]`이 project_id 키를 사용 (AUDIT §6.3). 다중 프로젝트가 실재한다면 락 키도 project_id로 분리해야 함.
- **확인 필요**: 현재 paper-research가 실제로 다중 프로젝트를 운영하는가? AUDIT는 `Collection`을 프로젝트 개념으로 시사하지만 단일/다중 운영 여부는 명시 안 함. 사용자에게 확인 후 락 파일명을 `data/discovery.lock` (단일) 또는 `data/discovery_<project_id>.lock` (멀티)로 결정.

### E.4 검증 방법

- Phase E 추가 테스트 #26~#30 (5건) 통과
- 수동: 두 개 터미널에서 `python -m services.run_agent_once` 동시 실행 → 두번째가 즉시 실패
- 수동: HTTP `POST /api/dashboard/agent/run` 두 번 연속 → 두번째 409 Conflict
- 수동: Discovery 사이클 도중 (KeyboardInterrupt 대신) `kill -9` → lock 파일이 OS에 의해 해제되는지 확인 (`lsof data/discovery.lock` 0건)
- 수동: bootstrap을 두 프로세스에서 동시 실행 → Collection/Folder 중복 0건

### E.5 사용자 체크포인트

- [ ] E.3의 멀티프로젝트 격리 정책 결정 (단일 락 vs 프로젝트별 락)
- [ ] 락 파일 위치(`data/discovery.lock`)가 git ignore되어 있는지 확인
- [ ] 마이그레이션 003 적용 전 DB 백업 (`data/backups/`)
- [ ] 두 터미널 동시 실행 테스트 직접 수행
- [ ] heartbeat 갱신 주기(30s 기본)가 본인 사이클 길이에 맞는지 검토

### E.6 롤백

- 마이그레이션 003 reversal 스크립트 함께 작성 (Drop column / index)
- 락 파일 자체는 코드 revert만으로 사용처가 사라지므로 잔존 파일은 수동 삭제
- `discovery.py` / `bootstrap.py` 변경분은 단일 commit으로 묶고 revert 가능하게

---

## Phase F — 죽은 API / 미연결 UI 정리

- **목표**: AUDIT §7.2의 6개 죽은 API에 대해 "삭제" vs "연결" 결정. 다른 모든 Phase가 끝나야 진짜 후보가 확정된다.
- **해결하는 AUDIT 항목**: §9 #10
- **작업 분량**: M (1~3h)
- **선행 Phase**: D, E

### F.1 6개 항목별 결정 초안

| 메서드 | AUDIT 위치 | 결정 초안 | 근거 |
|---|---|---|---|
| `searchAPI.search()` (client.js:6) | 일반 검색 진입점 | **연결**. Search 페이지에서 키워드만 넣고 AI 확장 없이 빠른 검색을 원할 때 사용. Toggle UI 추가. | Phase C에서 expand 실패 시 단일 키워드로 폴백하던 동작이 사라지므로, 사용자가 명시적으로 "빠른 검색"을 고를 수 있어야 함. |
| `papersAPI.getAnalyses()` (client.js:32) | 분석 이력 UI 부재 | **연결**. PaperDetail에 "분석 이력" 탭 추가. | AI 분석을 여러 번 돌리는 사용자 워크플로에 필요. |
| `foldersAPI.movePaper()` (client.js:64) | 폴더 간 이동 UI 부재 | **연결**. Library에서 drag&drop 또는 컨텍스트 메뉴. | AUDIT §9 #10이 명시적으로 "핵심 기능"으로 분류. |
| `dashboardAPI.agentStatus()` (client.js:143) | 상태는 getStats로만 조회 | **연결**. Phase E에서 heartbeat 도입했으므로 Dashboard에서 실시간 표시. | Phase E의 후속 작업. |
| `aiAPI.createPrompt()` (client.js:88) | 새 프롬프트 추가 UI 없음 | **삭제**. Settings에서 기존 프롬프트 수정만으로 충분. 새 프롬프트 추가는 yagni. | AUDIT 외 추론 — 사용자에게 확인 필요 |
| `aiAPI.getPrompt()` (client.js:86) | 단건 조회 미사용 | **삭제**. getPrompts 일괄 조회로 충분. | 동일 |

> **결정 정책**: "연결" 4건, "삭제" 2건. 단 createPrompt/getPrompt는 사용자 의사 확인 후 최종 결정.

### F.2 변경 파일 목록

| 파일 | 변경 |
|---|---|
| `frontend/src/pages/Search.jsx` | "빠른 검색" toggle + `searchAPI.search` 호출 분기 |
| `frontend/src/pages/PaperDetail.jsx` | "분석 이력" 탭 + `papersAPI.getAnalyses` 호출 |
| `frontend/src/pages/Library.jsx` | 폴더 이동 UI + `foldersAPI.movePaper` |
| `frontend/src/pages/Dashboard.jsx` | heartbeat 폴링 + `dashboardAPI.agentStatus` |
| `frontend/src/api/client.js` | (삭제 결정 시) `aiAPI.createPrompt`, `aiAPI.getPrompt` 제거. 또한 사용처 grep 0건 재확인 |
| `backend/routers/ai.py` | (삭제 결정 시) 해당 엔드포인트 핸들러 제거 — **단, 다른 사용처가 없는지 grep 한 번 더** |

### F.3 검증 방법

- Phase F 종료 후 `git grep "createPrompt\|getPrompt"` → 0건 (삭제 결정 시)
- "연결" 4건은 수동 시나리오로 직접 사용 (검색, 분석 이력 보기, 폴더 이동, 에이전트 상태 보기)
- 회귀 테스트: Phase A~E 모든 테스트가 그대로 통과 (Phase F는 신규 기능 연결이므로 기존 테스트는 영향 없음)

### F.4 사용자 체크포인트

- [ ] createPrompt / getPrompt 삭제 vs 유지 최종 결정
- [ ] "빠른 검색" toggle 기본값 (AI 확장 ON vs OFF) 결정
- [ ] 폴더 drag&drop UX (drag&drop vs 컨텍스트 메뉴) 선택
- [ ] PaperDetail의 "분석 이력" 탭 위치 (탭 vs 사이드 패널) 결정
- [ ] Phase F 완료 후 `git grep` 0건 확인 직접 수행

### F.5 롤백

- 프론트엔드 변경분은 페이지별 commit 분리 → 페이지별 revert
- 백엔드 엔드포인트 삭제는 마지막 commit으로 분리 → 단일 revert로 복구
- API 메서드 삭제는 git history에서 즉시 복구 가능 (코드량 적음)

---

## 마지막 섹션 — 위험과 미해결 질문

### M.1 AUDIT에 없어서 추측한 부분 (확인 필요)

1. **확인 필요**: RELEVANCE_SYSTEM 프롬프트의 정확한 정의 위치 — 코드 상수인지, DB `prompt_templates` row인지, `services/llm/tasks/*.py`인지. Phase D 시작 전 grep + DB 조회로 확정해야 함. (§D.1)
2. **확인 필요**: paper-research가 실제로 멀티 프로젝트를 운영하는가? `_discovery_running: dict[str, bool]`이 project_id 키를 사용한다는 점은 다중 프로젝트 가능성을 시사하지만, AUDIT는 명시하지 않음. Phase E 락 키 정책에 영향. (§E.3)
3. **확인 필요**: pydantic이 이미 의존성에 있는가? FastAPI가 표준으로 들고 있을 가능성이 높지만 `requirements.txt` 직접 확인 필요. Phase B의 strict_call schema 검증 기반. (§B.5)
4. **확인 필요**: 멀티 워커 환경(gunicorn -w N)이 실제로 운용 중인가, 아니면 단일 워커가 관행인가? 단일 워커라면 Phase E의 race는 잠재 위협이지만 우선순위 조정 가능. (AUDIT §9 #4 주: "현재 가림막: 단일 워커 + CLI 비사용 관행")
5. **추측**: AUDIT §4.6의 `suggest_tags` empty list 폴백은 Phase C의 fail-loud 정책에 포함하지 않았다. 이미 `error` 필드를 응답에 포함하므로 사용자 가시성이 어느 정도 있어 별도 처리 불필요로 판단. **이 판단의 검증 필요**.

### M.2 Phase 진행 중 막힐 가능성이 가장 높은 지점 3개

#### 위험 #1 — Phase B에서 ai_client.py의 어댑터 호환성

- **무엇이 막힐 수 있나**: AUDIT §2.1에 따르면 `complete()`는 `(text, prompt_tokens, completion_tokens)` 형태의 튜플 반환이 의심됨 (search.py:79 호출이 unpacking). strict_call이 단일 값(`str | dict | T`)을 반환하므로 어댑터가 토큰 카운트를 잃거나 추가 reverse-mapping이 필요. 모든 호출 사이트가 unpacking하는 형태라면 어댑터 작성이 까다로워짐.
- **선제 대응**: Phase B 착수 직후 가장 먼저 `grep -n "client.complete" backend/` 로 모든 unpacking 패턴 조사. 어댑터를 `(text, 0, 0)` 자리표시자 튜플로 우선 처리하고 호출부를 점진적으로 업데이트.

#### 위험 #2 — Phase C의 폴백 제거가 사용자 워크플로를 막을 수 있음

- **무엇이 막힐 수 있나**: 현재 사용자는 사일런트 폴백이 있는 상태에서 일상적으로 검색/알림을 사용 중. 폴백을 제거하는 순간 Ollama가 잠시만 느려도 검색 자체가 503으로 죽어버린다. 기존에 "느리지만 동작하던" 워크플로가 "안 동작"으로 바뀌는 회귀로 체감될 수 있음.
- **선제 대응**:
  - Phase C 적용 전 Ollama 응답시간 측정 (1주일 분 metrics 수집)
  - strict_call의 `timeout_s` 기본값을 보수적으로 설정 (60s → 120s)
  - retry 횟수 조정 (max_retries=2 → 3)
  - 적용 후 첫 24시간은 staging branch에서 dogfood, 503 발생 빈도 모니터링

#### 위험 #3 — Phase E의 fcntl 락이 macOS NFS / iCloud Drive에서 오작동

- **무엇이 막힐 수 있나**: `data/papers.db`가 iCloud Drive 동기화 폴더 안에 있다면 fcntl.flock의 동작이 비결정적. AUDIT §1에서 경로는 `/Users/igeonho/paper-research/data/`로 보이지만 이 디렉토리가 iCloud 백업/동기화 대상인지 확정 안 됨. 락 파일이 동기화 충돌로 깨질 가능성.
- **선제 대응**:
  - Phase E 시작 전 `ls -lO data/` (macOS) 또는 `xattr data/` 로 iCloud 동기화 여부 확인
  - 동기화 대상이라면 락 파일을 `~/.cache/paper-research/discovery.lock` (사용자 캐시 디렉토리)로 분리
  - 또는 `tempfile.gettempdir()` 사용

---

## 부록 — Phase 1 범위 외 항목

다음 항목은 본 플랜에서 다루지 않는다. 별도 Phase 2로 분리.

| 항목 | 이유 |
|---|---|
| AUDIT §9 #8 (`pdf_text` TEXT + JSON 컬럼 성능) | 스키마 마이그레이션 + 데이터 이전이 필요. Phase 1과 의존성 약함. 운영 데이터 증가 추세 측정 후 결정 |
| APScheduler / cron 자동 트리거 (AUDIT §9 #7의 "스케줄러" 부분) | Phase E에서 heartbeat까지만 다룸. 자동 스케줄링은 추가 의존성(APScheduler) + 운영 정책 결정이 필요해 분리 |
| CI/CD 파이프라인 (AUDIT §9 #5의 ".github/workflows/" 부분) | Phase A에서 pytest 인프라까지만. CI는 GitHub Actions 설정 + secrets 정책이 필요해 분리 |
| `.env`, `package.json`, `requirements.txt` 변경 | 본 플랜에서 발생하는 변경은 사용자에게 명시 보고 후 진행 (CLAUDE.md 규칙) |
