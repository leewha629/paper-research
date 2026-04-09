# Phase F 통합 사양 v2 (Integrated Plan)

> 작성일: 2026-04-09 (v2)
> v1 → v2 변경: 다른 세션 Claude의 평가(논문계획3.md) 중 F 관련 5건 패치 반영
> 컨텍스트: PHASE_E 완료 후, 두 번째 세션에서 작성
> 입력: (1) 이 세션 Phase F 초안, (2) 다른 세션 Opus의 "논문계획2.md" Phase F~K, (3) 본인 사전 검증 grep 3건, (4) 다른 세션 Claude의 v1 평가 "논문계획3.md"
> 결정: 두 계획 통합 → Phase F를 F-1 / F-1.5 / F-2 세 단계로 분할
> 다음 세션 작업: 본 사양 → Claude Code로 실행

---

## v1 → v2 변경 사항 요약

| # | 패치 | 적용 위치 | 출처 |
|---|---|---|---|
| 1 | datetime lambda 패턴 명시 | §F-1.4 | 논문계획3.md §1 |
| 2 | 마이그레이션 dry-run 프로토콜 | §F-1.2 | 논문계획3.md §2 |
| 3 | 성능 베이스라인 측정 | §F-0 (신규) | 논문계획3.md §5 |
| 4 | F-2.2 folder_id 응답 검증 | §F-2.2 | 논문계획3.md 본문 평가 |
| 5 | PHASE_F_DONE.md 템플릿 | §13 (확장) | 논문계획3.md §8 |

**v2에 반영하지 않은 항목** (G로 이연 또는 거부):
- 논문계획3.md §3 search.py 분리 → **거부**. 본인 결정 "직접 구현 안 함" 원칙과 모순. paper-qa는 별도 라우터로 추가하므로 search.py 리팩토링 불필요. 자세한 거부 근거는 REVIEW_FROM_OTHER_SESSION.md 참조.
- 논문계획3.md §4 paper-qa 동기화 전략 → FUTURE_ROADMAP v2로 이연
- 논문계획3.md §6 RAG graceful degradation → FUTURE_ROADMAP v2로 이연
- 논문계획3.md §7 외부 dep 버전 고정 → FUTURE_ROADMAP v2로 이연

---

## 0. 사전 검증 결과 (2026-04-09 grep 3건)

### F.3 — discovery.py HOLD_SCORE 폴백: ✅ 잔존 확정
```
backend/services/research_agent/discovery.py
  48: HOLD_SCORE = 4
  58: if score == HOLD_SCORE:    # 분기 처리
  277: score = HOLD_SCORE         # ← 폴백 대입 (Phase C에서 누락)
```
→ Phase C에서 search.py/alerts.py만 잡고 discovery.py 내부 폴백은 안 건드림.
   LLM 실패 시 score=4로 떨어져서 "검토대기" 폴더에 묻힘. 사용자 화면에 평가 실패가 안 보임.
   **Phase C의 fail-loud 원칙 위반. F-1에서 박는다.**

### F.4 — pdfs.py path traversal: ⚠️ 약한 취약점 확정
```
backend/routers/pdfs.py
  save_path = os.path.join(PDF_DIR, f"{paper.paper_id}.pdf")
  save_path = os.path.join(PDF_DIR, f"{paper.paper_id}_manual.pdf")
```
- `paper.paper_id`는 DB에서 옴 (직접 사용자 입력 아님)
- S2 paperId는 보통 SHA hex라 일반 케이스 안전
- **but** sanitize 0건. import 기능 / 수동 INSERT / BibTeX import 등으로 악성 paper_id 들어오면 path escape 가능
- 본인 환경(단일 사용자/로컬)에선 실질 위험 낮음
- **fix는 5줄. 방어 깊이 차원에서 박는다. F-1 채택.**

### F.1 — papers.py N+1: ✅ 사실, 우선순위 낮음
```
backend/routers/papers.py
  joinedload/selectinload 0건
```
→ 50건 규모에선 체감 거의 없음. **본 Phase에서 보류. 100~200건 임계 전에 박는다.**
   "FUTURE_ROADMAP.md → 보류 항목"으로 분리.

---

## 1. Phase F 분할 구조

```
Phase F-0 "베이스라인 측정" (10분)         ← v2 신규
  └─ 현재 성능/DB 상태 기록 (전후 비교용)

Phase F-1 "위생/보안 스프린트" (1~2일)
  ├─ F-1.1 SQLite WAL
  ├─ F-1.2 discovery.py eval_failed 버킷 + 마이그레이션 004 (dry-run 포함)
  ├─ F-1.3 pdfs.py path traversal 방어
  ├─ F-1.4 deprecated API 정리 (lifespan, DeclarativeBase, datetime lambda, ai_client.py 삭제)
  └─ F-1.5 코드 위생

Phase F-1.5 "Pydantic 입력 스키마" (반나절~1일, 별도 commit)
  └─ F-1.6 POST/PUT 엔드포인트 dict → Pydantic

Phase F-2 "UI 통합" (1일)
  ├─ F-2.0 죽은 API 6개 결정 (grep 검증 후)
  ├─ F-2.1 createPrompt/getPrompt 처리
  ├─ F-2.2 Library 폴더 드롭다운 (사용자 명시 요청, folder_id 응답 선행 확인)
  ├─ F-2.3 PaperDetail 분석 이력 탭
  └─ F-2.4 Dashboard heartbeat 폴링
```

**보류 (FUTURE_ROADMAP.md로 분리)**:
- F.1 N+1 + 페이지네이션 (collection 100~200건 임계 전)
- Phase G/H/I/J/K 전체

**Phase 간 의존**: F-0 → F-1 → F-1.5 → F-2 (순차). 각 단계 끝나면 사용자 검증 체크포인트.

---

## 2. Phase F-0: 베이스라인 측정 (v2 신규)

> 출처: 논문계획3.md §5
> 목적: F 적용 전후 비교 가능하게 수치 기록. 10분 작업.
> 결과물: `docs/PHASE_F_BASELINE.md`

### 측정 항목

```bash
cd ~/paper-research

# 1. API 응답 시간 (서버 띄운 상태에서)
echo "## API 응답 시간" > docs/PHASE_F_BASELINE.md
echo '```' >> docs/PHASE_F_BASELINE.md
{ time curl -s http://localhost:7010/papers -o /dev/null; } 2>> docs/PHASE_F_BASELINE.md
{ time curl -s http://localhost:7010/folders -o /dev/null; } 2>> docs/PHASE_F_BASELINE.md
{ time curl -s "http://localhost:7010/search/stream?query=CeO2&collection_id=1" -o /dev/null; } 2>> docs/PHASE_F_BASELINE.md
echo '```' >> docs/PHASE_F_BASELINE.md

# 2. DB 상태
echo "## DB 상태" >> docs/PHASE_F_BASELINE.md
echo '```' >> docs/PHASE_F_BASELINE.md
ls -lh data/papers.db >> docs/PHASE_F_BASELINE.md
sqlite3 data/papers.db "SELECT 'papers', COUNT(*) FROM papers;" >> docs/PHASE_F_BASELINE.md
sqlite3 data/papers.db "SELECT 'folders', COUNT(*) FROM folders;" >> docs/PHASE_F_BASELINE.md
sqlite3 data/papers.db "SELECT 'folder_papers', COUNT(*) FROM folder_papers;" >> docs/PHASE_F_BASELINE.md
sqlite3 data/papers.db "SELECT 'collections', COUNT(*) FROM collections;" >> docs/PHASE_F_BASELINE.md
sqlite3 data/papers.db "PRAGMA journal_mode;" >> docs/PHASE_F_BASELINE.md
echo '```' >> docs/PHASE_F_BASELINE.md

# 3. 서버 메모리
echo "## 서버 프로세스" >> docs/PHASE_F_BASELINE.md
echo '```' >> docs/PHASE_F_BASELINE.md
ps aux | grep uvicorn | grep -v grep | awk '{print "RSS:", $6/1024, "MB"}' >> docs/PHASE_F_BASELINE.md
echo '```' >> docs/PHASE_F_BASELINE.md

# 4. pytest baseline
echo "## pytest" >> docs/PHASE_F_BASELINE.md
echo '```' >> docs/PHASE_F_BASELINE.md
cd backend && pytest --tb=no -q >> ../docs/PHASE_F_BASELINE.md 2>&1
cd ..
echo '```' >> docs/PHASE_F_BASELINE.md
```

**기록**: `docs/PHASE_F_BASELINE.md`. Phase F 완료 후 동일 측정해서 PHASE_F_DONE.md에 before/after 표 작성.

---

## 3. Phase F-1: 위생/보안 스프린트

> 원칙: 기존 동작 유지 + fail-loud 강화 + 보안/표준 정리
> 모든 기존 테스트(28 단위 + 4 통합) 통과 유지
> 신규 테스트 추가 (각 항목별 1~3건)

### F-1.1 — SQLite WAL 모드

**변경 파일**: `backend/database.py`

**구현**:
```python
from sqlalchemy import event

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
```

**검증**:
- 적용 후 `sqlite3 data/papers.db "PRAGMA journal_mode;"` → `wal` 출력
- discovery 사이클 실행 중 프론트에서 `GET /papers` 호출 → 블로킹 없이 응답
- `data/papers.db-wal`, `data/papers.db-shm` 파일 생성 확인

**주의**:
- WAL 모드 적용 후 기존 백업 도구가 .db 파일만 복사하면 .db-wal 누락. 향후 자동 백업(FUTURE_ROADMAP)에서 WAL 체크포인트 후 백업 패턴 사용 필요.
- 본인 환경 iCloud 아님 (Phase E 때 확인 완료) → fcntl 호환성 문제 없음.

**테스트 신규 1건**: `tests/test_db_pragma.py`
- 새 connection 열고 `PRAGMA journal_mode` 결과가 `wal`인지 확인

---

### F-1.2 — discovery.py eval_failed 버킷 (마이그레이션 004 dry-run 포함)

**변경 파일**:
- `backend/services/research_agent/discovery.py`
- `backend/models.py`
- `backend/services/research_agent/bootstrap.py`
- `backend/migrations/004_eval_failed.py` (신규)

**구현**:

```python
# discovery.py — 기존 line 275~278 부근
# 변경 전:
except StrictCallError as e:
    score = HOLD_SCORE
    reason = f"평가 실패: ..."

# 변경 후:
except StrictCallError as e:
    report.errors.append(f"score_relevance 실패 ({cand['paper_id']}): {e}")
    # 논문은 저장하되 is_eval_failed=True 마킹
    score = None  # 또는 -1 (sentinel)
    reason = f"[평가 실패] {str(e)[:200]}"
    eval_failed_flag = True
    # _classify 호출 우회 → 직접 "평가 실패" 폴더로 라우팅

# HOLD_SCORE 상수 자체는 보존 (사용자 수동 보류 의도와 구분)
# 단, 폴백 대입은 절대 X
```

```python
# models.py — Paper 모델에 추가
# 주의: default는 lambda 패턴으로 (F-1.4 §1 참조 — 단순 callable이 아니면 즉시 평가됨)
class Paper(Base):
    ...
    is_eval_failed = Column(Boolean, default=False, nullable=False)
    eval_failure_reason = Column(Text, nullable=True)
    eval_retry_count = Column(Integer, default=0, nullable=False)
```

```python
# bootstrap.py — SYSTEM_FOLDERS에 추가
SYSTEM_FOLDERS = [
    {"name": "풀분석 추천", "icon": "⭐"},
    {"name": "자동발견", "icon": "🔍"},
    {"name": "검토대기", "icon": "📥"},
    {"name": "평가 실패", "icon": "⚠️"},  # ← 신규
    {"name": "휴지통", "icon": "🗑️"},
]
```

**마이그레이션 004 dry-run 프로토콜** (사용자 승인 + dry-run 후 본 DB 적용):

```bash
# 1. 백업
TS=$(date +%Y%m%d_%H%M%S)
cp data/papers.db data/backups/papers_pre_004_${TS}.db

# 2. dry-run: 백업 파일에 먼저 적용
cp data/backups/papers_pre_004_${TS}.db /tmp/papers_dryrun.db
DATABASE_URL=sqlite:////tmp/papers_dryrun.db python -m backend.migrations.004_eval_failed

# 3. dry-run 무결성 검증
sqlite3 /tmp/papers_dryrun.db "PRAGMA integrity_check;"
# → "ok" 출력 확인
sqlite3 /tmp/papers_dryrun.db ".schema papers" | grep is_eval_failed
# → 컬럼 존재 확인
sqlite3 /tmp/papers_dryrun.db "SELECT name FROM folders WHERE name='평가 실패';"
# → 1건+ 출력 확인

# 4. dry-run 통과 시 본 DB에 적용
python -m backend.migrations.004_eval_failed
sqlite3 data/papers.db "PRAGMA integrity_check;"
sqlite3 data/papers.db "SELECT name FROM folders WHERE name='평가 실패';"

# 5. 적용 후 즉시 pytest
cd backend && pytest -v

# 6. 임시 파일 정리
rm /tmp/papers_dryrun.db
```

**주의**: dry-run은 SQL syntax/integrity 에러는 잡지만 의미적 spec 사고(Phase E의 UNIQUE 컬럼 잘못 박음 같은 사고)는 못 막음. 그건 사용자 검증 시나리오로 별도 확인.

**프론트 영향**: 자동. Library.jsx의 폴더 트리 UI가 "평가 실패" 폴더를 자연 표시. 별도 코드 변경 없음.

**테스트 신규 2건**:
- `tests/test_discovery_eval_failed.py`
  - LLM mock이 strict_call에서 LLMError raise → 논문은 저장, is_eval_failed=True, "평가 실패" 폴더에 들어감 검증
- `tests/test_bootstrap_eval_failed_folder.py`
  - 새 collection 부트스트랩 시 "평가 실패" 폴더가 생성되는지 확인

**검증 (사용자 직접)**:
```bash
# ollama 죽이기
pkill ollama
# discovery 트리거 (테스트 collection)
curl -X POST http://localhost:7010/dashboard/run-agent -d '{"collection_id": <test>}'
# 결과: 후보 논문이 "평가 실패" 폴더에 들어감, 사용자 화면에 표면화
sqlite3 data/papers.db "SELECT id, title, is_eval_failed FROM papers WHERE is_eval_failed=1 LIMIT 5;"
```

---

### F-1.3 — pdfs.py path traversal 방어

**변경 파일**: `backend/routers/pdfs.py`

**구현**:
```python
import re

def _safe_pdf_path(paper_id: str, suffix: str = "") -> str:
    """paper_id를 sanitize하여 안전한 PDF 파일 경로 반환.
    
    suffix: "_manual" 등 변형 지정 (저장 모드 구분용)
    """
    # 1. 화이트리스트 sanitize: 영숫자/언더스코어/하이픈만 허용
    safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(paper_id))
    if not safe_id:
        raise HTTPException(status_code=400, detail="잘못된 paper_id")
    
    filename = f"{safe_id}{suffix}.pdf"
    path = os.path.join(PDF_DIR, filename)
    
    # 2. 이중 방어: realpath가 PDF_DIR 내부인지 확인
    resolved = os.path.realpath(path)
    pdf_dir_resolved = os.path.realpath(PDF_DIR)
    if not resolved.startswith(pdf_dir_resolved + os.sep):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로")
    
    return resolved
```

**적용 지점** (모든 PDF 경로 생성):
- `download_pdf` 엔드포인트
- `upload_pdf_manual` 엔드포인트  
- `get_pdf` 엔드포인트
- `delete_pdf` 엔드포인트 (있다면)

**테스트 신규 3건**: `tests/test_path_traversal.py`
- `test_safe_path_normal`: 정상 paper_id → 정상 경로
- `test_safe_path_dotdot`: `paper_id="../../../etc/passwd"` → HTTPException 400
- `test_safe_path_absolute`: `paper_id="/etc/passwd"` → HTTPException 400

---

### F-1.4 — deprecated API 정리

**변경 파일**:
- `backend/main.py`
- `backend/database.py`
- `backend/models.py` (전역 datetime 교체 — **lambda 패턴 필수**)
- `backend/ai_client.py` (삭제)
- `backend/routers/alerts.py` (test_connection 참조 이전)

#### 작업 1 — lifespan 패턴

```python
# main.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    bootstrap_collections()
    yield
    # shutdown (현재는 비어있음)

app = FastAPI(lifespan=lifespan)
# 기존 @app.on_event("startup") 제거
```

#### 작업 2 — DeclarativeBase

```python
# database.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# 기존 Base = declarative_base() 제거
```

#### 작업 3 — datetime 전역 교체 (⚠️ lambda 패턴 필수)

**v2 핵심 패치 — 단순 치환은 silent bug 발생**:

```python
# ❌ 변경 전 (deprecated, but 동작함)
created_at = Column(DateTime, default=datetime.utcnow)
# datetime.utcnow는 callable. SQLAlchemy가 매 INSERT마다 호출.

# ❌ 단순 치환 (silent bug — 모든 row가 동일 시각)
created_at = Column(DateTime, default=datetime.now(timezone.utc))
# datetime.now(timezone.utc)는 모듈 로드 시점에 1회 평가된 datetime 객체.
# SQLAlchemy는 이 객체를 모든 INSERT에 재사용. → 모든 row가 같은 timestamp.

# ✅ 올바른 치환
created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
# lambda는 callable. 매 INSERT마다 호출되어 현재 시각 반환.
```

**규칙**:
- **Column의 `default=` 또는 `onupdate=`**: **반드시 `lambda: datetime.now(timezone.utc)`**
- **일반 코드의 `datetime.utcnow()` 호출**: `datetime.now(timezone.utc)`로 직접 치환 OK (즉시 호출이 의도)
- import: `from datetime import datetime, timezone`

**적용 범위**: models.py가 가장 많음 (~20+ 지점). 라우터/서비스에서도 산발.

**검증 시 주의**: 단순 grep으로 못 잡는 silent bug. 모든 default= 패턴을 수동 검토 필수. Claude Code에 "모든 Column default=datetime.utcnow를 lambda 패턴으로 바꿔라"라고 명시 지시할 것.

#### 작업 4 — ai_client.py 삭제

```bash
# 삭제 전 호출부 확인 (Phase B에서 deprecation 주석만 박았던 파일)
grep -rn "from ai_client\|import ai_client" backend/
# 결과 0건이어야 함. alerts.py의 test_connection만 남아있을 수 있음
# → services/llm/router.py에 동등한 함수 추가 후 alerts.py import 변경
# → ai_client.py 삭제
```

#### 검증

- pytest 28 + 4 = 32건 모두 통과
- DeprecationWarning 노이즈 0건 (`pytest -W error::DeprecationWarning`로 확인)
- 서버 startup 로그에 lifespan 정상 동작
- **datetime 검증 추가**: 새 논문 2건을 1초 간격으로 INSERT 후 created_at이 다른지 확인
  ```bash
  # 빠른 검증
  python -c "
  from backend.database import SessionLocal
  from backend.models import Paper
  import time
  db = SessionLocal()
  p1 = Paper(paper_id='test_dt_1', title='dt test 1')
  db.add(p1); db.commit()
  time.sleep(2)
  p2 = Paper(paper_id='test_dt_2', title='dt test 2')
  db.add(p2); db.commit()
  print('p1:', p1.created_at)
  print('p2:', p2.created_at)
  assert p1.created_at != p2.created_at, 'datetime default가 lambda가 아님!'
  db.delete(p1); db.delete(p2); db.commit()
  print('OK')
  "
  ```

**리스크**: datetime 교체 시 기존 DB의 naive datetime과 비교 연산이 깨질 수 있음. SQLAlchemy는 UTC tzaware/naive 혼용 시 비교 가능하지만, 일부 함수(strftime 등)에서 깨질 가능성. **테스트 통과 + 위 검증 스크립트로 확인**.

---

### F-1.5 — 코드 위생

**변경 파일**:
- `.gitignore`
- `.env.example`
- `frontend/src/components/Common/AIBackendBadge.jsx`
- `backend/routers/folders.py` (주석)
- `backend/services/llm/tasks.py` (docstring)

**작업**:
```
.gitignore: + node_modules/
.env.example: OLLAMA_MODEL=gemma4:e4b (현재 잘못된 값 있으면 교체)
AIBackendBadge.jsx: 모델명 표시 'qwen2.5:7b' → 'gemma4:e4b'
folders.py line ~121: UNIQUE 주석 정정 (Phase E 사고 흔적)
tasks.py line ~46: docstring "0~9" → "0~10" (RELEVANCE_SYSTEM v2 반영)
```

**검증**: 단순 시각 확인. 테스트 X.

---

## 4. Phase F-1 commit 단위

```
1. WAL 모드 (F-1.1)
2. eval_failed 버킷 + 마이그레이션 004 (F-1.2, dry-run 후 적용)
3. path traversal 방어 (F-1.3)
4. lifespan + DeclarativeBase + datetime lambda + ai_client.py 삭제 (F-1.4, 4건 한 번에)
5. 코드 위생 (F-1.5)
```

5개 commit. 각 commit 후 pytest 통과 확인.

---

## 5. Phase F-1 검증 체크포인트 (사용자 직접)

```bash
cd ~/paper-research && source venv/bin/activate

# 1. 모든 테스트 통과
cd backend && pytest -v
# 기대: 약 34건 passed (28 + eval_failed 신규 2 + path_traversal 신규 3 + db_pragma 신규 1)

# 2. WAL 활성
sqlite3 ../data/papers.db "PRAGMA journal_mode;"
# 기대: wal

# 3. eval_failed 폴더 생성
sqlite3 ../data/papers.db "SELECT name FROM folders WHERE name='평가 실패';"
# 기대: 1건+ (collection 수만큼)

# 4. ai_client.py 삭제
ls ai_client.py 2>&1
# 기대: No such file

# 5. deprecation warning 0건
pytest -W error::DeprecationWarning
# 기대: 32 passed (모든 deprecated 호출이 정리되었는지 확인)

# 6. datetime lambda 검증 (v2 신규)
# F-1.4 §검증 스크립트 실행 → "OK" 출력

# 7. ollama 죽이고 discovery 트리거 → 평가 실패 표면화
pkill ollama
# (UI에서 discovery 실행)
sqlite3 ../data/papers.db "SELECT id, title FROM papers WHERE is_eval_failed=1;"
# 기대: 후보 논문이 "평가 실패" 폴더에 들어감
```

전부 통과 시 → Phase F-1 commit + 다음 단계 진입.

---

## 6. Phase F-1.5: Pydantic 입력 스키마 (별도 commit)

> Phase F-1과 분리한 이유: 분량 큼 (15+ 엔드포인트), 회귀 영역 넓음, 별도 검증 필요

**변경 파일**:
- `backend/schemas.py` (신규 모델 15+개)
- `backend/routers/folders.py`
- `backend/routers/papers.py`
- `backend/routers/tags.py`
- `backend/routers/alerts.py`
- `backend/routers/ai.py`
- `backend/routers/settings.py`
- `backend/routers/dashboard.py` (해당되면)

**신규 Pydantic 모델**:

```python
# schemas.py 추가
class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: Optional[int] = None

class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    parent_id: Optional[int] = None

class FolderPaperAdd(BaseModel):
    paper_id: int

class PaperMove(BaseModel):
    paper_id: int
    target_folder_id: int

class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: Optional[str] = None

class PaperTagAdd(BaseModel):
    tag_id: int

class AnalyzeRequest(BaseModel):
    analysis_type: str = Field(
        ..., 
        pattern="^(summary|synthesis_conditions|experiment_summary|significance|keywords|structured|trend|review_draft)$"
    )

class AlertCreate(BaseModel):
    query: str = Field(min_length=1)
    collection_id: Optional[int] = None
    # ... 기존 필드들 typed로

class SettingUpdate(BaseModel):
    key: str = Field(min_length=1)
    value: Any

# ... 그 외 약 6~10개 더
```

**적용 패턴**:
```python
# 변경 전
@router.post("/folders")
async def create_folder(body: dict, db: Session = Depends(get_db)):
    name = body.get("name")
    if not name:
        raise HTTPException(400, "name required")
    ...

# 변경 후
@router.post("/folders")
async def create_folder(body: FolderCreate, db: Session = Depends(get_db)):
    ...
    # name은 Pydantic이 검증 완료
```

**프론트 영향**: 없음. 기존 axios 호출 그대로 호환 (body schema 동일).

**검증**:
- pytest 통과 (32+건)
- FastAPI auto docs (`/docs`) 에서 모든 POST/PUT 엔드포인트가 typed schema 표시 확인
- 의도적으로 잘못된 body 보내면 422 응답 (현재는 dict라 통과 가능했던 것들)

**테스트 신규 3건**: `tests/test_pydantic_input.py`
- 빈 name으로 folder 생성 → 422
- 잘못된 analysis_type → 422
- 정상 입력 → 200

---

## 7. Phase F-2: UI 통합

> 원래 이 세션의 Phase F 초안. F-1/F-1.5 이후로 미룬 것.
> 사용자가 명시 요청한 Library 폴더 드롭다운 절대 누락 X.

### F-2.0 — 죽은 API 6개 처리 결정

**대상** (AUDIT §7.2 + Phase F 초안):

| API | client.js 위치 | 결정 | 비고 |
|---|---|---|---|
| `searchAPI.search()` | line 6 | 연결 | Search 페이지에 "빠른 검색" 토글 추가 (S2 fetch 없이 로컬 검색만) |
| `papersAPI.getAnalyses()` | line 32 | 연결 | PaperDetail에 "분석 이력" 탭 추가 (F-2.3) |
| `foldersAPI.movePaper()` | line 64 | 연결 | Library 폴더 드롭다운에서 사용 (F-2.2). 백엔드는 Phase E folders.py fix로 이미 준비됨. |
| `dashboardAPI.agentStatus()` | line 143 | 연결 | Dashboard heartbeat 폴링 (F-2.4) |
| `aiAPI.createPrompt()` | line 88 | 삭제 후보 | F-2.1에서 grep 검증 후 결정 |
| `aiAPI.getPrompt()` | line 86 | 삭제 후보 | 동상 |

**사전 grep**:
```bash
grep -rn "createPrompt\|getPrompt" frontend/src
```
- 결과 0건 → 안전 삭제. client.js에서 함수 제거 + 백엔드 라우터(`backend/routers/ai.py`의 prompt 관련) 제거 검토
- 결과 1건+ → 사용자 보고 후 결정. **자동 삭제 X**.

---

### F-2.1 — createPrompt/getPrompt 처리

**조건부 삭제**:
- F-2.0 grep 결과 0건이면:
  - `frontend/src/api/client.js`에서 두 함수 제거
  - `backend/routers/ai.py`의 prompt 관련 엔드포인트 제거 (있다면)
  - prompt_templates 테이블 자체는 보존 (다른 용도 가능성)
- 결과 1건+면 사용자 보고

---

### F-2.2 — Library 폴더 드롭다운 (사용자 명시 요청, v2 사전 검증 추가)

**변경 파일**: `frontend/src/pages/Library.jsx`, `frontend/src/api/client.js`, (필요 시) `backend/routers/papers.py`

#### 사전 검증 (v2 신규 — folder_id 응답 확인)

드롭다운으로 "현재 폴더"를 표시하려면 paper 응답에 folder_id가 포함되어야 함. 현재 paper_to_dict가 그걸 내려주는지 확인.

```bash
# 현재 응답 확인
curl -s http://localhost:7010/papers | jq '.[0]' | grep folder_id
# 또는
curl -s http://localhost:7010/papers | jq '.[0] | keys'
```

**케이스 1**: folder_id 또는 folder 정보가 응답에 있음 → 그대로 사용

**케이스 2**: 응답에 없음 → `backend/routers/papers.py`의 `paper_to_dict` 또는 `list_papers`에서 추가 필요:
```python
def paper_to_dict(paper: Paper) -> dict:
    # ... 기존 필드들
    # folder_papers 조인으로 folder_id 추출 (UNIQUE(paper_id) 보장이므로 단건)
    folder_link = paper.folder_papers[0] if paper.folder_papers else None
    d['folder_id'] = folder_link.folder_id if folder_link else None
    d['folder_name'] = folder_link.folder.name if folder_link else None
    return d
```

**주의**: `paper.folder_papers`가 lazy load면 N+1 발생 가능. 일단 50건 규모에선 무시하고, 페이지네이션 적용 시점(FUTURE_ROADMAP 보류)에 joinedload 같이 박을 것.

#### 구현

**현재**: Library.jsx의 각 논문 카드에 `[상세보기] [미읽음] [삭제]` 버튼

**추가**:
```jsx
// 각 논문 카드에 폴더 드롭다운 추가
<select 
  value={paper.folder_id || ''}
  onChange={(e) => handleMove(paper.id, parseInt(e.target.value))}
  className="paper-folder-select"
>
  <option value="">-- 폴더 선택 --</option>
  {folders.map(f => (
    <option key={f.id} value={f.id}>{f.name}</option>
  ))}
</select>
```

**핸들러**:
```jsx
const handleMove = async (paperId, targetFolderId) => {
  try {
    await foldersAPI.movePaper(paperId, targetFolderId);
    // optimistic update or refetch
    refetchPapers();
    toast.success("폴더 이동 완료");
  } catch (e) {
    toast.error("이동 실패: " + e.message);
  }
};
```

**API 호출**: `POST /folders/{target_folder_id}/papers/move` 또는 기존 movePaper 엔드포인트 (Phase E folders.py move semantics 사용)

**핵심**: Phase E의 folders.py 수정으로 이미 INSERT 전 DELETE → move semantics 보장됨. UNIQUE(paper_id) 제약과 호환.

**검증**:
- 폴더 A의 논문을 드롭다운으로 폴더 B로 이동 → 단일 폴더만 보임
- IntegrityError 없음
- UI에 현재 폴더가 정상 표시됨 (folder_id 응답 확인 결과)
- 이동 후 드롭다운 값도 새 폴더로 갱신됨

---

### F-2.3 — PaperDetail 분석 이력 탭

**변경 파일**: `frontend/src/pages/PaperDetail.jsx`, `frontend/src/api/client.js`

**현재**: PaperDetail에 [분석] [PDF] [메타데이터] 탭

**추가**:
```jsx
// 새 탭 [분석 이력]
<Tab label="분석 이력">
  {analyses.map(a => (
    <div key={a.id} className="analysis-history-item">
      <div className="analysis-header">
        <span className="analysis-type">{a.analysis_type}</span>
        <span className="analysis-time">
          {new Date(a.created_at).toLocaleString('ko-KR')}
        </span>
      </div>
      <pre className="analysis-result">{a.result}</pre>
    </div>
  ))}
</Tab>
```

**API 호출**: `papersAPI.getAnalyses(paperId)` → 기존 죽은 API 살림

**백엔드 검증**: `GET /papers/{id}/analyses` 엔드포인트가 정상 동작하는지 확인. 안 되면 라우터 추가.

---

### F-2.4 — Dashboard heartbeat 폴링

**변경 파일**: `frontend/src/pages/Dashboard.jsx`, `frontend/src/api/client.js`

**Phase E의 heartbeat 컬럼 활용**:
- AgentRun.heartbeat_at, locked_by 컬럼 이미 존재

**구현**:
```jsx
// Dashboard.jsx
useEffect(() => {
  if (!agentRunning) return;
  const interval = setInterval(async () => {
    const status = await dashboardAPI.agentStatus();
    setAgentStatus(status);
    if (!status.is_running) {
      clearInterval(interval);
    }
  }, 5000); // 5초 폴링
  return () => clearInterval(interval);
}, [agentRunning]);
```

**UI 표시**:
```jsx
{agentRunning && (
  <div className="agent-status">
    <span className="pulse-dot" />
    실행 중... 마지막 heartbeat: {agentStatus.heartbeat_at}
    <span>{agentStatus.processed_count} / {agentStatus.total_count}</span>
  </div>
)}
```

**백엔드**: `GET /dashboard/agent-status` 엔드포인트
```python
@router.get("/dashboard/agent-status")
async def agent_status(db: Session = Depends(get_db)):
    latest = db.query(AgentRun).order_by(AgentRun.id.desc()).first()
    if not latest:
        return {"is_running": False}
    is_stale = (
        datetime.now(timezone.utc) - latest.heartbeat_at
    ) > timedelta(minutes=2) if latest.heartbeat_at else True
    return {
        "is_running": latest.finished_at is None and not is_stale,
        "heartbeat_at": latest.heartbeat_at,
        "started_at": latest.started_at,
        "locked_by": latest.locked_by,
        "processed_count": getattr(latest, 'processed_count', 0),
        "total_count": getattr(latest, 'total_count', 0),
    }
```

---

## 8. Phase F-2 commit 단위

```
1. F-2.0/F-2.1 grep 검증 + createPrompt/getPrompt 처리
2. F-2.2 Library 폴더 드롭다운 (folder_id 응답 보강 포함)
3. F-2.3 PaperDetail 분석 이력 탭
4. F-2.4 Dashboard heartbeat 폴링
```

---

## 9. Phase F-2 검증 체크포인트 (사용자 직접)

```bash
# 1. Library 페이지에서 폴더 드롭다운 동작
# - 논문 A를 폴더 1 → 폴더 2로 이동
# - DB 확인:
sqlite3 data/papers.db "SELECT folder_id FROM folder_papers WHERE paper_id=<A>;"
# 기대: 폴더 2 단 1건 (UNIQUE(paper_id) 만족)
# - UI에서 드롭다운 값도 폴더 2로 갱신됨

# 2. PaperDetail 분석 이력 탭
# - 분석 여러 번 돌린 논문 페이지 → [분석 이력] 탭 클릭
# - 기대: 모든 분석 결과 시간순 표시

# 3. Dashboard heartbeat
# - "전체 분석 실행" 클릭
# - 진행 중 상태 표시 + 5초마다 heartbeat 갱신
# - 완료 후 자동으로 표시 사라짐

# 4. pytest 회귀
cd backend && pytest -v
# 기대: 32+건 passed
```

---

## 10. 보류 항목 (FUTURE_ROADMAP.md로 분리)

- **F.1 N+1 + 페이지네이션**: collection 100~200건 임계 도달 시 트리거
- **Phase G/H/I/J/K 전체**: 외부 도구 통합 전략으로 대체 (FUTURE_ROADMAP v2 참조)
- **search.py 900줄 분리**: 본인 결정 "직접 구현 안 함" 원칙에 따라 보류. 트리거 조건 = "search.py가 실제로 유지보수 부담이 됐을 때". (논문계획3.md §3 거부 결정, REVIEW_FROM_OTHER_SESSION.md 참조)

---

## 11. 다음 세션 발사 시퀀스

```bash
# 1. 컨텍스트 복원
cd ~/paper-research && source venv/bin/activate
git log --oneline -5
cd backend && pytest -v   # 28+4 통과 확인

# 2. 본 사양 attach 또는 참조
# claude code에 본 .md 파일 첨부 + "Phase F-0부터 시작" 지시

# 3. F-0(베이스라인) → F-1 → 사용자 검증 → F-1.5 → 사용자 검증 → F-2 → 사용자 검증

# 4. 완료 후 commit + push
git push origin main
```

**Claude Code 발사 프롬프트 초안** (`.claude/prompts/phase_f_launch.md`로 저장):
```
@docs/PHASE_F_INTEGRATED_PLAN_v2.md 를 사양으로 사용한다.

작업 순서:
1. Phase F-0 베이스라인 측정 (10분, docs/PHASE_F_BASELINE.md 생성)
2. Phase F-1 (F-1.1 ~ F-1.5 순차)
3. Phase F-1.5 Pydantic
4. Phase F-2 UI

각 항목 끝나면:
1. 해당 commit message로 git commit (사양에 명시된 commit 단위 따름)
2. pytest 실행 결과 보고
3. 사용자 검증 대기

주의 사항:
- F-1.2 마이그레이션 004: 사용자 승인 + dry-run 프로토콜 (사양 §3 F-1.2 참조) 필수
  백업 파일명: data/backups/papers_pre_004_<YYYYMMDD_HHMMSS>.db
- F-1.4 datetime 치환: Column default는 반드시 lambda 패턴
  단순 datetime.now(timezone.utc) 치환 금지 (silent bug)
  적용 후 검증 스크립트(사양 §3 F-1.4) 실행
- F-2.2 폴더 드롭다운: 시작 전 paper 응답에 folder_id 포함되는지 확인. 
  없으면 paper_to_dict에서 추가.

작업 시작.
```

---

## 12. 위험 식별

| 위험 | 영향 | 대응 |
|---|---|---|
| F-1.4 datetime Column default 단순 치환 | **높음 (silent bug)** | **lambda 패턴 명시 + 검증 스크립트** (v2 신규) |
| F-1.4 datetime 교체 시 비교 연산 깨짐 | 중 | pytest 32건이 회귀 감지. 깨지면 즉시 롤백 |
| F-1.2 마이그레이션 004 실수 (Phase E 사고 재발) | 높 | 사용자 승인 + dry-run + 백업 (v2 강화) |
| F-2.2 폴더 드롭다운이 UNIQUE 위반 | 낮 | Phase E folders.py fix로 이미 해결. 회귀 테스트로 확인 |
| F-2.2 paper 응답에 folder_id 누락 | 중 | v2 사전 검증 단계 추가 |
| F-1.4 ai_client.py 삭제 후 import 잔존 | 중 | grep으로 사전 확인 (Claude Code가 먼저 grep) |
| Pydantic 적용 시 프론트 호환성 깨짐 | 중 | 422 응답으로 즉시 발견. axios 에러 처리에서 표면화 |

---

## 13. PHASE_F_DONE.md 템플릿 (v2 신규)

> 출처: 논문계획3.md §8
> Phase F 완료 시 본 템플릿을 채워서 `docs/PHASE_F_DONE.md`로 저장.
> 다음 세션 컨텍스트 복원용.

```markdown
# PHASE_F_DONE.md

## 완료일
YYYY-MM-DD

## 적용된 commit
- `<hash>` F-0 베이스라인 측정 (PHASE_F_BASELINE.md 생성)
- `<hash>` F-1.1 WAL 모드
- `<hash>` F-1.2 eval_failed 버킷 + 마이그레이션 004
- `<hash>` F-1.3 path traversal 방어
- `<hash>` F-1.4 deprecated 정리 (lifespan + DeclarativeBase + datetime lambda + ai_client.py 삭제)
- `<hash>` F-1.5 코드 위생
- `<hash>` F-1.6 Pydantic 입력 스키마
- `<hash>` F-2.0/F-2.1 죽은 API 정리
- `<hash>` F-2.2 Library 폴더 드롭다운 (folder_id 응답 보강 포함)
- `<hash>` F-2.3 PaperDetail 분석 이력 탭
- `<hash>` F-2.4 Dashboard heartbeat 폴링

## 현재 상태
- pytest: N건 통과 (기존 28 + 신규 N)
- DB: 마이그레이션 004 적용
- WAL: 활성
- DeprecationWarning: 0건
- 삭제 파일: backend/ai_client.py
- datetime: 모든 Column default lambda 패턴 적용 + 검증 스크립트 통과

## 성능 변화 (베이스라인 대비)
| 측정 항목 | Before (F-0) | After (F 완료) | 변화 |
|---|---|---|---|
| GET /papers 응답 시간 | Xms | Yms | ±Z% |
| GET /folders 응답 시간 | Xms | Yms | ±Z% |
| Search stream 응답 시간 | Xms | Yms | ±Z% |
| DB 크기 | X MB | Y MB | +Z MB |
| papers 건수 | X | Y | +N |
| 서버 메모리 (RSS) | X MB | Y MB | ±Z MB |
| pytest 건수 | 32 | N | +N |

## Phase F 중 발견, 미해결 이슈
- (있으면 기록. 없으면 "없음")

## 다음 세션 작업
- FUTURE_ROADMAP_v2.md §1 Phase G 결정 항목 확인
- Phase G-1 paper-qa standalone 검증 → 결과에 따라 G-2 진입
- (또는 안정화 기간 1~2주 → 본인 사용 패턴 관찰 후 결정)

## 학습/회고
- (Phase A~E와 마찬가지로 본인이 박은 영구 규칙 / 사고 / 깨달음 기록)
```

---

## 14. Phase F 종료 기준

다음 모두 만족 시 Phase F 완료 선언:

- [ ] PHASE_F_BASELINE.md 작성 (F-0)
- [ ] pytest 38+건 모두 통과
- [ ] DeprecationWarning 0건
- [ ] WAL 모드 활성
- [ ] 마이그레이션 004 적용 (dry-run 통과 후)
- [ ] datetime lambda 검증 스크립트 통과
- [ ] eval_failed 시나리오 사용자 직접 검증 통과
- [ ] Library 폴더 드롭다운 사용자 직접 검증 통과 (folder_id 정상 표시 + 이동 + UI 갱신)
- [ ] PaperDetail 분석 이력 탭 동작
- [ ] Dashboard heartbeat 표시
- [ ] git push 완료
- [ ] PHASE_F_DONE.md 작성 (§13 템플릿 채움, before/after 표 포함)

---

> 본 사양 v2는 두 Claude 세션의 계획 + 본인 사전 검증 + 본인 결정(Q1=A, Q2=A, Q3=B, Q4=A) + 다른 세션 Claude의 v1 평가(논문계획3.md) 중 5건 패치를 통합한 결과.
> Phase A~E 명명 규칙 / 정신(테스트 먼저, fail-loud, ACID-safe, 검증 체크포인트)을 그대로 계승.
> v1 → v2 차이는 본 문서 상단 "변경 사항 요약" 표 참조.
> v1 평가에서 거부된 항목(search.py 분리)은 REVIEW_FROM_OTHER_SESSION.md에 기록 보존.
