# FUTURE_ROADMAP v2

> 작성일: 2026-04-15
> v1 → v2 변경: 논문계획3.md 평가 중 4건 패치 반영 + Phase F 운영에서 발견된 신규 항목 3건 추가
> 목적: Phase F 완료 후 다음 단계 결정용 카탈로그. 즉시 작업 대상 아님.
> 다음 세션 작업: Phase G 또는 ollama 원격화

---

## v1 → v2 변경 사항 요약

| # | 패치 | 출처 |
|---|---|---|
| 1 | paper-qa ↔ paper-research 데이터 동기화 전략 | 논문계획3.md §4 |
| 2 | RAG graceful degradation 정책 | 논문계획3.md §6 |
| 3 | 외부 의존성 버전 고정 | 논문계획3.md §7 |
| 4 | findpapers G-4 분량 1일 → 1~2일 조정 | 논문계획3.md 본문 평가 |
| 5 | ollama backend 원격화 (RTX 5080) | Phase F 운영에서 발견 |
| 6 | 분석 진행률 추적 (풀분석 추천 → 완료) | 사용자 발의 |
| 7 | frontend "분석 중" stale 상태 fix | Phase F 운영에서 발견 |

---

## 0. 즉시 다음 작업: Phase F 부록 — ollama 원격화

> 상태: **Phase G 이전에 먼저 진행 권장** (Phase G의 paper-qa도 같은 인프라 사용)
> 트리거: Phase F 운영에서 Mac mini 16GB + gemma4:e4b 단일 분석 stuck + 발열 65°C 직접 체감
> 분량: 본인이 집 갔을 때 30분

### 작업 내용

**Windows RTX 5080 데스크탑 (1회 설정)**:
1. 데스크탑 직접 가서 관리자 PowerShell 열기
2. 환경변수: `[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")`
3. 방화벽: `New-NetFirewallRule -DisplayName "Ollama Tailscale" -Direction Inbound -LocalPort 11434 -Protocol TCP -Action Allow`
4. ollama 트레이 Quit + 재시작

**Mac mini (paper-research 변경)**:
```bash
# 1. 검증
curl -s http://100.80.119.78:11434/api/tags | head
# → gemma4 26B MoE Q4 + gpt-oss-20b 모델 목록 JSON

# 2. paper-research backend의 ollama URL 분리
# backend/.env 또는 환경변수:
OLLAMA_URL=http://100.80.119.78:11434
# (현재 하드코딩 위치 확인: grep -rn "11434\|OLLAMA" backend/services/llm/)

# 3. backend 재시작 후 1편 분석 테스트
# gemma4:e4b 대신 gemma4 26B MoE 사용 → 더 빠르고 품질 ↑
```

**인증 우려 없음**: ollama HTTP API는 인증 레이어 없음. Tailscale이 IP 라우팅만 해주면 끝. 본인이 우려한 "MS 계정 비번" 문제는 SMB/파일공유 채널에만 해당, ollama HTTP와 무관.

**RTX 5080이 꺼져 있을 때**: backend → strict_call → connection refused → LLMError raise → Phase F-1.2 fail-loud로 사용자 화면에 503 표시. 기존 기능(키워드 검색, 폴더 관리, 논문 브라우징)은 완전 독립 경로라 영향 없음.

### Tailscale 네트워크 정보 (2026-04-10 확인)
```
100.107.100.32  macmini      macOS     ← paper-research backend
100.80.119.78   node         windows   ← RTX 5080 데스크탑 (ollama target)
100.94.98.74    iphone183    iOS
100.94.128.108  localhost-0  linux     ← WSL2 (추정)
```

---

## 1. Phase G — RAG 통합 스프린트

> 상태: **Phase F 완료 + ollama 원격화 완료 후 시작**
> 전략: 직접 구현 안 함. 검증된 외부 라이브러리를 paper-research에 import
> 본인 결정 (2026-04-09): "어차피 직접 구현해도 클로드 도움 없이는 못 함. 검증된 라이브러리 가져다 쓰는 게 합리적."

### 1.1 통합 대상 라이브러리

#### ① PaperQA2 (Future-House/paper-qa) — 핵심

**제공 기능**:
- PDF 폴더에 대한 high-accuracy RAG (citations 포함)
- 메타데이터 인지 임베딩 + LLM 기반 재랭킹 + 컨텍스트 요약
- agentic RAG (LLM이 쿼리 반복 정제)
- 인용수/저널 품질 자동 수집
- 로컬 PDF 풀텍스트 검색 엔진
- LiteLLM 기반 모든 LLM 지원 (Ollama 포함)

**대체 가능한 직접 구현 항목**:
- Phase G.2 벡터 임베딩 인프라
- Phase G.3 시맨틱 검색
- Phase H.4 PDF 구조화 파싱 (GROBID Docker 4GB+ 안 깔아도 됨)
- Phase J.5 추천 엔진 (부분)

**호환성**:
- pip install paper-qa
- Python 라이브러리. paper-research backend(FastAPI)에 그대로 import
- Ollama 지원: `embedding="ollama/mxbai-embed-large"` 지원
- 임베딩 모델: nomic-embed-text 또는 mxbai-embed-large (로컬, ~700MB)

**리스크**:
- Mac mini 16GB에 gemma4:e4b + 임베딩 모델 동시 적재 시 RAM 빡빡
- → **RTX 5080 데스크탑에서 paper-qa 돌리고 Tailscale로 접근** (ollama 원격화 인프라 재사용)
- multi-collection 격리 X. paper-research에서 collection별로 paper_directory 다르게 잡아 호출

#### ② findpapers (jonatasgrosman/findpapers) — 보조

**제공 기능**:
- 6개 학술 DB 동시 검색 (arXiv, IEEE Xplore, OpenAlex, PubMed, Scopus, S2)
- 자동 중복 제거
- snowballing (citation graph 빌드)
- PDF 자동 다운로드
- BibTeX/JSON export

**대체 가능한 직접 구현 항목**:
- Phase H.1 인용 관계 DB 모델 (snowball 결과로 직접 채움)
- Phase H.2 S2 인용 수집기

**주의 (v2 추가)**: findpapers의 snowballing이 citation graph를 DB 모델로 직접 뽑아주지는 않음. 결과를 파싱해서 paper_citations 테이블에 매핑하는 glue code는 직접 짜야 함. G-4 "1일"은 빡빡할 수 있음 → **1~2일로 조정**.

#### ③ Semantic Scholar MCP server (별도)

Claude Code에 직접 붙는 MCP 서버. paper-research와 별개로 본인이 Claude Code로 논문 작업할 때 사용 가능.
- alperenkocyigit/semantic-scholar-graph-api
- hamid-vakilzadeh/AIRA-SemanticScholar

### 1.2 Phase G 사양 (개요)

**Phase G-0: ollama 원격화 검증** (전제 조건)
- §0 "Phase F 부록" 완료 확인
- RTX 5080에서 paper-qa 실행 가능한 환경 확인

**Phase G-1: paper-qa standalone 검증** (반나절)
1. RTX 5080 데스크탑에 paper-qa 설치
2. 임베딩 모델 pull (`ollama pull mxbai-embed-large`)
3. CF4 collection의 PDF 중 10~20건을 임시 폴더에 모음
4. `pqa ask "CeO2 기반 CF4 분해 촉매의 메커니즘"` 실행
5. **품질 평가** — 본인이 직접 답변 만족도 확인
6. 만족스러우면 통합 진행. 아니면 전략 재검토.

**G-1 추가 검증 항목 (v2 신규 — paper-qa 동기화 전략)**:
- PDF 10건 인덱싱 후 1건 삭제 → 재질문 시 삭제된 논문이 답변에 나오는지 확인
- 결과에 따라 동기화 옵션 A/B 결정 (아래 §1.3 참조)

**Phase G-2: backend 통합** (1~2일)
- `backend/services/rag/` 신규 모듈
- `backend/routers/ai.py`에 신규 엔드포인트:
  - `POST /ai/qa` — 질문 → RAG 답변
  - `POST /ai/chat-with-papers` — 선택 논문에 대한 대화
- collection별 paper_directory 격리
- paper-qa의 내부 인덱스 캐싱 (재사용)
- ollama backend는 RTX 5080 (Tailscale 주소)
- **RAG graceful degradation 정책 적용** (§1.4 참조)

**Phase G-3: frontend 통합** (1일)
- Search 페이지에 새 모드 토글: [키워드] [의미검색(RAG)]
- 의미검색 결과: 답변 + 인용된 paper 카드 + similarity
- PaperDetail에 "이 논문에 질문하기" 버튼

**Phase G-4: findpapers 통합** (1~2일, 옵션)
- `backend/services/discovery/snowball.py` 신규
- discovery 사이클에서 옵션으로 1-hop snowballing 수행
- 결과는 새 paper_citations 테이블에 저장 (glue code 직접 작성 필요)
- frontend 인용 그래프 시각화는 Phase G-5로 별도

**Phase G-5: 인용 그래프 시각화** (옵션, 1~2일)
- Phase G-4 데이터 기반
- d3-force 또는 react-force-graph
- PaperDetail에 "인용 그래프" 탭

**총 분량**: G-0 ~ G-3까지 약 3~5일. G-4/G-5 추가 시 +2~4일.

### 1.3 paper-qa ↔ paper-research 데이터 동기화 전략 (v2 신규)

> 출처: 논문계획3.md §4

paper-qa는 자체 인덱스(벡터 DB + 문서 캐시)를 관리함. paper-research의 SQLite papers 테이블과 별개.

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

**결정 시점**: G-1 검증에서 "1건 삭제 후 재질문" 테스트 결과에 따라 결정. 본인 50~100건 규모에선 옵션 A가 충분할 가능성 높음.

### 1.4 RAG graceful degradation 정책 (v2 신규)

> 출처: 논문계획3.md §6

Phase G 이후 장애 지점이 늘어남:
- RTX 5080 데스크탑 꺼짐 → paper-qa 임베딩/추론 불가
- Tailscale 연결 끊김 → RAG 엔드포인트 타임아웃
- 임베딩 모델 + LLM 동시 로드 → OOM

**Phase G-2 구현 시 반드시 박을 것**:
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

### 1.5 외부 의존성 버전 고정 (v2 신규)

> 출처: 논문계획3.md §7

**G-1 검증 완료 후 즉시**:
```
# requirements.txt에 추가
paper-qa==5.x.x        # G-1 검증 완료 버전
findpapers==x.x.x      # G-4 검증 완료 버전 (G-4 진행 시)
litellm==x.x.x         # paper-qa 의존성, 간접 버전도 고정
```

**이유**: 3개월 뒤 `pip install paper-qa`에서 breaking change 맞으면, 그때 디버깅하느라 반나절 날림. 지금 pin 해두면 0분.

**업데이트 정책**: 분기 1회 `pip install --upgrade` → pytest 통과 확인 → 버전 갱신.

### 1.6 Phase G 사전 결정 항목 (다음 세션 시작 전)

본인이 결정해야 할 것:
- [ ] ollama 원격화 완료 여부 (§0 전제 조건)
- [ ] paper-qa 실행 호스트: RTX 5080 (권장) vs Mac mini
- [ ] G-1 standalone 검증을 별도 시간 잡아서 할지
- [ ] G-4 findpapers / G-5 인용 그래프 포함 여부 (G-3까지만 하고 일단 멈출지)
- [ ] paper-qa의 LLM 백엔드: ollama (무료, 느림) vs Claude API ($15 크레딧 사용)

---

## 2. 다른 세션 Opus Plan의 G/H/I/J/K (참고 카탈로그)

> 본인이 외부 도구 통합으로 가는 결정 했으므로, 아래는 **참고만**.
> 각 항목별로 외부 도구 대체 가능 여부 표시.

### Phase G — 검색 혁신

| 항목 | 직접 구현 분량 | 외부 도구 대체 |
|---|---|---|
| G.1 search.py 모듈 분리 | 1일 | X. 직접 구현. 우선순위 낮음. **거부됨 (REVIEW_FROM_OTHER_SESSION.md 참조)** |
| G.2 벡터 임베딩 인프라 | 3일+ | ✅ paper-qa 내장 |
| G.3 시맨틱 검색 엔드포인트 | 2일 | ✅ paper-qa 내장 |
| G.4 SQLite FTS5 | 1일 | △ paper-qa 풀텍스트 검색이 대신 |

### Phase H — 지식 그래프

| 항목 | 직접 구현 분량 | 외부 도구 대체 |
|---|---|---|
| H.1 인용 관계 DB 모델 | 0.5일 | △ findpapers snowball 결과를 저장만 하면 됨 |
| H.2 S2 인용 수집기 | 2일 | ✅ findpapers snowball |
| H.3 인용 그래프 시각화 (d3) | 2일 | X. 직접 구현 (Phase G-5) |
| H.4 PDF 구조화 파싱 (GROBID) | 3일+ | ✅ paper-qa 내장. GROBID 안 깔아도 됨 |
| H.5 자동 태그 생성 | 1일 | △ paper-qa 메타데이터 인지가 부분 대체 |

### Phase I — 자동화 엔진

| 항목 | 직접 구현 분량 | 외부 도구 대체 | 우선순위 |
|---|---|---|---|
| I.1 APScheduler | 1일 | X. 직접 구현 | **높음 — small win** |
| I.2 평가 실패 재시도 큐 | 1일 | X. 직접 구현 | 높음 (F-1.2 후속) |
| I.3 알림 확장 (이메일/webhook) | 2일 | X. 직접 구현 | 중간 |
| I.4 대시보드 agent 타임라인 | 1일 | X. 직접 구현 | 중간 |

### Phase J — 연구자 경험

| 항목 | 직접 구현 분량 | 외부 도구 대체 | 우선순위 |
|---|---|---|---|
| J.1 노트/메모 시스템 | 2일 | X. 직접 구현 | 중간~높음 |
| J.2 비교 뷰 강화 | 2일 | △ paper-qa multi-paper QA가 부분 대체 | 낮음 |
| J.3 키보드 단축키 (Cmd+K) | 1일 | X. 직접 구현 | 중간 |
| J.4 연구 일지 자동 생성 | 1일 | X. 본인 사용 패턴 관찰 후 | 낮음 |
| J.5 추천 엔진 | 3일 | ✅ paper-qa 임베딩으로 대체 | 낮음 |

### Phase K — 인프라 성숙

| 항목 | 직접 구현 분량 | 우선순위 |
|---|---|---|
| K.1 테스트 커버리지 80%+ | 3일+ | 점진 |
| K.2 Docker compose | 1일 | 보류 (단일 호스트) |
| K.3 GitHub Actions CI/CD | 1일 | 보류 (푸시 직진 패턴) |
| K.4 mypy 타입 체킹 | 2일+ | 점진 |
| K.5 자동 백업 + rotation | 0.5일 | **small win** |

---

## 3. 보류 항목 (Phase F에서 분리)

### F.1 — N+1 + 페이지네이션

**상태**: 사실 확인됨 (papers.py에 joinedload/selectinload 0건). 우선순위 낮음.

**트리거 조건**: 다음 중 하나
- collection 단일 100건 초과 (현재 CF4=85)
- Library 페이지 로딩이 체감상 1초 이상
- API 응답 측정값 > 500ms

**예상 분량**: 1일

### search.py 900줄 분리

**상태**: 거부됨. 본인 "직접 구현 안 함" 원칙에 따라 보류.
**트리거 조건**: search.py가 실제로 유지보수 부담이 됐을 때
**거부 근거**: REVIEW_FROM_OTHER_SESSION.md §4 참조

---

## 4. Phase F 운영에서 발견된 신규 항목 (v2 신규)

### 4.1 분석 진행률 추적 (사용자 발의)

> 트리거: 본인이 풀분석 추천 15편 일괄 분석 시도 후 "할 일 / 한 일" 구분 필요성 체감

**현재 동작**: 분석 실행해도 폴더 안 바뀜. 풀분석 추천 폴더에 분석 완료/미완료 논문이 섞임.

**옵션 A: analysis_status 컬럼 + 카드 배지 (권장)**
- Paper에 `analysis_status` 컬럼 추가 (`pending` / `in_progress` / `completed`)
- 폴더 분류는 그대로 유지 (관련도 등급)
- 시각: 풀분석 추천 폴더 안에서 카드에 ✅ / ⏳ 배지 표시
- 필터: "풀분석 추천 + 미완료" 같은 조합 검색

**옵션 B: 가상 폴더 (smart folder)**
- "분석 완료" = 동적 쿼리 결과 (`SELECT papers WHERE analyses.count > 0`)
- DB 컬럼 추가 X, 폴더 구조도 그대로
- 사이드바에 "스마트 폴더" 섹션 신설

**옵션 C: 실제 폴더 신설**
- 단순함, 직관적
- 단점: 폴더 분류 의미 충돌 (관련도 등급 vs 작업 상태). 원래 추천 등급 정보 사라짐.

**결정 시점**: 일괄 분석 빈도가 높아지면 자연스럽게 결정. 운영 안 해보고 미리 박으면 over-engineering.

### 4.2 frontend "분석 중" stale 상태 fix

> 트리거: Phase F 운영에서 ollama stuck → backend 503 → frontend "일괄 분석 진행 0/1 완료" 안 풀림

**현재 동작**: backend LLMError 503 응답 후 frontend "분석 중" 상태가 자동 클리어 안 됨. 브라우저 새로고침으로 우회.

**fix**: frontend의 분석 호출에서 catch(error) 시 "분석 중" 상태 리셋. 간단 fix (5줄). F 범위 밖이라 보류했음.

**분량**: 15분. I.4 대시보드 작업 또는 J.1 노트 작업과 같이 처리 가능.

### 4.3 ollama runner stuck 진단/방어

> 트리거: Mac mini gemma4:e4b 단일 분석 도중 runner stuck (CPU 13.9%, status U, 10분+)

**현재 동작**: ollama 재시작 외 복구 방법 없음.

**해결**: RTX 5080 원격화로 자연 해결 (§0). Mac mini에서 분석 안 돌리면 발생 안 함.

**추가 방어 (선택)**: strict_call에 ollama health check ping 추가. 60초 timeout으로도 안 끝나면 ollama restart 명령 보내기. over-engineering 느낌이라 보류.

---

## 5. 우선순위 추천 (Phase F 완료 기준)

```
Phase F 완료 (2026-04-10) ✅
  ↓
Phase F 부록: ollama 원격화 (30분, 집 갔을 때)
  ↓
Phase G-1: paper-qa standalone 검증 (반나절)
  - 품질 OK → G-2 진입
  - 품질 NO → 전략 재검토
  ↓
Phase G-2/G-3: backend + frontend 통합 (2~3일)
  ↓
[안정화 기간 1~2주 — 실제로 매일 사용해보고 빠진 거 발견]
  ↓
Phase I.1 + I.2: 스케줄러 + 재시도 큐 (3~4일)
  - 매일 새벽 자동 discovery
  - 평가 실패 자동 재시도
  - small win, 효과 큼
  ↓
[다시 안정화]
  ↓
Phase J.1: 노트 시스템 (2일)
  ↓
필요해지면 F.1 페이지네이션 (CF4 100건 넘을 때)
필요해지면 K.5 자동 백업
필요해지면 K.4 mypy
```

**총 예상 기간**: 본인 페이스로 6~10주 (1.5~2.5개월)
**총 작업 시간**: 약 15~25일 (풀타임 환산)

이 시점에서 paper-research가 본인 매일 워크플로의 핵심 도구가 됨. 멈추는 것 권장.

---

## 6. 절대 안 할 것들 (명시 보류)

| 항목 | 안 하는 이유 |
|---|---|
| GROBID Docker | Mac mini 16GB에 4GB+ 추가 부담. paper-qa로 대체 가능 |
| sqlite-vss 직접 통합 | M-series 호환성 의문. paper-qa의 numpy vector DB로 충분 |
| nomic-embed-text 직접 wrapping | paper-qa가 LiteLLM 통해 알아서 처리 |
| Docker compose 풀 스택 | 단일 호스트엔 굳이 |
| GitHub Actions CI | 푸시 직진 패턴 |
| Postgres 마이그레이션 | 단일 사용자엔 굳이 |
| OAuth2 / 멀티 유저 | 본인 혼자 씀 |
| GraphQL | REST로 충분 |

---

## 7. 본 문서 업데이트 정책

- Phase G/I/J 작업 시작 전: 본 문서 우선순위 재평가
- 본인 사용 패턴 변화 감지 시: 우선순위 조정
- 외부 도구 신규 발견 시: §1 통합 대상에 추가
- 완료된 항목: 본 문서에서 제거 → PHASE_*_DONE.md로 이동

---

## 8. 참고 링크

### 통합 대상 라이브러리
- PaperQA2: https://github.com/Future-House/paper-qa
- findpapers: https://github.com/jonatasgrosman/findpapers
- Paperlib (참고용 UX): https://github.com/Future-Scholars/paperlib

### Semantic Scholar MCP (Claude Code 별도 통합용)
- alperenkocyigit/semantic-scholar-graph-api
- hamid-vakilzadeh/AIRA-SemanticScholar

### 원본 Plan 문서
- 다른 세션 Opus Plan 전문: 본인 첨부 파일 "논문계획2.md"
- 결정 트래킹: docs/REVIEW_FROM_OTHER_SESSION.md

---

## 9. 다음 세션 발사 시퀀스

```bash
# 1. 컨텍스트 복원
cd ~/paper-research && source venv/bin/activate
git log --oneline -5
python -m pytest backend/tests/ --tb=no -q   # 36 passed 확인

# 2. ollama 원격화 완료 여부 확인
curl -s --max-time 3 http://100.80.119.78:11434/api/tags | head
# → JSON 뜨면 §0 완료. 안 뜨면 §0 먼저.

# 3. 본 문서 + PHASE_F_DONE.md 를 새 Claude 세션에 attach
# "Phase G-1부터 시작" 지시

# 4. G-1 paper-qa standalone 검증 → 결과에 따라 G-2 진입
```

---

> 본 문서는 즉시 작업 대상이 아님. Phase F 완료 후 다음 세션에서 Phase G 시작 시 참조.
> 매번 우선순위를 본인이 직접 결정하는 자료. 클로드/클로드코드는 본 문서를 자동 실행하지 않음.
