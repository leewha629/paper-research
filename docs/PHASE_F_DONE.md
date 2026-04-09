# PHASE_F_DONE.md

## 완료일
(Phase F 전체 완료 시 기입)

## 적용된 commit
- `dd97148` F-0/F-1.1: 베이스라인 측정 + SQLite WAL 모드
- `86d7a64` F-1.2: eval_failed 버킷 + 마이그레이션 004
- `ce05144` F-1.3: pdfs.py path traversal 방어
- `a6613e9` F-1.4: deprecated API 정리 (lifespan + DeclarativeBase + datetime lambda + ai_client.py 삭제)

## 현재 상태
- pytest: 33건 통과 (아래 "테스트 수 변동" 참조)
- DB: 마이그레이션 004 적용
- WAL: 활성
- DeprecationWarning: 우리 코드 0건 (Pydantic class Config은 기존 이슈, F-1.4 범위 밖)
- 삭제 파일: backend/ai_client.py
- datetime: 모든 Column default lambda 패턴 적용 + 검증 스크립트 통과

## 테스트 수 변동 (37 → 33)

F-1.4에서 `backend/ai_client.py` 삭제에 따라 테스트 대상이 사라진 4건 제거:

| 제거 테스트 | 파일 | 사유 |
|---|---|---|
| test_complete_returns_text_when_expect_json_false (#1) | test_ai_client_contract.py | AIClient.complete 직접 테스트 — 대상 삭제 |
| test_complete_retries_on_invalid_json_when_expect_json_true (#2) | test_ai_client_contract.py | 〃 |
| test_complete_returns_raw_text_after_max_retries (#3) | test_ai_client_contract.py | 〃 |
| test_legacy_ai_client_complete_delegates_to_strict_call (#15) | test_strict_call.py | AIClient.complete 존재 contract — 대상 삭제 |

**판단 근거**: 사양 §F-1.4는 ai_client.py 삭제를 명시하나 테스트 제거는 명시하지 않음. 테스트 대상 모듈이 삭제되어 실행 자체가 불가하므로 자체 판단으로 제거. `parse_json_response` 테스트(#4)는 `services/llm/router.py`로 이전하여 보존.

**보존된 커버리지**: `call_llm` 경로는 기존 테스트 (test_strict_call #10~#13, test_search_helpers, test_alerts_score 등)가 커버. `parse_json_response`는 test_ai_client_contract #4가 계속 커버.

## 성능 변화 (베이스라인 대비)
| 측정 항목 | Before (F-0) | After (F 완료) | 변화 |
|---|---|---|---|
| (Phase F 전체 완료 시 측정) | | | |

## Phase F 중 발견, 미해결 이슈
- ai_client.py import 사이트가 사양 예상(0~1건)보다 많았음(8건). 라우터 3개 + 테스트 5개. 전수 마이그레이션 완료.
- `pytest -W error::DeprecationWarning` 실행 시 pymupdf segfault + Pydantic class Config 경고 발생. 둘 다 기존 이슈이며 F-1.4 범위 밖.

## 다음 세션 작업
- F-1.5 코드 위생

## 학습/회고
- (Phase F 전체 완료 시 기입)
