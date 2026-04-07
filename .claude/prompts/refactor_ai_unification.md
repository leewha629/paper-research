역할: paper-research AI 호출 단일화 구현자 (strict_call 도입).

## 단일 진실원
- docs/REFACTOR_PLAN.md §"Phase B — AI 호출 단일화 (`strict_call`)"가 유일한 사양이다.
- docs/PHASE_A_DONE.md §3의 테스트 표를 참고해 "어떤 동작이 잠겨 있는지" 인지하라. Phase B에서는 그 잠금을 깨면 안 된다.

## 제약
- **Phase B 범위만 작업한다.** Phase C의 fail-loud 폴백 제거 절대 금지. 폴백은 호출부에 그대로 둔다.
- Phase A의 10개 테스트가 모두 그대로 통과해야 한다 (특성화 테스트 포함). 깨지면 Phase B 작업 잘못된 것이다.
- 작업 종료 후 자동으로 Phase C로 진행하지 말 것. 멈춰라.

## 사용자 환경 사실 (확정됨)
- pydantic >= 2.5.0 설치됨 (requirements.txt 확인 완료) → schema 검증 그대로 사용
- 단일 워커 (uvicorn --reload, --workers 없음) → HTTP 멀티워커 race는 잠재 위협
- multi-project 운영 예정 (CF₄/CPN/AI/3D 모델링 등) → strict_call은 project_id 인지 불필요지만, 호출부 어댑터는 향후 확장 고려
- iCloud 동기화 아님 → 파일 경로 자유

## 작업 순서
1. PLAN §B.1의 strict_call 시그니처 그대로 구현 (`backend/services/llm/ollama_client.py`)
2. PLAN §B.2의 신규 모듈 6개 생성 (services/llm/__init__.py, ollama_client.py, claude_client.py, router.py, exceptions.py, schemas.py)
3. PLAN §B.3의 호출 사이트 16개를 표 순서대로 마이그레이션
   - **각 사이트마다 별도 commit으로 분리** (롤백 단위)
   - 1번부터 시작. 각 사이트 끝날 때마다 `pytest -v` 실행해 Phase A 10건 + Phase B 신규 5건 모두 PASS 확인
   - 한 사이트라도 PASS 깨지면 그 사이트만 revert하고 멈춰서 사용자에게 보고
4. PLAN §A.2의 "Phase B 종료 시 추가 (5건)" 테스트 #11~#15 작성 — strict_call 동작 자체 검증
5. ai_client.py를 strict_call로 위임하는 어댑터로 만들기. **단, 폴백 분기는 그대로 유지** (Phase C가 제거)

## Risk #1 대응 (PLAN M.2 §위험 #1)
- 작업 시작 직후 가장 먼저: `grep -rn "client\.complete\|ai_client\.complete" backend/` 실행해 모든 unpacking 패턴 조사
- `(text, prompt_tokens, completion_tokens)` 형태로 unpacking하는 호출부가 있으면 어댑터를 `(text, 0, 0)` 자리표시자 튜플 반환으로 처리
- 결과를 PHASE_B_DONE.md §"호출 사이트 분석"에 표로 기록

## 산출물
1. PLAN §B.2의 모든 파일
2. ai_client.py 어댑터 수정
3. 호출 사이트 16개 마이그레이션 (각각 commit 분리)
4. tests/test_strict_call.py (5건)
5. **`docs/PHASE_B_DONE.md` 새 파일** — 다음 내용 직접 Write:
   - strict_call 시그니처 최종본 (코드블럭)
   - 호출 사이트 16개 마이그레이션 결과 표 (사이트, 어떤 expect, 어떤 schema, 검증 통과 여부)
   - Risk #1 대응 결과 — unpacking 호출부 발견 여부, 어댑터 처리 방식
   - Phase A 10건 + Phase B 5건 = 15건 pytest 결과
   - PLAN과 어긋난 결정 (있으면)
   - Phase C 진입 전 사용자 체크포인트 (PLAN §B.5의 5개 항목 그대로)

## 작성 방식
- 사이트 1개 마이그레이션할 때마다 즉시 commit + 테스트 실행. 메모리에 16개 모았다가 한 번에 쓰지 마라.
- Phase B는 가장 광범위한 변경 단계. 컨텍스트 폭발 위험 매우 높음 — 사이트 4개 정도 끝날 때마다 사용자에게 /compact 권장 알림

## 금지
- 폴백 제거 금지 (Phase C 일)
- Phase A 테스트 깨기 금지 — 깨지면 Phase B 자체가 실패
- 사용자 승인 없이 ai_client.py의 폴백 분기 변경 금지
- 새로운 분석 종류 추가 금지 (마이그레이션만)