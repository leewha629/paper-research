# FIX_ANALYZE_SPEED — 진단 (작업 전)

날짜: 2026-04-08
대상: paper-research backend, gemma4:e4b on Mac Mini 16GB
보고된 증상: AI 전체 분석 1분 → 6분 (~5~10배 회귀). 360s timeout 발생.

## 1. 회귀 원인

Phase B `strict_call` 마이그레이션에서 `expect_mode`를 `"json"` 또는 `"schema"`로 보낼 때, ollama_client는 디코더 레벨에서 `format=json` 또는 `format=<JSON Schema>` (방어선 1)을 강제한다. gemma4:e4b 같은 작은 모델에서는 grammar-constrained 디코딩이 토큰당 5~10배 느려지고, 본문 30000자 컨텍스트와 곱해져 사용자 보고와 일치한다.

`call_llm`의 기본값은 `max_retries=2` (총 3회) + `timeout_s=120`. 디코딩이 느려지면 첫 호출에서 timeout → 3회 재시도까지 합쳐 최악 360s로 증폭.

## 2. expect_mode 결정 위치

| 함수 | 파일 | 라인 | 분기 |
|---|---|---|---|
| analyze_paper | backend/routers/ai.py | 315 | `"json" if analysis_type == "structured" else "text"` |
| analyze_all | backend/routers/ai.py | 385 | 동일 (structured만 json) |
| batch_analyze | backend/routers/ai.py | 498 | 동일 |
| trend_analyze | backend/routers/ai.py | 590 | `"text"` 고정 — 정상 |
| review_draft | backend/routers/ai.py | 649 | `"text"` 고정 — 정상 |
| suggest_tags | backend/routers/ai.py | (별도) | `"schema"` — 짧은 응답이라 grammar 영향 작음, 본 fix 범위 외 |

→ 회귀 발생 지점은 `structured` 분석 1종 (analyze_paper, analyze_all, batch_analyze 안에서). 다른 분석 종류(`summary`, `synthesis_conditions` 등)는 이미 `"text"`이므로 본문상은 디코더 grammar가 켜져 있지 않다.

### 다만 spec 의도 재해석
사양서가 명시한 `synthesis_conditions, analyze_paper, analyze_all, batch_analyze` 4개는 **분석 함수 단위**이며, 그중 grammar 회귀는 `structured` 분석에서만 발생. 따라서 본 fix는:
- 함수 호출부 3곳 (analyze_paper / analyze_all / batch_analyze)에서 `expect_mode = "text"`로 강제
- `structured` 분석 종류에 한해 사후 `parse_json_response`로 변환 (legacy `result_json` 컬럼 호환 유지)
- `max_retries=1, timeout_s=60` 명시 (모든 호출)

## 3. 시스템 프롬프트 위치

- 하드코딩 기본값: `backend/routers/ai.py:44-162` `SYSTEM_PROMPTS` dict
- DB 우선 조회: `backend/routers/ai.py:199-211` `get_system_prompt(db, analysis_type)` — `PromptTemplate` 테이블의 `system_prompt` 컬럼이 있으면 그것을, 없으면 하드코딩 fallback. **항상 `BASE_CONTEXT`(라인 18-25)를 앞에 prepend**.
- 인라인 prompts.py: `backend/services/llm/prompts.py` (140줄). 검토 결과 ai.py 분석 종류와는 별도(검색 관련성/요약용 헬퍼)로, 본 fix 범위 외.
- DB seed: `_seed_default_prompts()` (라인 183) — 하드코딩 본문을 그대로 시드. 본 fix에서 하드코딩 본문 (`SYSTEM_PROMPTS["structured"]`)을 갱신해도 **이미 시드된 DB 레코드는 갱신되지 않는다**. 사용자 운영 환경에서는 `PromptTemplate` 레코드를 직접 업데이트하거나 fresh seed 필요.

## 4. parse_json_response 위치

- `backend/ai_client.py:153-165` — Phase A 회귀 테스트 #4(`test_parse_json_response_strips_markdown_fence`)가 잠그는 함수.
- 마크다운 코드펜스 제거 + `{...}` 또는 `[...]` 본체 추출 + `json.loads`.
- ai.py는 이미 `from ai_client import AIClient, parse_json_response` (라인 11)로 import 중 → 추가 import 불필요.
- 동등 헬퍼: `services/llm/ollama_client.py:87` `clean_json_response()` (정규화만, json.loads 안 함). 본 fix는 ai.py 친화성 + Phase A 테스트 #4 보존을 위해 `ai_client.parse_json_response`를 사용.

## 5. 변경 계획 요약

| # | 파일 | 라인 | 변경 |
|---|---|---|---|
| 1 | backend/routers/ai.py | 311-329 | analyze_paper: `expect="text"` 강제, 사후 parse, `max_retries=1, timeout_s=60` |
| 2 | backend/routers/ai.py | 376-406 | analyze_all: 동일 패턴 |
| 3 | backend/routers/ai.py | 480-512 | batch_analyze: 동일 패턴 |
| 4 | backend/routers/ai.py | 121-133 | `SYSTEM_PROMPTS["structured"]` 강화: 출력 형식 강제 + few-shot |
| 5 | backend/tests/test_ai_analyze_text_mode.py | new | `analyze_paper`가 markdown fence 포함 응답을 정상 파싱하는지 검증 |

## 6. 영향 범위

- 변경 함수: `analyze_paper`, `analyze_all`, `batch_analyze` (structured 포함 8가지 분석 종류 모두)
- 비변경 함수: `trend_analyze`, `review_draft` (이미 text), `suggest_tags` (schema, 짧은 응답이라 무관 — spec 명시 제외)
- 마이그레이션: 없음
- 의존성: 없음
