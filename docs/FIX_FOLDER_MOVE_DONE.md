# FIX: folders.py 폴더 이동 move semantics 적용 — 완료 보고

- **일자**: 2026-04-08
- **브랜치**: main
- **사양**: `.claude/prompts/fix_folder_move_semantics.md`

## 배경 — 왜 깨졌나

`data/papers.db`에는 Phase E 마이그레이션 이후 두 개의 UNIQUE 인덱스가 걸려 있다.

```
CREATE UNIQUE INDEX uq_folder_papers_folder_paper ON folder_papers(folder_id, paper_id);
CREATE UNIQUE INDEX uq_folder_papers_paper        ON folder_papers(paper_id);
```

두 번째 인덱스(`uq_folder_papers_paper`)는 "한 논문은 동시에 한 폴더에만 속한다"는
강한 불변을 DB 레벨에서 강제한다. 그런데 `backend/routers/folders.py` 의 라우터들은
이 불변을 모른 채 기존 폴더 매핑을 빼지 않고 새 매핑을 INSERT 하려고 했고,
그 결과 사용자 일상 워크플로(논문 폴더 이동) 가 IntegrityError 로 막혀 있었다.

- `POST /api/folders/{id}/papers` — 다른 폴더에 이미 매핑된 논문을 추가하면 즉시 IntegrityError
- `PUT /api/folders/{id}/move` — 원본/대상이 아닌 제3 폴더에 잔재가 있으면 복구 불가
- `discovery.py` 는 이미 move semantics 라 문제없음 (변경 금지 대상)

## 변경 표

| 위치 | Before | After |
|---|---|---|
| `backend/routers/folders.py` `add_paper_to_folder` (POST `/api/folders/{id}/papers`) | `existing`이 같은 폴더에 있는지만 체크 후 INSERT | 같은 폴더면 멱등 no-op. 아니면 **paper_id 에 대한 모든 기존 매핑 DELETE → 새 INSERT** 를 단일 트랜잭션으로 처리 |
| `backend/routers/folders.py` `move_paper_between_folders` (PUT `/api/folders/{id}/move`) | 원본에서 삭제 후 대상으로 `fp.folder_id = target` UPDATE, 대상에 이미 있으면 원본만 삭제 | 원본 유효성은 유지(에러 메시지). source == target no-op. 그 외에는 **paper_id 에 대한 모든 기존 매핑 DELETE → target 에 새 INSERT** 를 단일 트랜잭션으로 처리 |
| `backend/tests/test_folder_papers_unique.py` | 2건 (DB-level UNIQUE + move semantics 흉내) | + `test_router_add_paper_move_semantics` 1건 추가 (실제 라우터 호출로 A→B 이동 검증) |

### 핵심 스니펫

```python
# add_paper_to_folder (folders.py)
db.query(FolderPaper).filter(
    FolderPaper.paper_id == paper_id,
).delete(synchronize_session=False)
db.add(FolderPaper(paper_id=paper_id, folder_id=id))
db.commit()
```

```python
# move_paper_between_folders (folders.py)
db.query(FolderPaper).filter(
    FolderPaper.paper_id == paper_id,
).delete(synchronize_session=False)
db.add(FolderPaper(folder_id=target_folder_id, paper_id=paper_id))
db.commit()
```

DELETE + INSERT 는 같은 `db` 세션(SQLAlchemy 기본 트랜잭션) 안에서 실행된 뒤
단일 `commit()` 으로 반영되므로 원자성이 보장된다. 중간에 예외가 나면 세션 롤백 시
두 변경 모두 취소된다.

## 제약 준수

- [x] `discovery.py` 변경 없음
- [x] DB UNIQUE 인덱스 추가/제거 없음 (`uq_folder_papers_paper` 그대로)
- [x] 마이그레이션 파일 수정 없음
- [x] 기존 `folders.py:131-133` 의 "같은 폴더 중복 방지" 멱등 동작 유지 (`existing_same` 체크)
- [x] `models.py` 그대로 (ORM 레벨 UNIQUE 선언은 `(folder_id, paper_id)` 만이며, 이는
      DB 에서 별도로 박힌 `paper_id` UNIQUE 와 충돌하지 않는다)

## 테스트 결과

```
$ cd backend && ../venv/bin/python -m pytest -q
.............................                                            [100%]
29 passed, 4 deselected in 0.98s
```

- 기존 28건 유지
- Phase D integration 4건 deselected (변동 없음)
- 신규 `test_router_add_paper_move_semantics` 1건 PASS

신규 테스트는 FastAPI `TestClient` 로 `POST /api/folders/{B}/papers` 를 호출해
폴더 A 에 있던 논문이 DELETE → 폴더 B 로 INSERT 되는지를 라우터 레벨에서 검증한다.

> 주: in-memory SQLite 테스트 DB 에는 paper_id-only UNIQUE 가 없다 (ORM 선언에 없기 때문).
> 따라서 이 테스트는 "IntegrityError 가 안 나는지" 가 아니라 "A 매핑이 실제로 사라지고
> B 매핑만 남는지" 를 기능적으로 검증한다. DB 레벨 UNIQUE 충돌은 기존
> `test_move_semantics_replaces_existing` 에서 별도로 커버된다.

## 검증 체크리스트

- [x] `cd backend && ../venv/bin/python -m pytest -v` → 29 passed, 4 deselected
- [ ] paper-research UI 에서 임의 논문을 폴더 A → 폴더 B 로 드래그 → 성공 (사용자 검증 필요)
- [x] `sqlite3 data/papers.db "SELECT paper_id, COUNT(*) FROM folder_papers GROUP BY paper_id HAVING COUNT(*) > 1;"` → 0건

## 사용자 검증 가이드

1. 백엔드 재시작: `cd backend && ../venv/bin/python main.py` (또는 기존 실행 방식)
2. 프론트에서 임의 논문 하나를 폴더 A 에 확인
3. 같은 논문을 폴더 B 로 드래그 & 드롭 (또는 "폴더 이동" 메뉴)
4. 기대:
   - 성공 응답 (에러 토스트 없음)
   - 폴더 A 에서 사라지고 폴더 B 에 나타남
   - 새로고침 후에도 유지
5. 시스템 폴더 (자동 발견 / 풀분석 추천 / 검토 대기 / 휴지통) 간 이동도 동일하게 동작

## 후속 작업 (이 PR 범위 밖)

- `models.py` 의 `FolderPaper.__table_args__` 에 `UniqueConstraint("paper_id", name="uq_folder_papers_paper")`
  선언을 추가해 ORM 과 live DB 스키마를 일치시키는 것을 고려할 수 있음.
  단, 이 경우 in-memory 테스트 DB 에도 같은 UNIQUE 가 생겨 `test_duplicate_paper_in_two_folders_blocked`
  시나리오의 첫 INSERT 가 실패할 수 있으므로 테스트 재설계 필요. 지금 사양은
  "UNIQUE INDEX 변경 금지" 이므로 이번 PR 에서는 손대지 않았다.
- `discovery.py` 의 move semantics 는 시스템 폴더 4종만 타겟으로 DELETE 하지만,
  DB 레벨 UNIQUE(paper_id) 가 박힌 지금은 사실상 "paper_id 전체" 로 확장해도 안전하다.
  현재 사양상 건드리지 않음.
