@docs/PHASE_F_INTEGRATED_PLAN_v2.md 사용.

Phase F-0 베이스라인 측정부터 시작. 그 다음 F-1 → F-1.5 → F-2 순차 진행.

각 항목 끝나면:
1. 사양에 명시된 commit message로 git commit
2. pytest 실행 결과 보고
3. 사용자 검증 대기

특별 주의:
- F-1.2 마이그레이션 004: dry-run 프로토콜(사양 §3 F-1.2) 필수, 적용 전 사용자 승인 받기
  백업 파일명: data/backups/papers_pre_004_<YYYYMMDD_HHMMSS>.db
- F-1.4 datetime 치환: Column default는 반드시 lambda 패턴
  단순 datetime.now(timezone.utc) 치환 금지 (silent bug)
  적용 후 검증 스크립트(사양 §3 F-1.4) 실행
- F-2.2 폴더 드롭다운: 시작 전 paper 응답에 folder_id 포함되는지 확인. 
  없으면 paper_to_dict에서 추가 (사양 §F-2.2 사전 검증).
