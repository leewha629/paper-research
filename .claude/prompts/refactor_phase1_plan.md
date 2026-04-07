역할: paper-research 리팩토링 계획 수립자.
제약: 코드 수정 절대 금지. 추가 조사 금지(AUDIT만 신뢰). 산출물은 docs/REFACTOR_PLAN.md 단 하나, 직접 Write.

## 입력
- docs/AUDIT_2026Q2.md를 먼저 통째로 읽어라. 위험 Top 10이 작업 우선순위의 유일한 근거다.

## 출력 구조 (docs/REFACTOR_PLAN.md)

### 0. 의존성 결정 (가장 먼저 작성)
AUDIT Top 10을 보고 다음을 직접 결정하라:
- 어느 항목이 다른 항목의 선행 조건인가?
- 어느 항목이 병렬 가능한가?
- 어느 항목이 "안전망" 역할이라 가장 먼저 와야 하는가? (예: 테스트 스캐폴딩이 리팩토링 전에 와야 하는가, 후에 와야 하는가?)
- 결정 근거를 2~3줄로 명시. "직관"이 아니라 "X가 깨지면 Y를 검증할 수 없으므로" 형식.
- 최종 단계 순서를 Phase A, B, C... 로 라벨링. Phase 개수는 4~7개 사이에서 직접 정해라.
- 단계 의존 그래프 텍스트로 그려라.

### 1~N. 각 Phase 상세
각 Phase마다:
- **목표**: 한 줄
- **해결하는 AUDIT 항목**: Top 10 중 어느 번호인지
- **변경 파일 목록**: 파일:라인 단위
- **작업 분량**: S(<1h) / M(1~3h) / L(>3h)
- **선행 Phase**: 어느 Phase가 끝나야 시작 가능한지
- **검증 방법**: 이 Phase가 성공했음을 어떻게 확인하나? (테스트 / 수동 점검 / 로그 패턴)
- **사용자 체크포인트**: Phase 종료 시 사용자가 직접 확인해야 할 항목 (3~5개 체크리스트)
- **롤백**: 망했을 때 어느 커밋/파일로 되돌리나

### 마지막 섹션: 위험과 미해결 질문
- AUDIT에 없어서 추측한 부분이 있다면 "확인 필요" 마커로 명시
- Phase 진행 중 막힐 가능성이 가장 높은 지점 3개

## 필수 내용 — 반드시 다뤄야 함 (Phase 배치는 자유)

1. **AI 호출 단일화**: services/llm/ollama_client.py:strict_call 시그니처 설계 (expect_json/schema/retry/timeout). AUDIT §2의 호출 16개 마이그레이션 단계
2. **사일런트 폴백 제거**: AUDIT §4의 ai_score_papers / alerts.py 5.0 / translate / expand_keywords 4건. fail-loud 정책 + UI 표면화 방안
3. **점수 캘리브레이션**: RELEVANCE_SYSTEM 프롬프트 개정안 + few-shot (CF₄/할로겐/VOC 인접 = 4~5 강제). 본인 분야 키워드는 사용자가 직접 채울 수 있게 TODO 마커
4. **회귀 테스트 스캐폴딩**: pytest 구조 / fixture / mock ollama. 최소 30개 테스트 목록
5. **Discovery 안정화**: _discovery_running dict race 해결 (DB lock / file lock / Redis 중 어느 것이 paper-research 규모에 맞는지 직접 판단), heartbeat, 멀티프로젝트 격리 검증
6. **bootstrap ACID**: Collection/Folder 트랜잭션 경계, 부분 실패 롤백
7. **죽은 API / 미연결 UI**: 삭제 vs 연결 결정

## 작성 방식
- 메모리에 모았다가 마지막에 쓰지 마라. 섹션 하나 완성될 때마다 docs/REFACTOR_PLAN.md에 append 또는 직접 Write로 점진적으로 채워라.
- 추측 금지. AUDIT 인용할 때는 §번호와 줄 번호 같이 적어라.
