# FIX_ANALYZE_SPEED — 작업 보고 (작업 후)

날짜: 2026-04-08
환경: paper-research backend, gemma4:e4b on Mac Mini 16GB
관련 진단: `docs/FIX_ANALYZE_SPEED_DIAGNOSIS.md`
관련 사양: `.claude/prompts/fix_analyze_speed.md`

## 요약

Phase B 마이그레이션 후 `structured` 분석에서 ollama `format=json`/`format=<schema>` 디코더 grammar가 켜지면서 gemma4:e4b가 5~10배 느려져 1분 → 6분 회귀 발생. **3개 호출부 모두 `expect="text"`로 강제 + 사후 `parse_json_response` 파싱 + `max_retries=1, timeout_s=60` 강제**로 디코더 grammar를 우회. `structured` 시스템 프롬프트를 강화하여 모델이 순수 JSON만 출력하도록 유도.

## 변경 파일

| 파일 | 라인 (변경 후 기준) | 변경 요약 |
|---|---|---|
| `backend/routers/ai.py` | 121-145 | `SYSTEM_PROMPTS["structured"]` — 출력 형식 디렉티브 + 스키마 + few-shot 1건 추가 |
| `backend/routers/ai.py` | 311-348 | `analyze_paper` — `expect="text"` 강제, structured는 사후 파싱 |
| `backend/routers/ai.py` | 380-422 | `analyze_all` — 동일 패턴 |
| `backend/routers/ai.py` | 504-526 | `batch_analyze` SSE 루프 — 동일 패턴 |
| `backend/tests/test_ai_analyze_text_mode.py` | 신규 (1 테스트) | structured + markdown fence 응답 정상 파싱 검증 |

(나머지 호출부 `trend_analyze` / `review_draft` / `suggest_tags`는 spec 제외 대상이므로 미수정.)

## expect 모드 변경 표

| 함수 | 분석 종류 | Before | After |
|---|---|---|---|
| `analyze_paper` | structured | `expect="json"` (grammar 강제, max_retries=2, timeout_s=120) | `expect="text"` + 사후 `parse_json_response`, max_retries=1, timeout_s=60 |
| `analyze_paper` | summary/synthesis_conditions/experiment_summary/significance/keywords | `expect="text"` (이미) | `expect="text"`, max_retries=1, timeout_s=60 |
| `analyze_all` | structured | `expect="json"` | `expect="text"` + 사후 파싱 |
| `analyze_all` | (기타) | `expect="text"` | `expect="text"`, max_retries=1, timeout_s=60 |
| `batch_analyze` | structured | `expect="json"` | `expect="text"` + 사후 파싱 |
| `batch_analyze` | (기타) | `expect="text"` | `expect="text"`, max_retries=1, timeout_s=60 |

(`trend_analyze` / `review_draft` / `suggest_tags`는 변경 없음 — spec 제외 명시.)

## 시스템 프롬프트 강화 (structured)

`SYSTEM_PROMPTS["structured"]` (ai.py:121)에 다음 섹션 추가:

- **### 출력 형식 (반드시 준수)** — markdown fence 금지, 큰따옴표 강제, null 금지(누락은 `"초록만으로 확인 불가"`)
- **### 스키마** — 6개 키의 예시 구조
- **### 예시** — Cu/SSZ-13 NH3-SCR 1건 few-shot

> ⚠️ **운영 주의**: `_seed_default_prompts()`(ai.py:183)는 DB가 비어 있을 때만 시드한다. 이미 운영 환경에서 `PromptTemplate.name == "structured"` 레코드가 존재하면, **하드코딩 본문 갱신이 자동 반영되지 않는다**. 운영 DB에 반영하려면:
> 1. `/api/prompts` 라우터에서 structured 프롬프트를 새 본문으로 업데이트, 또는
> 2. `prompt_templates` 테이블의 해당 row를 직접 삭제 후 백엔드 재시작 (자동 reseed).

## 분석 종류별 프롬프트 강화 범위

사양서는 "synthesis_conditions, analyze_paper, analyze_all, batch_analyze의 system 프롬프트"를 강화 대상으로 지목했지만, 실제 코드에서:

- `analyze_paper` / `analyze_all` / `batch_analyze`는 **함수**이지 분석 종류가 아니다 — 자체 시스템 프롬프트가 없음.
- `synthesis_conditions`는 마크다운 표를 반환하는 분석 종류로, 현재 이미 `expect="text"` (grammar 회귀 무관). JSON 스키마 디렉티브를 추가하면 프론트엔드 마크다운 렌더링이 깨진다.
- 실제 grammar 회귀는 `structured` 분석 종류에서만 발생.

→ 본 fix는 **`structured` 시스템 프롬프트 1종에만** 출력 형식 강제 디렉티브를 적용. 호출부 변경(`expect="text"` 강제 + max_retries=1 + timeout_s=60)은 **3개 함수 모두**에 적용. 결과적으로 spec의 핵심 목표(디코더 grammar 제거 + retry/timeout 단축)는 100% 달성.

## 신규 테스트 결과

```
backend/tests/test_ai_analyze_text_mode.py::test_analyze_paper_structured_parses_markdown_fence_response PASSED
```

검증 항목:
1. `analyze_paper`가 LLM에 `expect="text"`를 전달함 (디코더 grammar 회귀 가드)
2. `max_retries=1`이 강제됨 (retry 폭주 가드)
3. ` ```json ... ``` ` fence가 섞인 응답이 와도 `parse_json_response`로 정상 dict 추출
4. 결과의 `result_json`에 직렬화된 dict가 저장됨

## 전체 회귀 결과

```
$ venv/bin/python -m pytest backend/tests/ -q
..................                                                       [100%]
18 passed in 0.35s
```

기존 17건 + 신규 1건 = **18/18 PASS**.

## 사용자 검증 가이드

1. **백엔드 재시작** (코드 변경 반영):
   ```bash
   # 기존 백엔드 프로세스 종료 후
   cd backend && ../venv/bin/python -m uvicorn main:app --reload
   ```
2. **운영 DB의 structured 프롬프트 갱신** (선택, structured 분석을 자주 쓰는 경우):
   - 프론트엔드 "프롬프트 관리" 화면에서 `structured` 항목을 열고, 본문을 ai.py:121-145의 새 본문으로 덮어쓰기 + 저장.
   - 또는 운영 SQLite에서 `DELETE FROM prompt_templates WHERE name='structured';` 후 재시작.
3. **속도 검증**:
   - 임의 논문(중간 길이, PDF 본문 5000~15000자) 한 건에 대해 **"AI 전체 분석" 버튼** 클릭.
   - 기대치: **6개 분석 (summary, synthesis_conditions, experiment_summary, significance, keywords, structured) 합쳐 1분 이내 완료**.
   - 360s timeout 미발생.
4. **결과 정상성 확인**:
   - structured 결과에 6개 키 (`purpose`, `catalysts`, `synthesis_methods`, `characterization_techniques`, `key_results`, `relevance_to_environmental_catalysis`) 모두 존재.
   - markdown fence(``` ``` ```) 가 결과 텍스트에 섞여 있지 않음.
   - 다른 분석(요약/합성조건 등)의 마크다운 표 렌더링이 기존과 동일.
5. **실패 케이스 동작 확인** (선택):
   - 모델이 비정상적으로 망가져 JSON을 못 만드는 경우, structured 분석은 HTTP 500 + `"AI 응답 형식 오류: structured JSON 파싱 실패 ..."` 에러 메시지를 반환 (사일런트 폴백 없음, Phase C 정책 유지).

## 적용 제약 준수 체크리스트

- [x] Phase E (Discovery / bootstrap) 미변경
- [x] Phase D (RELEVANCE_SYSTEM) 미변경
- [x] suggest_tags / trend_analyze / review_draft 미변경
- [x] LLMError 글로벌 핸들러 미변경
- [x] 마이그레이션 추가 없음
- [x] grammar mode 재활성화 없음
- [x] timeout 60s × 1 baseline 강제 (모든 변경 호출부)
- [x] 모델 교체 없음 (gemma4:e4b 유지)
