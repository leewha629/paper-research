역할: paper-research 내 서재 리스트에 폴더 선택 드롭다운 추가.

## 목적
사용자가 논문 페이지 열지 않고 서재 리스트에서 직접 폴더 이동 가능하게. 특히 "휴지통으로 보내기"를 한 번 클릭으로.

## 변경 위치
- frontend/src/pages/Library.jsx — 리스트 아이템 렌더링 부분
- 현재 버튼 배치: [상세 보기] [미읽음 ▼] [삭제]
- 목표 배치: [상세 보기] [미읽음 ▼] [폴더 ▼] [삭제]

## 신규 드롭다운 — "폴더" 선택기
- 현재 논문이 속한 폴더를 기본값으로 표시
- 드롭다운 옵션: 현재 collection 내 모든 폴더 (검토 대기, 자동 발견, 풀분석 추천, 휴지통 등)
- 선택 시 즉시 이동 (저장 버튼 없음)
- 이동 성공 → 리스트에서 해당 아이템 업데이트 또는 제거 (현재 보고 있는 폴더에서 빠지면 제거)

## 백엔드 연결
- 기존 foldersAPI.movePaper(folder_id, paper_id) 사용 (AUDIT §7.2의 연결 대상)
- 또는 이미 연결돼있다면 그거 사용
- 호출 전 grep으로 확인: grep -n "movePaper\|move_paper" frontend/src/api/client.js backend/routers/folders.py

## 중요 — move semantics 검증
- Phase E에서 folders.py가 move semantics로 fix됐음 (DELETE + INSERT 원자성)
- 이 드롭다운이 그 라우터를 호출해야 함
- UNIQUE(paper_id) INDEX 있어서 잘못 호출하면 IntegrityError
- 호출 경로가 안전한지 확인

## UX 세부
- 드롭다운 너비는 다른 컨트롤과 어울리게 (너무 넓지 않게)
- 모바일/좁은 화면 고려
- 폴더 이름이 길면 truncate
- Collection별로 폴더 목록 다름 (CF4 collection과 CPN0 collection 폴더 구조 다를 수 있음) → 논문의 collection_id 기준으로 필터

## 테스트
- 기존 폴더 이동 테스트 (test_folder_papers_unique.py)가 이 경로도 커버하는지 확인
- 안 하면 신규 테스트 1건: Library 페이지에서 드롭다운 선택 시 fetch 호출 + 상태 업데이트 검증

## 산출물
1. frontend/src/pages/Library.jsx 수정
2. (필요시) frontend/src/api/client.js에 헬퍼 추가
3. docs/FIX_LIBRARY_FOLDER_SELECTOR_DONE.md — 변경 표 + 사용자 검증 가이드

## 검증 (DONE.md 끝에 체크리스트)
- [ ] 서재 리스트에서 폴더 드롭다운 보임
- [ ] 드롭다운 옵션이 현재 collection의 폴더 맞음
- [ ] 이동 성공 → 리스트 즉시 업데이트
- [ ] sqlite 중복 0건 재검증
- [ ] pytest -v 기존 통과 유지

## 금지
- 백엔드 라우터 변경 금지 (Phase E에서 fix 완료)
- UNIQUE INDEX 변경 금지
- 새로운 엔드포인트 추가 금지 (기존 movePaper 사용)
- 마이그레이션 추가 금지