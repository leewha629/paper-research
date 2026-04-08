역할: paper-research folders.py 폴더 이동 move semantics 적용.

## 우선순위 1 — 즉시 fix 필요
folder_papers에 UNIQUE(paper_id) INDEX가 이미 박혀있다 (uq_folder_papers_paper). folders.py의 INSERT가 IntegrityError로 깨지는 상태. 사용자 일상 워크플로(폴더 이동) 막힘. 즉시 fix.

## 문제
backend/routers/folders.py:131-138, 207-209의 폴더 이동/추가 라우터가 기존 폴더에서 paper를 빼지 않고 INSERT만 한다. UNIQUE INDEX와 충돌.

## 작업
backend/routers/folders.py의 모든 FolderPaper INSERT 지점을 move semantics로 교체:

1. INSERT 전: 같은 paper_id의 모든 기존 FolderPaper row DELETE
2. INSERT: 새 (folder_id, paper_id)
3. 단일 트랜잭션 (DELETE + INSERT 원자성)

또는 INSERT OR REPLACE 패턴을 SQLAlchemy로 — db.merge() 또는 raw SQL.

## 영향 라우터 (grep 기반)
- 138번 라인 부근 — 추가 라우터 (POST)
- 207-209번 라인 부근 — 이동 라우터 (PUT/PATCH)
- 기타 FolderPaper 생성하는 모든 곳 — grep으로 발견되는 것 모두

## 제약
- discovery.py는 이미 move semantics라 변경 금지
- folders.py:131-133의 existing 체크 (같은 폴더 중복 방지) 로직은 살리되, 다른 폴더 매핑도 같이 정리하도록 확장
- 트랜잭션 내 처리 (DELETE + INSERT 원자성)
- UNIQUE INDEX 추가/제거 금지 (이미 박혀있음)
- discovery.py 변경 금지

## 테스트
backend/tests/test_folder_papers_unique.py의 test_move_semantics_replaces_existing이 라우터 호출 시나리오까지 커버하는지 확인. 안 하면 신규 테스트 1건 추가:
- POST /api/folders/{id}/papers/{paper_id} 시 기존 다른 폴더 매핑이 DELETE됨

## 산출물
1. backend/routers/folders.py 수정
2. tests/test_folder_papers_unique.py에 라우터 시나리오 1건 추가 (필요시)
3. docs/FIX_FOLDER_MOVE_DONE.md — 변경 표 + 사용자 검증 가이드

## 검증 (FIX_FOLDER_MOVE_DONE.md 끝에 체크리스트)
- [ ] pytest -v → 기존 28 + Phase D deselected 4 + 신규 1건 PASS
- [ ] paper-research UI에서 임의 논문 폴더 이동 시도 → 성공
- [ ] sqlite로 중복 체크: SELECT paper_id, COUNT(*) FROM folder_papers GROUP BY paper_id HAVING COUNT(*) > 1; → 0건

## 금지
- UNIQUE INDEX 변경/제거 금지
- discovery.py 변경 금지
- 자동 마이그레이션 금지
- 사용자 승인 없이 paper 데이터 변경 금지