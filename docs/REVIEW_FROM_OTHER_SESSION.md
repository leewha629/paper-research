# REVIEW_FROM_OTHER_SESSION.md

> 작성일: 2026-04-09
> 목적: PHASE_F_INTEGRATED_PLAN_v1 + FUTURE_ROADMAP_v1에 대한 다른 세션 Claude(논문계획3.md)의 평가를 보존하고, 각 항목별 수용/거부 결정을 트래킹.
> v2 작성 근거. 본인이 나중에 결정을 재검토할 때 참조.

---

## 1. 평가 출처

- **평가 작성자**: 다른 Claude 계정의 Claude Code 세션
- **입력**: 본 세션이 작성한 PHASE_F_INTEGRATED_PLAN.md + FUTURE_ROADMAP.md
- **출력**: 논문계획3.md (8건 보완 사항 + 본문 평가)
- **본 세션 응답**: 9건 항목별 수용/거부 결정 → v2 두 파일 작성

---

## 2. 본문 평가 (논문계획3.md 앞부분)

### 잘한 점으로 평가받은 것
1. 사전 grep 검증 3건 — "이슈 있다" 주장을 코드에서 직접 확인하고 수용/보류 판단
2. F-1 / F-1.5 / F-2 분할 — 의존성 순서에 맞게 쪼갬 + Phase E 사고 학습 반영
3. F-1.2 eval_failed 설계 정교함 — 3컬럼 + 마이그레이션 + bootstrap + 검증 시나리오까지 spec화
4. 발사 프롬프트 초안 — Claude Code 효율 메타 전략

### 보완 가능한 점으로 평가받은 것
- **F-1.4 datetime 단순 치환 함정** → v2에 반영
- **F-2.2 folder_id 응답 검증 누락** → v2에 반영

### FUTURE_ROADMAP에 대한 평가
- "어차피 직접 구현해도 클로드 도움 없이는 못 함" 결정이 정확
- 비교 테이블(§2)이 결정 품질을 높임
- "절대 안 할 것들"(§5) 적절
- §4 우선순위에서 "안정화 기간 1~2주"를 Phase 사이에 넣은 것 좋음

### FUTURE에 대해 보완 가능한 점
- paper-qa의 ollama 임베딩 LiteLLM 경유 불안정 가능성 → G-1 검증으로 확인 OK
- findpapers snowballing이 citation graph 모델로 직접 안 뽑힘 → glue code 필요, "1일"은 빡빡

---

## 3. 8건 보완 사항 결정 트래킹

| # | 항목 | 결정 | 적용 위치 | 거부 이유 (해당 시) |
|---|---|---|---|---|
| 1 | datetime lambda 패턴 | ✅ 수용 | PHASE_F_v2 §F-1.4 | — |
| 2 | 마이그레이션 dry-run 프로토콜 | ✅ 수용 | PHASE_F_v2 §F-1.2 | — |
| 3 | search.py 900줄 분리 (G 이전) | ❌ **거부** | — | 아래 §4 상세 |
| 4 | paper-qa ↔ paper-research 동기화 전략 | ✅ 수용 (G로 이연) | FUTURE_v2 §G | — |
| 5 | 성능 베이스라인 측정 | ✅ 수용 | PHASE_F_v2 §F-0 (신규) | — |
| 6 | RAG graceful degradation | ✅ 수용 (G로 이연) | FUTURE_v2 §G | — |
| 7 | 외부 dep 버전 고정 | ✅ 수용 (G로 이연) | FUTURE_v2 §G | — |
| 8 | PHASE_F_DONE.md 템플릿 | ✅ 수용 | PHASE_F_v2 §13 | — |

**+추가 (본문 평가에서)**:
| 항목 | 결정 | 적용 위치 |
|---|---|---|
| F-2.2 folder_id 응답 검증 | ✅ 수용 | PHASE_F_v2 §F-2.2 |
| findpapers G-4 분량 조정 | ✅ 수용 (G로 이연) | FUTURE_v2 §G |

**합계**: 9건 수용, 1건 거부.

---

## 4. 거부 항목 상세 — #3 search.py 900줄 분리

### 다른 세션 Claude의 주장

> FUTURE_ROADMAP에서 G.1 search.py 모듈 분리를 "우선순위 낮음"으로 보류했으나, Phase G RAG 통합 시 이게 발목을 잡는다.
>
> **문제**: paper-qa RAG 검색을 기존 search 흐름에 합치려면, search.py의 7개 책임(한국어 처리, 번역, 불리언, 동의어, AI 스코어링, SSE, 캐싱)이 뒤섞인 상태에서 끼워넣어야 함. 900줄 파일에 새 검색 모드 추가하면 1200줄+. 그때 분리하면 이미 엉켜있음.
>
> **제안**: F-2와 G 사이에 F-3을 추가하거나, G 첫 commit으로 분리부터.

### 본 세션의 거부 근거

#### 근거 1: 전제가 본인 전략과 다름

상대 Claude의 논리는 "**paper-qa RAG를 search.py에 합치려면** 분리가 선행돼야 한다"임. 

**but** 본인 G 전략에서 paper-qa는 search.py에 합치지 않음. paper-qa는 별도 라우터(`POST /ai/qa`, `POST /ai/chat-with-papers`)로 추가하는 게 자연스러움. 기존 search.py 흐름과 독립.

상대 Claude가 search.py 분리를 G의 필수 선행으로 본 건 "자기가 G를 직접 구현한다고 가정"한 거. 본인은 안 함. 그러면 분리 필요성이 사라짐.

#### 근거 2: 본인 결정 원칙과 모순

본인이 이 세션에서 명시한 핵심 결정:
> "어차피 직접 구현해도 클로드 도움 없이는 못 함. 그럼 검증된 라이브러리 가져다 쓰는 게 합리적."

이 원칙대로면 search.py 900줄 리팩토링은 **본인이 직접 손대는 코드 작업**이고, 사이드 프로젝트 시간 우선순위에서 한참 뒤. 반나절짜리 작업이지만 **본인 시간 가용성 기준으로는 1주일치 부담**.

상대 Claude가 못 본 것: 본인이 "직접 구현 안 함" 결정의 함의를 일관되게 적용해야 함. 코드 위생 작업도 같은 카테고리.

#### 근거 3: 트리거 조건 부재

리팩토링은 "필요해질 때" 하면 됨. 현재 search.py가 **유지보수 부담을 일으키고 있다는 증거 없음**:
- 본인이 search.py 때문에 작업이 느려진 적 있나? 없음
- 버그가 search.py 구조 때문에 잡기 어려웠나? 없음 (Phase A~E 동안)
- 새 기능 추가 시 충돌했나? 안 했음

→ "예방적 리팩토링"은 명백한 yagni 위반. 트리거 발생 후에 박으면 됨.

### 거부 후속 조치

PHASE_F_v2 §10 "보류 항목"에 명시 추가:

> **search.py 900줄 분리**: 본인 결정 "직접 구현 안 함" 원칙에 따라 보류. 트리거 조건 = "search.py가 실제로 유지보수 부담이 됐을 때". (논문계획3.md §3 거부 결정, REVIEW_FROM_OTHER_SESSION.md 참조)

미래에 search.py가 진짜 부담이 되면, 그때 본 문서를 다시 보고 결정 재검토. 현재로선 거부 유지.

---

## 5. 메타 학습

### 다른 세션 Claude의 강점
- **silent bug 한 건 잡음** (datetime Column default). 본 세션이 못 본 것
- **dry-run 같은 ops 디테일** 챙김
- **외부 도구 통합 시 운영 시나리오** (paper-qa 동기화, RAG degradation) 미리 짚음
- 본인 결정 원칙을 정확히 이해하고 인용함

### 다른 세션 Claude의 약점
- search.py 분리는 자기 전제(직접 구현)를 본인 전제(외부 도구)로 옮기지 못함
- 1건. 9/10 hit ratio면 매우 좋은 cross-check.

### 본 세션의 학습
- **cross-check 패턴이 다시 입증됨**. Phase D 때 RELEVANCE_SYSTEM secondary Opus 검토와 동일 패턴.
- 단일 Claude 세션이 silent bug를 놓치는 경우가 분명히 있음. **중요한 사양 작업은 cross-check 권장**.
- 영구 규칙 후보: "복잡한 사양은 다른 Claude 세션에 평가 의뢰" — 이미 본인이 박은 규칙(C번)과 일치.

---

## 6. 논문계획3.md 원문 보존

> 다음은 논문계획3.md 전문. 결정의 출처. 수정하지 말 것.

```markdown
# 논문계획3.md — Phase F/G 보완 사항

> 작성일: 2026-04-09
> 입력: PHASE_F_INTEGRATED_PLAN.md + FUTURE_ROADMAP.md 평가 기반
> 목적: 두 문서에서 빠져 있거나 약한 부분 8건 정리. 실행 세션에서 참조.
> 본 문서는 기존 spec을 수정하지 않음. 실행 시 병행 참조용.

---

## 1. F-1.4 datetime 치환 함정 — lambda 패턴 필수

models.py의 Column default에서 `datetime.utcnow`를 단순 치환하면 버그.

```python
# 현재 (deprecated but 동작함)
created_at = Column(DateTime, default=datetime.utcnow)
# → utcnow는 callable이라 매 INSERT마다 호출됨

# 단순 치환 (버그)
created_at = Column(DateTime, default=datetime.now(timezone.utc))
# → 모듈 로드 시점에 1회 평가. 모든 row가 동일 시각.

# 올바른 치환
created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
# → callable 유지. 매 INSERT마다 호출.
```

**적용 범위**: models.py의 `default=datetime.utcnow` 전부 + 코드 내 `datetime.utcnow()` 호출 전부.
Column의 `default=`만 lambda 필요. 일반 코드의 `datetime.utcnow()` 호출은 `datetime.now(timezone.utc)`로 직접 치환 OK.

**실행 세션 지시**: "datetime 치환 시 Column default는 반드시 lambda로 감싸라."

---

## 2. 마이그레이션 004 Dry-Run 프로토콜

Phase E 마이그레이션 사고 재발 방지. 현재 spec은 "백업 + 사용자 승인"만 있음.

```bash
# 1. 백업
cp data/papers.db data/backups/papers_pre_004_$(date +%Y%m%d_%H%M%S).db

# 2. 백업 파일에 먼저 dry-run
sqlite3 data/backups/papers_pre_004_*.db < migrations/004_eval_failed.sql
sqlite3 data/backups/papers_pre_004_*.db "PRAGMA integrity_check;"
# → "ok" 확인

# 3. dry-run 성공 확인 후 본 DB에 적용
python -m backend.migrations.004_eval_failed
sqlite3 data/papers.db "PRAGMA integrity_check;"
# → "ok" 확인

# 4. 적용 후 즉시 pytest
cd backend && pytest -v
```

**핵심**: 백업이 있어도 복원하면 백업~복원 사이 데이터가 날아간다. dry-run이 방어 깊이 +1.

---

## 3. search.py 900줄 분리 — Phase G 이전에 해야 한다

FUTURE_ROADMAP에서 G.1 search.py 모듈 분리를 "우선순위 낮음"으로 보류했으나, Phase G RAG 통합 시 이게 발목을 잡는다.

**문제**: paper-qa RAG 검색을 기존 search 흐름에 합치려면, search.py의 7개 책임(한국어 처리, 번역, 불리언, 동의어, AI 스코어링, SSE, 캐싱)이 뒤섞인 상태에서 끼워넣어야 함. 900줄 파일에 새 검색 모드 추가하면 1200줄+. 그때 분리하면 이미 엉켜있음.

**제안**: F-2와 G 사이에 F-3을 추가하거나, G 첫 commit으로 분리부터.

```
Phase F-2 완료
  ↓
Phase F-3 "search.py 구조 분리" (반나절)
  ├─ search/korean.py       (한국어 처리 + 동의어)
  ├─ search/translate.py    (번역)
  ├─ search/scoring.py      (AI 스코어링)
  ├─ search/sse.py          (SSE 스트리밍)
  ├─ search/cache.py        (캐싱)
  ├─ search/boolean.py      (불리언 파싱)
  └─ search/router.py       (엔드포인트만, import 조립)
  ↓
Phase G: RAG 통합 (search/rag.py로 깔끔하게 추가)
```

**검증**: 분리 후 기존 검색 동작 동일 + pytest 통과. 기능 변경 0.

---

## 4. paper-qa ↔ paper-research 데이터 동기화 전략

FUTURE_ROADMAP Phase G spec에서 빠진 부분. paper-qa는 자체 인덱스(벡터 DB + 문서 캐시)를 관리함. paper-research의 SQLite papers 테이블과 별개.

**문제 시나리오**:
- paper-research에서 논문 삭제 → paper-qa 인덱스에는 남아있음 → RAG 답변에 삭제된 논문 인용
- collection 간 논문 이동 → paper-qa는 collection 개념 없음 → 다른 collection 질문에 엉뚱한 논문 답변
- PDF 재업로드(수정본) → paper-qa 인덱스 갱신 필요

**옵션 A: 인덱스를 일회용으로 취급 (권장, 단순)**
- 매 질문 시 해당 collection의 PDF 폴더를 paper-qa에 전달
- paper-qa의 내부 캐싱이 있으므로 두 번째부터는 빠름
- 논문 삭제/이동 시 자연스럽게 반영 (PDF 폴더 내용이 곧 진실)
- 단점: 첫 질문이 느림 (인덱싱 시간)

**옵션 B: 인덱스 무효화 훅 (복잡, 빠름)**
- paper 삭제/이동/PDF 업로드 시 paper-qa 인덱스 rebuild 트리거
- `backend/services/rag/index_manager.py` 신규
- 논문 CRUD 엔드포인트에 훅 추가
- 단점: glue code 필요, 동기화 버그 가능성

**G-1 검증 시 확인 항목 추가**:
- PDF 50건 인덱싱 후 1건 삭제 → 재질문 시 삭제된 논문이 답변에 나오는지 확인
- 결과에 따라 옵션 A/B 결정

---

## 5. 성능 베이스라인 측정

Phase F에서 WAL 적용, Phase G에서 RAG 추가하는데, "전"의 수치가 없으면 개선 여부 판단 불가.

**F-1 시작 전 1회 측정 (10분)**:

```bash
# API 응답 시간
time curl -s http://localhost:7010/papers | jq length
time curl -s http://localhost:7010/folders | jq length
time curl -s "http://localhost:7010/search/stream?query=CeO2&collection_id=1" > /dev/null

# DB 크기 + 건수
ls -lh data/papers.db
sqlite3 data/papers.db "SELECT COUNT(*) FROM papers;"
sqlite3 data/papers.db "SELECT COUNT(*) FROM analyses;"
sqlite3 data/papers.db "SELECT COUNT(*) FROM folders;"

# 서버 메모리 사용량
ps aux | grep uvicorn | grep -v grep | awk '{print $6/1024 "MB"}'
```

**기록 위치**: `PHASE_F_BASELINE.md` (Phase F 완료 후 동일 측정으로 before/after 비교)

---

## 6. RAG Graceful Degradation

Phase G 이후 장애 지점이 늘어남:
- RTX 5080 데스크탑 꺼짐 → paper-qa 임베딩/추론 불가
- Tailscale 연결 끊김 → RAG 엔드포인트 타임아웃
- 임베딩 모델 + LLM 동시 로드 → OOM

**Phase G spec에 추가할 degradation 정책**:

```
RAG 불가 시 동작:
1. /ai/qa 엔드포인트: 503 + {"error": "RAG 서비스 연결 불가", "fallback": "키워드 검색을 사용하세요"}
2. 기존 키워드 검색은 완전 독립 경로 — RAG 장애와 무관하게 동작
3. frontend Search 페이지:
   - RAG 서비스 연결 실패 시 [의미검색(RAG)] 토글 비활성화
   - 툴팁: "RAG 서비스 연결을 확인하세요"
   - [키워드] 모드는 항상 사용 가능
4. 타임아웃: 연결 5초 + 응답 60초. 1회 재시도 후 포기.
5. PaperDetail "이 논문에 질문하기" 버튼: 연결 불가 시 disabled + 사유 표시
```

**원칙**: RAG는 "있으면 좋은 기능"이지 핵심 경로가 아님. RAG 장애가 기존 기능을 끌어내리면 안 됨.

---

## 7. 외부 의존성 버전 고정

paper-qa, findpapers는 활발히 개발 중. breaking change 위험.

**G-1 검증 완료 후 즉시**:

```
# requirements.txt에 추가
paper-qa==5.x.x        # G-1 검증 완료 버전
findpapers==x.x.x      # G-4 검증 완료 버전 (G-4 진행 시)
litellm==x.x.x         # paper-qa 의존성, 간접 버전도 고정
```

**이유**: 3개월 뒤 `pip install paper-qa`에서 breaking change 맞으면, 그때 디버깅하느라 반나절 날림. 지금 pin 해두면 0분.

**업데이트 정책**: 분기 1회 `pip install --upgrade` → pytest 통과 확인 → 버전 갱신.

---

## 8. PHASE_F_DONE.md 템플릿

PHASE_F_INTEGRATED_PLAN.md §13 종료 기준에 "PHASE_F_DONE.md 작성"이 있으나 내용 정의 없음.

(템플릿 본문은 PHASE_F_INTEGRATED_PLAN_v2.md §13에 통합되어 보존됨)

---

> 본 문서는 PHASE_F_INTEGRATED_PLAN.md와 FUTURE_ROADMAP.md를 수정하지 않음.
> 실행 세션에서 두 문서와 함께 참조하는 보완 자료.
```

---

## 7. 다음 단계

- 본 문서: 결정 트래킹 보존용. 수정 X.
- PHASE_F_INTEGRATED_PLAN_v2.md: 실행 사양. Phase F 작업 시 사용.
- FUTURE_ROADMAP_v2.md: **다음 세션에서 작성 예정**. 본인이 "G도 해줘" 요청 시 본 세션이 작성.
  - 반영할 항목: 논문계획3.md §4, §6, §7 + findpapers G-4 분량 조정 + 기존 v1 내용 유지

---

> 본 문서는 본인이 미래에 결정을 재검토할 때 추적 가능하게 하는 자료.
> 수용/거부 결정의 근거를 기록함으로써, 같은 cross-check가 다시 들어와도 일관된 답을 줄 수 있게 함.
