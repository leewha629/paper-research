역할: paper-research 회귀 테스트 스캐폴딩 구현자.

## 단일 진실원
- docs/REFACTOR_PLAN.md §"Phase A — 회귀 테스트 스캐파딩"이 유일한 사양이다.
- AUDIT_2026Q2.md는 배경 참고용. 작업 결정의 근거는 PLAN에만 둔다.

## 제약
- **Phase A 범위만 작업한다.** Phase B~F의 어떤 파일도 건드리지 말 것.
- PLAN에 없는 추가 테스트, 추가 픽스처, 추가 인프라 만들지 말 것.
- 산출물 종료 후 자동으로 Phase B로 진행하지 말 것. 멈춰라.

## 작업 순서
1. PLAN §A.1의 신규 파일 12개를 모두 생성한다 (pytest.ini, conftest.py, fixtures/, test_*.py 4개)
2. PLAN §A.2의 "Phase A에서 작성 (10건)" 테스트를 모두 구현한다. 번호 #1~#10
3. **현재 버그 동작을 그대로 캡처하는 특성화 테스트(#5, #6, #7, #9)는 의도적으로 현재 폴백 동작을 PASS로 만든다.** Phase C에서 교체될 예정. 이 테스트들이 "잠그는 동작"이 PLAN에 명시된 그대로인지 확인.
4. requirements.txt에 pytest, pytest-asyncio, httpx 추가
5. `cd backend && pytest -v` 실행 → 10건 모두 PASS 확인
6. 네트워크 차단 검증: mock 픽스처가 실제 ollama/s2를 호출하지 않는 것을 확인하기 위해 `pytest --disable-socket` 또는 환경변수로 동등 효과 시도. 안 되면 mock_ai 픽스처가 monkeypatch로만 동작하는지 코드 리뷰

## 멀티 프로젝트 고려 (사용자 추가 요구사항)
- paper-research는 multi-project로 운영된다 (CF₄/CPN/AI/3D 모델링 등).
- conftest.py의 DB 픽스처에 `project_id` 파라미터를 받을 수 있는 형태로 설계하라.
- sample_papers.py 픽스처는 분야 태그를 함께 가지도록 (CF₄/할로겐/VOC/AI/3D/무관).
- Phase A에서는 픽스처 구조만 준비. 실제 multi-project 격리 검증은 Phase E.

## 산출물
1. PLAN §A.1의 12개 파일
2. requirements.txt 수정
3. **`docs/PHASE_A_DONE.md` 새 파일** — 다음 내용 직접 Write:
   - 생성한 파일 목록 (실제 라인 수 포함)
   - `pytest -v` 출력 (PASS/FAIL 표)
   - 10개 테스트가 각각 어떤 현재 동작을 잠그고 있는지 한 줄씩 (#5, #6, #7, #9는 "버그 캡처"로 명시)
   - PLAN과 어긋난 결정이 있다면 그 사유 (없으면 "없음")
   - 다음 Phase로 넘어가기 전 사용자 체크포인트 (PLAN §A.4의 5개 항목 그대로 체크리스트)

## 작성 방식
- 파일 하나 만들면 즉시 Write. 메모리에 모았다가 한 번에 쓰지 마라.
- 컨텍스트 폭발 위험 작업이라 중간에 /compact 권장 (사용자에게 알릴 것).

## 금지
- Phase B의 strict_call 미리 만들기 금지
- Phase C의 fail-loud 폴백 제거 금지
- Phase A 범위 외 파일 편집 금지
- 사용자 승인 없이 마이그레이션 적용 금지 (Phase A는 마이그레이션 없음)