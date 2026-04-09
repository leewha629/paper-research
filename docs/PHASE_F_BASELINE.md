# Phase F 베이스라인 측정

> 측정일: 2026-04-09
> Phase F 적용 전 수치. 완료 후 PHASE_F_DONE.md에서 before/after 비교용.

## API 응답 시간
```
GET /api/papers:  0.109s
GET /api/folders: 0.005s
```

## DB 상태
```
papers.db:      2.6M
journal_mode:   delete
papers:         77
folders:        5
folder_papers:  50
collections:    2
```

## 서버 프로세스
```
PID: 82408  RSS: 5.6 MB
```

## pytest
```
29 passed, 4 deselected in 1.06s
```
