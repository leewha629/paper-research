역할: paper-research 사일런트 폴백 제거 + UI 표면화 구현자.

## 단일 진실원
- docs/REFACTOR_PLAN.md §"Phase C — 사일런트 폴백 제거 + UI 표면화"가 기본 사양이다.
- 단, Phase B에서 deferred된 2건이 Phase C에 흡수된다 (PHASE_B_DONE.md §4 deviation #2, #3 참조):
  - alerts._score_relevance를 strict_call로 마이그레이션 + 정규식 폴백 제거
  - ai_client.py:complete() 본문에서 retry/fallback 시맨틱 제거 + strict_call 위임으로 완전 전환

## 제약
- **Phase C 범위만 작업한다.** Phase D의 RELEVANCE_SYSTEM 프롬프트 개정 절대 금지.
- Phase A의 특성화 테스트 #5, #6, #7, #9는 **의도적으로 깨진다.** 깨진 후 Phase A.2의 #16~#21 (6건)으로 교체.
- 자동으로 Phase D 진입 금지. 멈춰라.

## 사용자 환경 사실
- 단일 사용자, 단일 워커 — staging branch dogfood는 본인이 직접 ollama 죽이고 검증
- multi-project 운영 예정 — alert 모델 변경 시 project_id 컬럼 영향 없는지 확인
- pydantic 2.5+ 확정

## 작업 순서
1. **백엔드 글로벌 에러 핸들러 등록** (`main.py`) — LLMError → 503 매핑
2. **search.py 3건 폴백 제거** (PLAN §C.2의 search.py:79-83, 363-375, 419-445)
3. **ai_client.py:complete() 본문 정리** (Phase B deferred #3) — strict_call 위임으로 완전 전환, 폴백 분기 제거
4. **alerts.py:281 _score_relevance를 strict_call로 마이그레이션** (Phase B deferred #2) — 정규식 폴백 제거
5. **alerts.py:241-254 폴백 제거** — Alert 생성 대신 logger.error + 실패 기록
6. **Phase A 특성화 테스트 #5, #6, #7, #9 → fail-loud 테스트로 교체** (PLAN §A.2의 #16~#21 6건 작성)
7. **Alert 모델 변경 결정** — `is_ai_failed` 컬럼 vs 별도 `AlertFailure` 테이블 vs 단순 로그. 사용자에게 결정 요청 후 진행. 기본 권장: `is_ai_failed: bool` 컬럼 (마이그레이션 1줄)
8. **마이그레이션 002 작성** (Alert 모델 변경 시) — `data/backups/`에 백업 후 적용
9. **프론트엔드 에러/경고 UI**:
   - `frontend/src/api/client.js`: 에러 응답 표준화 (`{error, detail, warning}` 파싱)
   - `frontend/src/pages/Search.jsx`: 503 빨간 배너 + 재시도 버튼
   - `frontend/src/pages/Search.jsx`: warning yellow 배너 (쿼리 확장 실패)
   - `frontend/src/pages/Alerts.jsx`: "AI 실패" 탭 또는 필터
   - `frontend/src/components/Common/StatusBadge.jsx`: 실패 상태 배지
10. **수동 검증 시나리오**:
    - `ollama` 프로세스 정지 → 검색 → 503 + 빨간 배너 확인
    - alerts cron 트리거 → DB에 score=5.0 Alert 생성 안 됨 확인
    - Discovery 1회 → 실패 명시 기록 확인

## Phase B deviation #4 (ai_score_papers expect="json") 검토
- Phase B에서 ai_score_papers가 expect="json"으로 마이그레이션됨 (Ollama format 파라미터 제약)
- Phase C 작업 시작 전: search.py:419-445의 호출부가 dict를 list로 어떻게 unwrap하는지 확인
- 만약 schema 검증이 빠져있다면, Phase C에서 호출부에 명시적 검증 추가 (pydantic으로 ScoredPaperList 검증)
- 결과를 PHASE_C_DONE.md §"deviation #4 후처리"에 기록

## 산출물
1. PLAN §C.2의 모든 백엔드 변경
2. Phase B deferred 2건 정리
3. 마이그레이션 002 (Alert 모델 변경 시)
4. 프론트엔드 변경 (PLAN §C.2의 5개 파일)
5. tests/test_search_helpers, test_alerts 업데이트 — Phase A의 #5,#6,#7,#9 → #16~#21 교체. Phase D 통합 테스트는 작성하지 마라
6. **`docs/PHASE_C_DONE.md` 새 파일** — 다음 내용 직접 Write:
   - 폴백 제거 4건 + Phase B deferred 2건 결과 표
   - 마이그레이션 002 적용 여부 + 백업 위치
   - pytest 결과 (Phase A에서 4건 깨져서 #16~#21 6건으로 교체된 후 → 총 17건 PASS 예상: A 6건 + B 5건 + C 6건)
   - 수동 검증 시나리오 결과
   - PLAN과 어긋난 결정
   - Phase D 진입 전 사용자 체크포인트 (PLAN §C.5의 5개 항목)

## 작성 방식
- 백엔드 → 테스트 교체 → 프론트엔드 순서로. 백엔드만 끝내고 본인 검증할 수 있게 단계별 commit.
- search.py 3건 폴백 제거 후 즉시 pytest. Phase A 특성화 테스트가 *깨지는지* 확인 (안 깨지면 Phase B 마이그레이션이 잘못된 것)
- 마이그레이션 002 적용 직전 사용자에게 알림 + 백업 확인 요청
- Alert 모델 변경 결정은 사용자 응답 대기

## 금지
- RELEVANCE_SYSTEM 프롬프트 변경 금지 (Phase D 일)
- Phase A의 #1, #2, #3, #4, #8, #10 테스트 건드리기 금지 (이건 안 깨져야 함)
- Phase B의 strict_call 시그니처 변경 금지
- Discovery 락 추가 금지 (Phase E 일)