# Phase A — 회귀 테스트 스캐폴딩 완료 보고서

- **작성일**: 2026-04-07
- **근거**: `docs/REFACTOR_PLAN.md` §"Phase A — 회귀 테스트 스캐파딩"
- **상태**: ✅ 완료. **다음 Phase로 자동 진행하지 않음.** 사용자 체크포인트 통과 후 Phase B 또는 E 시작.

---

## 1. 생성/수정 파일 목록 (실제 라인 수)

### 신규 (12개, PLAN §A.1과 일치)

| 파일 | 라인 수 | 비고 |
|---|---|---|
| `backend/pytest.ini` | 16 | rootdir=backend, asyncio_mode=auto, marker `integration` 등록 |
| `backend/tests/__init__.py` | 1 | 패키지 마커 |
| `backend/tests/conftest.py` | 167 | DB(in-memory) / mock_ai / mock_ollama_lowlevel / mock_s2 / sample_papers / **autouse HTTP 차단 가드** |
| `backend/tests/fixtures/__init__.py` | 1 | 패키지 마커 |
| `backend/tests/fixtures/mock_ai.py` | 134 | `MockAIBehavior` (queue/default), `install_mock_ai`, `install_mock_ollama` |
| `backend/tests/fixtures/mock_s2.py` | 30 | `S2Client.bulk_search` monkeypatch (Phase C 이후 사용) |
| `backend/tests/fixtures/sample_papers.py` | 139 | CF₄/할로겐/VOC 인접 5건 + 무관 5건, `field` 태그 포함 |
| `backend/tests/test_ai_client_contract.py` | 110 | 테스트 #1~#4 |
| `backend/tests/test_search_helpers.py` | 92 | 테스트 #5~#7 |
| `backend/tests/test_alerts_score.py` | 69 | 테스트 #8~#9 |
| `backend/tests/test_dashboard_agent.py` | 43 | 테스트 #10 |

> **합계**: 11개 파일 + `pytest.ini` = **12개**, 802 라인.

### 수정 (1개)

| 파일 | 변경 |
|---|---|
| `requirements.txt` | `pytest>=8.0.0`, `pytest-asyncio>=0.23.0` 추가 (`httpx`는 이미 있음) |

---

## 2. `pytest -v` 출력

```
$ cd backend && pytest -v
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/igeonho/paper-research/backend
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.12.1, asyncio-1.2.0
asyncio: mode=auto
collected 10 items

tests/test_ai_client_contract.py::test_complete_returns_text_when_expect_json_false PASSED [ 10%]
tests/test_ai_client_contract.py::test_complete_retries_on_invalid_json_when_expect_json_true PASSED [ 20%]
tests/test_ai_client_contract.py::test_complete_returns_raw_text_after_max_retries PASSED [ 30%]
tests/test_ai_client_contract.py::test_parse_json_response_strips_markdown_fence PASSED [ 40%]
tests/test_alerts_score.py::test_score_relevance_extracts_first_number PASSED [ 50%]
tests/test_alerts_score.py::test_score_relevance_returns_5_on_no_match PASSED [ 60%]
tests/test_dashboard_agent.py::test_discovery_running_dict_blocks_second_call_same_process PASSED [ 70%]
tests/test_search_helpers.py::test_translate_korean_returns_original_on_exception PASSED [ 80%]
tests/test_search_helpers.py::test_expand_keywords_returns_single_keyword_on_exception PASSED [ 90%]
tests/test_search_helpers.py::test_ai_score_papers_returns_all_as_high_on_exception PASSED [100%]

============================== 10 passed in 0.29s ==============================
```

| # | 테스트 | 결과 |
|---|---|---|
| 1 | `test_complete_returns_text_when_expect_json_false` | ✅ PASS |
| 2 | `test_complete_retries_on_invalid_json_when_expect_json_true` | ✅ PASS |
| 3 | `test_complete_returns_raw_text_after_max_retries` | ✅ PASS *(버그 캡처)* |
| 4 | `test_parse_json_response_strips_markdown_fence` | ✅ PASS |
| 5 | `test_translate_korean_returns_original_on_exception` | ✅ PASS *(버그 캡처)* |
| 6 | `test_expand_keywords_returns_single_keyword_on_exception` | ✅ PASS *(버그 캡처)* |
| 7 | `test_ai_score_papers_returns_all_as_high_on_exception` | ✅ PASS *(버그 캡처)* |
| 8 | `test_score_relevance_extracts_first_number` | ✅ PASS |
| 9 | `test_score_relevance_returns_5_on_no_match` | ✅ PASS *(버그 캡처)* |
| 10 | `test_discovery_running_dict_blocks_second_call_same_process` | ✅ PASS *(부분 버그 캡처)* |

---

## 3. 각 테스트가 잠그는 현재 동작 (한 줄 요약)

| # | 잠그는 동작 | 종류 |
|---|---|---|
| 1 | `expect_json=False`이면 `_ollama` 응답 텍스트가 그대로 반환된다 (`ai_client.py:47`) | 정상 동작 |
| 2 | `expect_json=True`에서 `JSONDecodeError` 발생 시 보강 프롬프트로 재시도하고 다음 응답이 유효하면 그것을 반환 (`ai_client.py:49-53`) | 정상 동작 |
| 3 | **버그 캡처** — `expect_json=True`인데 `max_retries+1`회 모두 invalid JSON이면 `raise`하지 않고 마지막 raw 텍스트를 그대로 반환 (`ai_client.py:54-55`). Phase B/C에서 `LLMSchemaError` raise로 교체 예정. | **버그 캡처** |
| 4 | `parse_json_response`는 ` ```json ` 코드펜스를 제거하고 dict/list를 반환한다 (`ai_client.py:144-156`) | 정상 동작 |
| 5 | **버그 캡처** — `translate_korean_to_english`가 AI 실패 시 영문 번역 자리에 한국어 원문을 그대로 반환 (`search.py:79-83`). 사용자는 번역 실패를 모름. Phase C에서 503 raise로 교체. | **버그 캡처** |
| 6 | **버그 캡처** — `generate_queries_and_terms`가 AI 실패 시 입력 키워드 1개만 담은 리스트를 반환 (`search.py:372-375`). 검색 범위 급감 silent. Phase C에서 warning/503으로 교체. | **버그 캡처** |
| 7 | **버그 캡처** — `ai_score_papers`가 AI 실패 시 모든 논문을 첫 번째 반환값(high)에 그대로 넣고 `relevance_score=None`으로 둔다 (`search.py:440-445`). RELEVANCE_THRESHOLD 우회 = AUDIT §9 #1. Phase C에서 503으로 교체. | **버그 캡처** |
| 8 | `_score_relevance`가 LLM 응답에서 첫 숫자를 정규식으로 추출해 점수로 사용 (`alerts.py:283-286`) | 정상 동작 |
| 9 | **버그 캡처** — `_score_relevance`가 응답에 숫자가 없으면 `5.0`을 하드코딩 반환 (`alerts.py:287`) → AUDIT §9 #2 "유령 알림" 원흉. Phase C에서 Alert 생성 자체를 막거나 별도 실패 레코드로 분리. | **버그 캡처** |
| 10 | **부분 버그 캡처** — `_discovery_running` (in-process dict)에 의해 동일 프로세스 내 중복 트리거는 409로 거부됨 (`dashboard.py:172-176`). 한계: 멀티 워커/별도 프로세스 race를 막지 못함 = AUDIT §9 #4. Phase E에서 파일락/DB 마커로 교체. | **부분 버그 캡처** |

---

## 4. PLAN과 어긋난 결정

**없음**, 단 PLAN의 명시적 허용 범위 안에서 다음 두 가지 추가 결정이 있다 — 각각 PLAN의 요구사항을 더 강하게 만족하기 위한 것이지, PLAN 외 작업이 아니다.

1. **`conftest.py`에 autouse `_block_real_http` 가드 추가**.
   - **사유**: PLAN §A.3 "네트워크 차단 검증"을 단발성 실행 검증이 아니라 매 테스트마다 자동으로 강제. `pytest --disable-socket`은 별도 플러그인이고 PLAN A.1에 없는 의존성이라 도입하지 않음. 대신 `httpx.AsyncClient.send`를 monkeypatch로 raise시켜, 만에 하나 mock이 새도 실제 HTTP는 절대 닿지 않음. `socket.socket` 전역 차단은 ssl 모듈을 깨뜨려 부적절했다 (시도했다가 ssl.py 임포트 실패 확인).
   - **PLAN 부합성**: A.1 신규 파일 목록 안의 `conftest.py` 내부 강화이므로 신규 파일 추가 아님.

2. **`mock_ai.py`에 `install_mock_ollama` 헬퍼 추가** (저수준 monkeypatch).
   - **사유**: 테스트 #2, #3은 `AIClient.complete`의 retry/JSON 검증 로직 자체를 검증해야 하므로 `complete`를 패치하면 안 되고 `_ollama`를 패치해야 한다. 두 함수 모두 `mock_ai.py` 한 파일에 있다 (PLAN A.1의 `fixtures/mock_ai.py`).
   - **PLAN 부합성**: A.1의 "성공/타임아웃/JSON깨짐 3가지 모드" 요구사항을 만족시키는 구현 디테일.

3. **`requirements.txt` 위치**.
   - PLAN A.1 표는 `requirements.txt`라고만 적혀 있고 경로는 명시 안 함. 프로젝트 루트의 `requirements.txt`를 수정함 (`backend/requirements.txt`는 존재하지 않음). `start.sh`가 루트 `requirements.txt`를 사용하는 것을 확인.

---

## 5. 네트워크 차단 검증 결과

- ✅ **autouse 가드 동작 확인**: `httpx.AsyncClient.send`가 `RuntimeError("테스트 중 실제 HTTP 호출 차단됨")`로 교체된 상태에서 10건 모두 PASS → 어떤 테스트도 실제 HTTP를 호출하지 않음을 자동 입증.
- ✅ **가드 음성 검증**: 별도 스크립트로 `httpx.AsyncClient`에 차단 send를 주입한 뒤 GET 호출 → `BLOCKED` raise 확인. 가드가 실제로 작동함.
- ✅ **mock_ai 코드 리뷰**: `install_mock_ai`는 `monkeypatch.setattr(AIClient, "complete", patched_complete)` 하나만 사용. 외부 IO 없음.
- ⚠️ `pytest --disable-socket` 또는 `socket.socket` 전역 차단은 ssl 모듈을 깨뜨려 사용 불가 (Python 3.9). autouse httpx 가드가 동등 효과 + 더 안전.

---

## 6. 사용자 체크포인트 (PLAN §A.4 그대로)

다음 5개 항목을 직접 확인하고, 모두 ✅이면 Phase B (또는 E) 시작 승인:

- [ ] `requirements.txt`에 추가된 의존성(`pytest`, `pytest-asyncio`, `httpx`) 승인
  - 이미 venv에 설치 완료. `httpx`는 변경 없음.
- [ ] `cd backend && pytest -v` 직접 실행 → 10건 PASS 확인
  - 본 보고서의 §2 출력과 동일해야 함.
- [ ] 테스트가 실제 ollama/s2를 호출하지 않는지 (네트워크 끄고 재실행) 확인
  - `_block_real_http` autouse 가드가 매 테스트 자동 차단. 추가로 `unplug` 또는 `sudo ifconfig en0 down` 후 `pytest -v` 재실행 권장.
- [ ] `backend/tests/` 디렉토리 구조가 향후 확장하기에 합리적인지 검토
  - 구조: `tests/{test_*.py, conftest.py, fixtures/{mock_ai,mock_s2,sample_papers}.py}`. Phase B/C/D/E의 +20건 테스트는 같은 패턴으로 추가됨.
- [ ] 특성화 테스트(#5, #6, #7, #9)가 **현재 버그를 의도적으로 잠그고 있다는 점**을 인지
  - §3 표의 "버그 캡처" 5건. Phase C에서 의도적으로 깨지고 fail-loud 버전(#16~#21)으로 교체될 예정.

---

## 7. 다음 단계

PLAN §0.3 Phase 순서:
```
Phase A ✅ → Phase B (strict_call) ┐
            → Phase E (Discovery 안정화) ┘  ← 둘은 병렬 가능
```

**자동 진행하지 않음.** 위 체크포인트 5건 모두 ✅로 표시되면, 사용자가 명시적으로 "Phase B 시작" 또는 "Phase E 시작"을 지시할 것.
