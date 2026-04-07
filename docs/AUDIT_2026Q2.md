# Paper Research — 2026 Q2 코드베이스 감사

- **감사일**: 2026-04-07
- **방법론**: 4개 Explore 서브에이전트 병렬 실행 (읽기/grep 전용, 코드 수정 없음)
- **범위**: backend/, frontend/, data/, services/research_agent
- **분할 기준**:
  - **A1** = 디렉토리 구조 / DB 스키마 / 테스트·CI / 데이터 파일
  - **A2** = AI 호출 인벤토리 / 사일런트 폴백
  - **A3** = 라우터 인벤토리 / Discovery 상태 머신 / 동시성
  - **A4** = 프론트엔드 페이지 / API 정합성 / 데드 메서드
- **합산 산출**: 위험 후보 18건을 메인이 종합하여 §9 Top 10 위험으로 정렬

> 본 문서는 정적 분석에 기반한 스냅샷이다. 런타임 통계, 실제 트래픽, DB 인덱스 사용 빈도는 별도 검증 필요.

---

## 1. 디렉토리 구조

```
/Users/igeonho/paper-research/
├── backend/
│   ├── models.py                    (16개 테이블 정의)
│   ├── database.py                  (SQLAlchemy, DB: data/papers.db)
│   ├── main.py                      (FastAPI 진입점)
│   ├── routers/                     (10개 라우터)
│   │   ├── papers.py, search.py, ai.py, pdfs.py
│   │   ├── tags.py, folders.py, alerts.py, dashboard.py, export.py, settings.py
│   ├── services/
│   │   ├── run_agent_once.py        (CLI Discovery 진입점)
│   │   └── research_agent/
│   │       ├── __init__.py
│   │       ├── bootstrap.py         (Collection/Folder 멱등 시드)
│   │       └── discovery.py         (1 사이클 메인 로직)
│   ├── migrations/
│   │   └── 001_add_agent_columns.py
│   ├── s2_client.py, ai_client.py, schemas.py
│   └── static/index.html
├── frontend/
│   ├── src/
│   │   ├── App.jsx, main.jsx
│   │   ├── pages/                   (7개: Library, Search, Dashboard, Alerts, Compare, Settings, PaperDetail)
│   │   ├── components/
│   │   ├── api/client.js
│   │   └── index.css
│   ├── package.json, vite.config.js
├── data/
│   ├── papers.db                    (~2.5MB, 운영 DB)
│   └── backups/papers_20260407_171639.db
├── docs/, .vscode/, venv/
└── requirements.txt, package.json, start.sh, .env.example, CLAUDE.md
```

---

## 2. AI 호출 경로 인벤토리

### 2.1 AIClient 동작 요약

`backend/ai_client.py` (157 라인):

- `complete(system, user, images, max_retries=2, expect_json=False)`
  - backend 설정값에 따라 `_claude()` / `_ollama()` 분기
  - `expect_json=True`일 때 응답을 `re.sub` 정리 후 `json.loads` 검증, 실패 시 보강 프롬프트로 재시도
  - 최종 재시도까지 실패해도 **예외 대신 원본 텍스트 반환**
- `_claude(...)`: Anthropic AsyncAnthropic, 모델 `claude-sonnet-4-20250514`
- `_ollama(..., expect_json)`: `format="json"` + `temperature=0.1` (Gemma용)
- `parse_json_response(text)`: 마크다운 코드블록 제거 후 첫 `{...}` 또는 `[...]` 추출

### 2.2 호출 사이트 인벤토리

| 파일:라인 | 호출자 | expect_json | 파싱 방식 | 폴백 |
|---|---|---|---|---|
| search.py:80 | `translate_korean_to_english()` | False | 텍스트 그대로 | `return text, text` (예외 무시) |
| search.py:364 | `generate_queries_and_terms()` | False | `json.loads(clean)` | `return [keywords], [], ""` |
| search.py:420 | `ai_score_papers()` | False | `json.loads(clean)` | papers 전체 반환, score=None |
| alerts.py:281 | `_score_relevance()` | False | `re.search(r"\d+\.?\d*")` | `return 5.0` |
| alerts.py:241 | `check_alerts()` | (간접) | — | `relevance_score=5.0` 하드코딩 alert 생성 |
| ai.py:315 | `analyze_paper()` | True (structured) | `parse_json_response()` | HTTPException |
| ai.py:378 | `analyze_all()` | True (structured) | `parse_json_response()` | HTTPException |
| ai.py:484 | `batch_analyze()` | True (structured) | `parse_json_response()` | SSE 에러 이벤트 |
| ai.py:565 | `trend_analyze()` | False | 텍스트 | HTTPException |
| ai.py:614 | `review_draft()` | False | 텍스트 | HTTPException |
| ai.py:671 | `suggest_tags()` | True | `parse_json_response()` | empty list + error 필드 |
| services/research_agent/discovery.py | `extract_keywords()` / `score_relevance()` (services/llm/tasks 경유) | True | structured | discovery 사이클 내부 처리 |

> 주의: search.py의 3건은 `expect_json` 인자를 명시하지 않거나 False다. ai_client의 retry 로직(`expect_json=True`일 때만 활성)이 작동하지 않는다.

---

## 3. 라우터 인벤토리

| 파일 | Prefix | Tag | 엔드포인트 수 |
|---|---|---|---|
| search.py | `/search` | search | 8 |
| papers.py | (없음) | papers | 13 |
| ai.py | `/ai` | ai | 13 |
| pdfs.py | `/pdfs` | pdfs | 3 |
| export.py | `/export` | export | 6 |
| settings.py | `/settings` | settings | 2 |
| tags.py | `/tags` | tags | 7 |
| folders.py | `/folders` | folders | 8 |
| alerts.py | (없음) | alerts | 9 |
| dashboard.py | `/dashboard` | dashboard | 3 |

**총 ≈72개 엔드포인트**, 모두 `app.include_router(..., prefix="/api")` 하에 마운트.

### 핵심 라우터 발췌

**search.py**
- `GET /api/search`
- `POST /api/search/ai-search/stream`
- `GET /api/search/history`, `DELETE /api/search/history`, `DELETE /api/search/history/{id}`
- `GET /api/search/similar/{paper_id}`
- `GET /api/search/author`
- `GET|POST /api/search/filter-presets`, `DELETE /api/search/filter-presets/{id}`

**dashboard.py** (Discovery 에이전트 트리거)
- `GET /api/dashboard/stats`
- `POST /api/dashboard/agent/run` (BackgroundTasks)
- `GET /api/dashboard/agent/status`

---

## 4. 사일런트 폴백 위치

### 4.1 search.py:79-83 — 한글→영문 번역
```python
try:
    result_text, _, _ = await client.complete(system=system, user=user)
    return result_text.strip(), text
except Exception:
    return text, text  # 한글 그대로 S2에 전달 → 검색 0건/오류
```

### 4.2 search.py:363-375 — AI 쿼리 확장
```python
try:
    ...
    return queries, terms, expanded
except Exception:
    pass
return [keywords], [], ""  # 단일 키워드만 검색, 사용자는 모름
```

### 4.3 search.py:419-445 — `ai_score_papers()` (가장 위험)
```python
try:
    ...
    return high, low
except Exception:
    for p in papers:
        p["relevance_score"] = None
        p["relevance_reason"] = None
    return papers, []   # 전부 high_relevance 취급, 임계값 무시
```

### 4.4 alerts.py:241-254 — 알림 점수 폴백
```python
try:
    score = await _score_relevance(ai, sub, p)
    if score >= threshold: ...
except Exception:
    alert = Alert(..., relevance_score=5.0)  # 하드코딩
    db.add(alert)
```

### 4.5 alerts.py:266-287 — `_score_relevance()` 정규식 매칭 실패
```python
match = re.search(r"(\d+\.?\d*)", result_text.strip())
if match:
    return min(float(match.group(1)), 10.0)
return 5.0  # "six", "6 out of 10" → 5.0
```

### 4.6 ai.py:671 — `suggest_tags()`
JSON 파싱 실패 시 empty list + error 필드. 프론트가 error를 무시하면 "태그 없음"으로 보임.

---

## 5. 테스트 커버리지 현황

- **단위/통합 테스트**: 없음 (`tests/`, `test_*.py`, `conftest.py` 부재)
- **pytest 설정**: 없음 (`pytest.ini` / `pyproject.toml` 부재)
- **CI/CD**: 없음 (`.github/workflows/` 부재)
- **마이그레이션**: `backend/migrations/001_add_agent_columns.py` 1건 (멱등 보장, 직접 실행)
- **E2E**: 없음 (Playwright/Cypress 등 설정 없음)

→ 16 테이블 / ≈72 엔드포인트 / 7 페이지 규모에서 **회귀 감지 수단이 0**.

---

## 6. Discovery 에이전트 상태 머신

### 6.1 트리거 진입점

1. **HTTP** (공식): `POST /api/dashboard/agent/run` → `_run_discovery_async()` → BackgroundTasks
   - `routers/dashboard.py:155-186`
2. **CLI** (수동): `python -m services.run_agent_once`
   - `services/run_agent_once.py` — **`_discovery_running` 플래그 미체크**
3. **스케줄러**: ❌ 없음 (APScheduler/cron 미구현)

### 6.2 1 사이클 흐름 (`services/research_agent/discovery.py:144-296`)

| 단계 | 라인 | 작업 |
|---|---|---|
| 초기화 | 155-162 | `bootstrap_project()` → `ProjectHandles`, `DiscoveryReport` 생성 |
| 1. 키워드 추출 | 163-174 | 최근 키워드 로드 → LLM `extract_keywords()` |
| 2. S2 검색 | 182-189 | `S2Client.bulk_search(limit_per_query=10)` |
| 3. 중복 제거 | 191-205 | DB 기존 paper_id + in-batch set |
| 4. 평가 + 분류 | 208-241 | 각 후보마다 `score_relevance()` LLM → `_classify(score)` |
| 5. 저장 | 243-283 | `dry_run=False`일 때만 `Paper` + `PaperCollection` + `FolderPaper` |
| 6. 키워드 기록 | 286-288 | `SearchedKeyword` 누적 |
| 7. 커밋 + AgentRun | 289-320 | `db.commit()` → `_persist_run()` (try/except/rollback) |

**분류 임계값** (`_classify()`):
- 0–3 → 휴지통 (`is_trashed=True`)
- 4 → 검토 대기
- 5–6 → 자동 발견
- 7–9 → 풀분석 추천

### 6.3 동시성 보호

- `_discovery_running: dict[str, bool]` — `routers/dashboard.py:21`
- 보호 범위: **단일 프로세스, HTTP 진입점만**
- heartbeat / 진행률: 없음 (로그만)
- 트랜잭션: Paper/PaperCollection/FolderPaper는 단일 commit, AgentRun은 별도 commit + rollback 처리

---

## 7. 프론트엔드 페이지 인벤토리

### 7.1 페이지 ↔ 라우트 ↔ API 매트릭스

| 페이지 | 라우트 | 사용 API | 상태 |
|---|---|---|---|
| Dashboard | `/dashboard` | `dashboardAPI.getStats`, `dashboardAPI.runAgent` | 정상 |
| Search | `/search` | `searchAPI.aiSearchStream`, `getPaper`, `getHistory`, `*FilterPreset*`, `papersAPI.save` | 정상 |
| PaperDetail | `/paper/:paperId` | `searchAPI.getPaper`, `papersAPI.*`, `collectionsAPI.*`, `tagsAPI.*`, `foldersAPI.*`, `aiAPI.analyze*`, `aiAPI.suggestTags`, `pdfsAPI.*` | 정상 |
| Library | `/library` | `papersAPI.*`, `collectionsAPI.*`, `tagsAPI.*`, `foldersAPI.*`, `aiAPI.batchAnalyzeStream/trendAnalyze/reviewDraft`, `exportAPI.*` | 정상 |
| Compare | `/compare` | `papersAPI.list`, `aiAPI.analyze/trendAnalyze`, `exportAPI.csv`, `searchAPI.getPaper` | 정상 |
| Alerts | `/alerts` | `alertsAPI.*`, `papersAPI.save` | 정상 |
| Settings | `/settings` | `settingsAPI.*`, `aiAPI.getPrompts/updatePrompt/resetPrompts/testConnection` | 정상 |

### 7.2 죽은 API 메서드 (정의되었으나 import 0)

| 메서드 | 위치 | 영향 |
|---|---|---|
| `searchAPI.search()` | client.js:6 | 일반 검색 진입점인데 미사용 |
| `papersAPI.getAnalyses()` | client.js:32 | 분석 이력 UI 부재 |
| `foldersAPI.movePaper()` | client.js:64 | 폴더 간 이동 UI 부재 |
| `dashboardAPI.agentStatus()` | client.js:143 | 상태는 `getStats()`로만 조회 |
| `aiAPI.createPrompt()` | client.js:88 | 새 프롬프트 추가 UI 없음 |
| `aiAPI.getPrompt()` | client.js:86 | 단건 조회 미사용 |

### 7.3 엔드포인트 정합성

**전부 일치**. 프론트엔드의 모든 호출 경로가 백엔드 라우터에 존재.

---

## 8. DB 스키마

| 테이블 | 핵심 컬럼 | 인덱스 | JSON/Text 컬럼 |
|---|---|---|---|
| **papers** (44 컬럼) | id PK, paper_id UNIQUE, title, year, venue, status, is_trashed, relevance_score, pdf_text | paper_id, is_trashed, relevance_score | authors_json, external_ids_json, fields_of_study_json, **pdf_text(TEXT)** |
| **collections** | id, name UNIQUE, description | — | — |
| **paper_collections** | id, paper_id FK, collection_id FK | — | — |
| **tags** | id, name UNIQUE, color | — | — |
| **paper_tags** | id, paper_id FK, tag_id FK | — | — |
| **folders** | id, name, parent_id FK self | — | — |
| **folder_papers** | id, folder_id FK, paper_id FK | — | — |
| **ai_analysis_results** | id, paper_id FK, analysis_type, model_name | — | result_json |
| **app_settings** | id, key UNIQUE, value | — | — |
| **search_cache** | id, keyword UNIQUE | keyword | queries_json, results_json |
| **search_history** | id, keyword, searched_at | keyword | queries_json, expanded_terms |
| **subscriptions** | id, sub_type, query, is_active, last_checked | — | — |
| **alerts** | id, subscription_id FK, paper_id_s2, title, relevance_score, is_read | — | authors_json |
| **batch_jobs** | id, job_type, status, progress | — | paper_ids_json, result_json |
| **prompt_templates** | id, name UNIQUE, category, system_prompt | — | — |
| **filter_presets** | id, name UNIQUE | — | filters_json |
| **agent_runs** | id, started_at | started_at | keywords_used, decisions_json |
| **searched_keywords** | id, keyword UNIQUE, last_searched_at | last_searched_at | — |

총 **18개 테이블**, JSON Text 컬럼 ≈12개.

---

## 9. 발견된 위험 Top 10

A1–A4의 18건 위험 후보를 영향도/재현 가능성/노출 표면 기준으로 종합·정렬한 결과.

### #1 [High] `ai_score_papers()` 사일런트 폴백이 임계값을 무력화
- **위치**: `backend/routers/search.py:419-445`
- **영향**: AI 점수 매기기 실패 시 모든 논문이 `relevance_score=None`인 채 high_relevance 버킷에 들어간다. `RELEVANCE_THRESHOLD ≥ 6.0` 필터(`search.py:746`)가 무관 논문을 거르지 못한다.
- **재현**: Ollama 다운/타임아웃/JSON 파싱 실패 한 번이면 즉시 발생.
- **근본 원인**: `expect_json=True` 미지정 + `except Exception: pass` 후 fail-open 반환.

### #2 [High] 알림 점수 폴백으로 잘못된 하드코딩 알림 생성
- **위치**: `backend/routers/alerts.py:241-254`, `:266-287`
- **영향**: 점수 계산 실패 시 `relevance_score=5.0` 하드코딩으로 Alert 저장. `threshold=6.0`로 운영하면 영원히 사용자에게 노출되지 않는 "유령 알림"이 누적된다.
- **근거**: `_score_relevance()`도 정규식 매칭 실패 시 `return 5.0`.

### #3 [High] `expand_keywords` / `translate_korean_to_english` 사일런트 폴백
- **위치**: `search.py:79-83`, `search.py:363-375`
- **영향**: 번역 실패 시 한글 원문이 그대로 S2에 전달돼 결과 0건. 쿼리 확장 실패 시 단일 키워드만 검색돼 검색 범위 급감. 사용자에게는 정상 동작처럼 보임.
- **근본 원인**: 두 함수 모두 `expect_json` 미지정 + 광범위 `except Exception`.

### #4 [High] 멀티 워커 / CLI ↔ HTTP race
- **위치**: `routers/dashboard.py:21` (`_discovery_running: dict`), `services/run_agent_once.py`
- **영향**: 단일 프로세스 메모리 dict로만 동시 실행 방지. gunicorn N workers 또는 CLI 동시 실행 시 같은 프로젝트에서 Discovery 사이클이 중복 실행된다. SearchedKeyword 중복, AgentRun 중복, S2 quota 낭비, 부분 저장 위험.
- **현재 가림막**: 단일 워커 + CLI 비사용 관행에 의존.

### #5 [High] 테스트/CI 인프라 0
- **위치**: `tests/`, `pytest.ini`, `.github/workflows/` 모두 부재
- **영향**: 18 테이블 / ≈72 엔드포인트 / 사일런트 폴백 다수에 대해 회귀 감지 수단이 없다. 특히 #1~#3 폴백은 단위 테스트 1개로 잡을 수 있는 종류의 결함.

### #6 [High] bootstrap의 Collection/Folder 멱등성에 ACID 없음
- **위치**: `services/research_agent/bootstrap.py:43-69`
- **영향**: `query → not found → add → flush` 사이에 다른 워커가 같은 이름의 Collection/Folder를 INSERT 가능. 멀티 워커 환경에서 시드 데이터 중복.
- **수정 방향**: UNIQUE 제약 + `IntegrityError` 폴백 또는 advisory lock.

### #7 [Med] "자율 에이전트"인데 스케줄러/heartbeat 부재
- **위치**: `services/research_agent/discovery.py`, `routers/dashboard.py`
- **영향**: APScheduler/cron 없음 → 사용자가 매번 수동 트리거. heartbeat/진행률 없음 → 2~3분 동안 프론트는 폴링만. 실패 시점·단계 추적 불가능 (로그 외).
- **분류 근거**: 기능 누락이지 결함은 아니므로 Med.

### #8 [Med] `papers.pdf_text` TEXT + JSON 컬럼 다수의 성능 위험
- **위치**: `models.py` (papers.pdf_text, authors_json, external_ids_json, fields_of_study_json, search_cache.results_json, batch_jobs.paper_ids_json 등)
- **영향**: SQLite는 JSON 네이티브 인덱스 미지원. 검색·필터링은 Python 레벨 디시리얼라이즈에 의존. 데이터 1만건 규모에서 latency 누적, pdf_text는 SELECT * 시 메모리 폭증.
- **완화**: 자주 필터링되는 키는 정규화 컬럼으로 분리, pdf_text는 별도 테이블 분리.

### #9 [Med] Discovery 저장 단계 부분 실패 처리 부재
- **위치**: `services/research_agent/discovery.py:243-283`
- **영향**: Paper/PaperCollection/FolderPaper 중간에 예외 발생 시 명시적 rollback 없이 다음 단계 진행. AgentRun만 별도 commit으로 보호.
- **수정 방향**: 단일 트랜잭션 + savepoint, 실패 후보는 ReviewQueue로.

### #10 [Med] 죽은 API & 미연결 UI 기능
- **위치**: `frontend/src/api/client.js` (searchAPI.search, foldersAPI.movePaper, dashboardAPI.agentStatus, aiAPI.createPrompt/getPrompt, papersAPI.getAnalyses)
- **영향**: 백엔드는 구현돼 있는데 UI가 없거나, UI는 기획돼 있는데 호출이 없다. 특히 `foldersAPI.movePaper`와 `searchAPI.search`는 사용자에게 노출돼야 할 핵심 기능. 향후 회귀·혼동 위험.
- **분류 근거**: 사용자에게 즉각 피해가 없으므로 Med.

---

## 부록 — 후속 권장 작업 (감사 범위 외, 참고용)

> 본 문서는 read-only 감사 산출물이다. 아래는 단순 메모이며, 실제 변경은 별도 승인/플랜이 필요하다.

1. **§9 #1~#3 폴백 정리**: `expect_json=True` 명시 + 폴백을 사용자 가시 에러로 변환
2. **alerts 하드코딩 5.0 제거**: 실패 시 알림을 만들지 않거나 별도 "AI 실패" 카테고리
3. **테스트 부트스트랩**: pytest + httpx async client + ai_client/s2_client mock
4. **Discovery 동시성**: 단일 워커 강제 또는 DB advisory lock
5. **죽은 메서드 정리**: 사용처가 없으면 client.js에서 삭제하거나 UI 연결
