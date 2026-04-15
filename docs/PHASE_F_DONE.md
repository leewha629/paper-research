# PHASE_F_DONE.md

## 완료일
2026-04-10 (작업), 2026-04-15 (문서 마무리)

## 적용된 commit
- `dd97148` F-0/F-1.1: 베이스라인 측정 + SQLite WAL 모드
- `86d7a64` F-1.2: eval_failed 버킷 + 마이그레이션 004
- `ce05144` F-1.3: pdfs.py path traversal 방어
- `a6613e9` F-1.4: deprecated API 정리 (lifespan + DeclarativeBase + datetime lambda + ai_client.py 삭제)
- `43cc9e9` Docs: Phase F 통합 사양 v2 + 통합 CLAUDE.md + 발사 프롬프트
- `f248cd5` F-1.5: Pydantic 입력 스키마 (라우터 입력 typed + Config v2 마이그레이션)
- `cb472ae` docs: PHASE_F_DONE.md F-1.5 커밋 해시 + 테스트 수 업데이트
- `fa3c2e4` F-2.0/F-2.1: 죽은 API 정리 (getPrompt/createPrompt 삭제)
- `a9b0167` F-2.2: Library 폴더 드롭다운 (folder_id 응답 보강 + handleMove)
- `6996549` F-2.3: PaperDetail 분석 이력 탭 (getAnalyses 연결)
- `5f90dc5` F-2.4: Dashboard heartbeat 폴링 (agentStatus 연결 + 실시간 표시)
- `e2f5483` fix: Library 컴팩트 뷰에도 폴더 드롭다운 추가 (F-2.2 보완)
- `18ccc57` Phase F 마무리: folders.py created_at None 가드 + PHASE_F_DONE 갱신 + gitignore

## 현재 상태
- pytest: 36건 통과 (기존 28 → F-1.2 +2, F-1.3 +3, F-1.1 +1, F-1.5 +3 = +9 신규. F-1.4에서 AIClient 직접 테스트 4건 제거로 37→33→36)
- DB: 마이그레이션 004 적용 (is_eval_failed, eval_failure_reason, eval_retry_count 컬럼 + "평가 실패" 시스템 폴더)
- WAL: 활성 (`PRAGMA journal_mode;` → `wal`)
- DeprecationWarning: 우리 코드 0건 (F-1.5에서 schemas.py `class Config` → `model_config = ConfigDict(...)` 마이그레이션 완료. 외부 의존성 pymupdf segfault만 잔존, F 범위 밖)
- 삭제 파일: backend/ai_client.py
- datetime: 모든 Column default → `lambda: datetime.now(timezone.utc)` 패턴 적용 + 검증 스크립트 통과

## 테스트 수 변동 (37 → 33 → 36)

F-1.4에서 `backend/ai_client.py` 삭제에 따라 테스트 대상이 사라진 4건 제거:

| 제거 테스트 | 파일 | 사유 |
|---|---|---|
| test_complete_returns_text_when_expect_json_false (#1) | test_ai_client_contract.py | AIClient.complete 직접 테스트 — 대상 삭제 |
| test_complete_retries_on_invalid_json_when_expect_json_true (#2) | test_ai_client_contract.py | 〃 |
| test_complete_returns_raw_text_after_max_retries (#3) | test_ai_client_contract.py | 〃 |
| test_legacy_ai_client_complete_delegates_to_strict_call (#15) | test_strict_call.py | AIClient.complete 존재 contract — 대상 삭제 |

**판단 근거**: 사양 §F-1.4는 ai_client.py 삭제를 명시하나 테스트 제거는 명시하지 않음. 테스트 대상 모듈이 삭제되어 실행 자체가 불가하므로 자체 판단으로 제거. `parse_json_response` 테스트(#4)는 `services/llm/router.py`로 이전하여 보존.

**보존된 커버리지**: `call_llm` 경로는 기존 테스트 (test_strict_call #10~#13, test_search_helpers, test_alerts_score 등)가 커버. `parse_json_response`는 test_ai_client_contract #4가 계속 커버.

## 사용자 검증 결과 (2026-04-10)

| 항목 | 결과 | 비고 |
|---|---|---|
| WAL 활성 | ✅ | `PRAGMA journal_mode;` → `wal` |
| eval_failed 폴더 | ✅ | `SELECT name FROM folders WHERE name='평가 실패';` → 1건 |
| ai_client.py 삭제 | ✅ | `ls ai_client.py` → No such file |
| datetime lambda 검증 | ✅ | p1/p2 시각 다름 확인, 16건 전부 lambda 패턴 |
| Library 폴더 드롭다운 | ✅ | paper_id=134 이동 → folder_id=4 단 1건 (UNIQUE 만족) |
| PaperDetail 분석 이력 탭 | ✅ | paper_id 94(기존 분석 5건) → 시간순 목록 정상 표시 |
| Dashboard heartbeat | ✅ | Discovery 사이클 실행 → "실행 중" 표시 → 완료 후 복귀 |
| Discovery 사이클 | ✅ | 후보 40 / 신규 35 / 추천 2 / 저장 3 / 휴지통 32 / 196s |
| path traversal 방어 | ✅ | pytest test_path_traversal 5건 통과 |
| Pydantic 422 | ✅ | pytest test_pydantic_input 3건 통과 |

## 성능 변화 (베이스라인 대비)
| 측정 항목 | Before (F-0) | After (F 완료) | 변화 |
|---|---|---|---|
| papers 건수 | 77 | 112 | +35 (Discovery 사이클 1회) |
| folders 건수 | 5 | 6 | +1 ("평가 실패") |
| folder_papers 건수 | 50 | 85 | +35 |
| WAL 모드 | delete | wal | ✅ |
| pytest | 28+4 | 36+4 | +8 |

## Phase F 중 발견, 미해결 이슈

1. **ai_client.py import 사이트 8건**: 사양 예상(0~1건)보다 많았음. 라우터 3개 + 테스트 5개. 전수 마이그레이션 완료.

2. **마이그레이션 004 "평가 실패" 폴더 created_at NULL**: INSERT에서 created_at 누락. folders.py에서 `NoneType.isoformat` → 500 에러 발생. `UPDATE folders SET created_at=datetime('now') WHERE created_at IS NULL` 응급처치 + folders.py None 가드 추가 (`18ccc57`).

3. **pymupdf segfault**: `pytest -W error::DeprecationWarning` 실행 시 pymupdf C extension segfault. 외부 의존성 이슈, F 범위 밖. 일반 pytest 실행은 정상.

4. **Mac mini ollama stuck**: gemma4:e4b 단일 분석 도중 ollama runner stuck (CPU 13.9%, status U, 10분+ 무응답). ollama 재시작으로 복구. 운영 시 RTX 5080 데스크탑(Tailscale 100.80.119.78) + OLLAMA_URL 분리 권장.

5. **frontend "분석 중" stale 상태**: backend LLMError 503 응답 후 frontend "일괄 분석 진행" 상태가 자동 클리어 안 됨. 브라우저 새로고침으로 우회. UX 미흡, F 범위 밖.

6. **Library 폴더 드롭다운 뷰 누락**: 클로드 코드가 리스트 뷰에만 박고 컴팩트 뷰 누락. 사용자 검증에서 발견, `e2f5483`로 보완.

## 다음 작업
- FUTURE_ROADMAP_v2.md 참조 (Phase G: 외부 도구 통합 스프린트)
- Phase F 부록: ollama backend 원격화 (RTX 5080)
- Phase G 시작 결정 (paper-qa 통합)

## 학습/회고

1. **cross-check 패턴이 silent bug 1건 잡음**: F-1.4 datetime Column default lambda 패턴. 본 세션이 못 봤는데 다른 Claude 세션의 평가(논문계획3.md §1)가 잡음. Phase D RELEVANCE_SYSTEM cross-check 패턴이 이번에도 가치 입증.

2. **사용자 디버깅 본능 정확히 발동**: F-1.4 진행 중 본인이 "휙휙 넘어가는 것 같다"고 의심하고 클로드 코드 정지. 결과적으로 main.py 중간 끊김 상태(app = FastAPI 선언 누락) 발견. 본능이 빗나갔어도(silent bug 아님) 멈춘 것 자체가 가치.

3. **사양 vs 실행 분리**: PHASE_F_INTEGRATED_PLAN_v2.md를 docs/에, 발사 프롬프트를 .claude/prompts/에 분리. Phase A~E 영구 규칙 §12.A.2 패턴 정확히 따름.

4. **외부 도구 통합 결정 타당성 재확인**: 다른 세션 Claude가 search.py 분리를 G 선행으로 주장했지만 본 세션이 거부. 본인 "직접 구현 안 함" 원칙과 일관 적용. 거부 근거는 REVIEW_FROM_OTHER_SESSION.md에 기록 보존.

5. **운영 한계 직접 체감**: Mac mini 16GB + gemma4:e4b 단일 분석 stuck + 발열 65°C. RTX 5080 원격화 필요성을 운영 1편으로 즉시 발견. FUTURE_ROADMAP의 "ollama 원격화" 트리거가 명확해짐.

6. **마이그레이션 dry-run 프로토콜 가치**: Phase E 사고(UNIQUE 컬럼 spec 오류) 패턴 재발 방지용으로 도입. F-1.2에서 실전 적용. dry-run이 SQL syntax/integrity는 잡지만 의미적 spec 오류(created_at 누락 같은)는 못 막음. → 사용자 검증 시나리오와 조합해야 완전.

---

> Phase A: 10 tests, 0 infra
> Phase E: 28 tests, fcntl lock, heartbeat, ACID, UNIQUE
> Phase F: 36 tests, WAL, eval_failed, path traversal, Pydantic, lifespan, datetime lambda, Library 드롭다운, 분석 이력, heartbeat UI
