역할: paper-research analyze 속도 회귀 fix.

## 문제
Phase B 마이그레이션 후 ai.py의 구조화 분석(synthesis_conditions, analyze_paper, analyze_all, batch_analyze)이 strict_call의 grammar-constrained 모드(expect="json"/"schema")로 인해 gemma4:e4b on Mac Mini 16GB에서 5~10배 느려짐. 120s × 3 retry = 360s timeout 발생. 사용자 보고: "원래 1분 → 6분".

## 전략 (디코더 grammar 제거 + 프롬프트 강제 + 사후 파싱)
1. 모든 구조화 분석을 expect="text"로 변경
2. 시스템 프롬프트에 JSON schema를 텍스트로 명시 + few-shot 1개 + "Output ONLY JSON, no markdown fence" 디렉티브
3. 응답 받은 후 services/llm/validate.py 또는 ollama_client.py의 parse_json_response (또는 동등 헬퍼)로 파싱
4. 파싱 실패 시 LLMSchemaError raise (LLMTimeoutError 아님)
5. max_retries 3 → 1, timeout_s 120 → 60

## 작업 범위
- backend/routers/ai.py 라인 311 (analyze_paper), 378 (analyze_all), 480 (batch_analyze)
- backend/services/llm/prompts.py 또는 ai.py 내 분석 종류별 system 프롬프트
- backend/services/llm/router.py 또는 ollama_client.py — parse_json_response 헬퍼 노출 확인

## 작업 순서
1. 먼저 grep으로 다음 확인 후 docs/FIX_ANALYZE_SPEED_DIAGNOSIS.md에 기록 (코드 수정 전):
   - `expect_mode` 변수가 어디서 결정되는지 (analyze_paper/all/batch 각각)
   - 분석 종류별 system 프롬프트 위치 (services/llm/prompts.py vs ai.py 인라인 vs DB prompt_templates)
   - parse_json_response 또는 동등 함수 위치 (Phase A 테스트 #4가 잠그는 함수)

2. 프롬프트 강화 (분석 종류별):
   - synthesis_conditions, analyze_paper, analyze_all, batch_analyze의 system 프롬프트에 다음 추가:
### 출력 형식 (반드시 준수)
 - 응답은 JSON 객체 단 하나. 다른 텍스트 절대 포함 금지.
 - markdown fence (```json ... ```) 사용 금지. 순수 JSON만.
 - 모든 키와 문자열 값은 큰따옴표.
 - 누락 정보는 "초록만으로 확인 불가"로 채울 것 (null 금지).
 
 ### 스키마
 {<해당 분석 종류의 스키마를 JSON 문자열로 명시>}
 
 ### 예시 (반드시 이 형식으로)
 {<짧은 few-shot 1개>}
- synthesis_conditions의 경우 LaTeX 표기($\text{Ca(OH)}_2$ 등) 허용 — 백슬래시 이스케이프 안 깨지게 raw string으로

3. 호출부 변경 (ai.py 311, 378, 480):
   - `expect_mode = "text"` 강제 (구조화/비구조화 분기 제거)
   - 호출 후 구조화 분석이면 parse_json_response로 파싱
   - 파싱 실패 → LLMSchemaError("AI 응답 형식 오류: ...") raise
   - max_retries=1, timeout_s=60 명시

4. 테스트:
   - 기존 17건 모두 PASS 유지
   - 신규 테스트 1건 추가: tests/test_ai_analyze_text_mode.py
     - mock_ai로 markdown fence 포함된 응답 주입 → analyze_paper가 정상 파싱 + dict 반환 검증
   - 18/18 PASS 확인

5. 산출물 docs/FIX_ANALYZE_SPEED_DONE.md:
   - 변경 파일 목록 + 라인
   - 분석 종류별 expect 변경 표 (before → after)
   - 신규 테스트 결과
   - 사용자 검증 가이드: "AI 전체 분석 버튼 → 1분 이내 완료 + 정상 결과" 확인 절차

## 제약
- Phase E 작업 금지 (Discovery / bootstrap)
- Phase D 작업 금지 (RELEVANCE_SYSTEM)
- 다른 분석 종류 (suggest_tags=schema, trend_analyze=text, review_draft=text)는 건드리지 말 것 — 이미 정상
- LLMError 글로벌 핸들러 변경 금지 — Phase C에서 끝남
- 마이그레이션 추가 금지

## 금지
- grammar mode를 다시 켜는 어떤 변경도 금지
- timeout을 다시 늘리는 변경 금지 (60s × 1이 강제 baseline)
- 사용자 승인 없이 모델 교체 금지 (gemma4:e4b 유지)

## 산출물
- ai.py 변경 (3개 함수)
- 시스템 프롬프트 강화
- 신규 테스트 1건
- docs/FIX_ANALYZE_SPEED_DIAGNOSIS.md (작업 전 진단)
- docs/FIX_ANALYZE_SPEED_DONE.md (작업 후 보고)
