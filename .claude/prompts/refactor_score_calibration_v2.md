역할: paper-research recalibrate 스크립트 + RELEVANCE_SYSTEM v2.

## 진단된 문제 4가지
1. **Collection 격리 부재 (가장 심각)**: recalibrate_50.py가 collection 필터 없이 모든 paper에 CF4 RELEVANCE_SYSTEM 적용. 본인은 multi-project (CF4, CPN/CPL, 향후 AI/3D) 운영자. CPN/CPL 연구 자료가 CF4 도메인으로 평가받아 휴지통 행. 사용자 미래 6월 과제 자료가 위험.
2. **할루시네이션**: abstract NULL인 논문에 LLM이 촉매 조성/메커니즘을 추측해서 점수 인플레이션. "Lewis acid 기반 다중 금속 산화물"이라고 reason에 박는데 abstract가 없음. 제목만으로 그런 디테일 알 수 없음.
3. **NF3/SF6 함정**: molten metal 반응 매체 같은 비촉매 PFC abatement 논문이 7점 받음. "PFC abatement"라는 표면 키워드 매칭에 가산점 너무 큼.
4. **Cl-VOC zeolite 룰 over-application**: zeolite 아닌 페로브스카이트/CeO₂ Cl-VOC 논문에 5점 줌. 본인 zeolite 예외 룰을 LLM이 일반화함.

## 작업 1 — recalibrate_50.py를 v2로 교체

### 신규 시그니처
backend/scripts/recalibrate.py (이름 변경 — "50" 제거. 일반화)

### 필수 변경
- **CLI 옵션 추가**: `--collection <name>` 필수 인자. 미지정 시 에러로 종료.
- collection 이름으로 paper_collections 테이블 조회 → paper_id 목록 → 그 ID만 처리
- 안전장치: --collection 미지정 시 "ERROR: --collection is required (e.g., --collection CF4)" 출력 후 exit 1
- --dry-run 플래그 진짜로 동작 확인 (folder_papers 변경 없음, agent_runs 새 row 없음, paper.relevance_score 업데이트 없음, CALIBRATION_DIFF.md 만 작성)
- --dry-run 미지정 시 backup 자동 생성 (data/backups/papers_pre_recalibrate_<ts>.db)

### 출력 파일명
- docs/CALIBRATION_DIFF_<collection>_<ts>.md (collection 별 분리)

## 작업 2 — RELEVANCE_SYSTEM v2 (할루시 방지 + 룰 강화)

backend/services/llm/prompts.py의 RELEVANCE_SYSTEM에 다음 추가:

### 0층 필터 — Abstract 가용성 (1층보다 먼저)
입력에 abstract가 없거나 50자 미만이면:
- 절대 5점 이상 금지
- reason에 "abstract 부재로 메커니즘 확인 불가" 명시
- matched_mechanism_tokens는 제목에서 확인 가능한 토큰만
- 제목에 "CF4" + "catalyst/catalytic" 둘 다 있으면 최대 5점
- 제목에 "CF4"만 있으면 최대 4점
- 그 외는 최대 3점

이 룰은 1층/2층/3층 필터보다 우선한다. 추측 금지.

### 2층 필터 강화 — 비촉매 PFC abatement
다음 키워드가 제목에 있고 "catalyst/catalytic" 토큰이 없으면 최대 4점:
- "molten metal" / "molten salt" 반응
- "destruction and removal" (촉매 명시 없음)
- "scrubber" / "wet scrubber"
- "thermal abatement" 단독

### 3층 필터 강화 — Cl-VOC zeolite 예외 좁히기
"zeolite 기반 할로겐 organics" 5점 룰은 다음 조건 모두 만족 시에만 적용:
- 제목 또는 abstract에 "zeolite" / "ZSM" / "BEA" / "MFI" 등 zeolite 골격 명시
- 동시에 chlorinated organics 처리

위 조건 미충족 시 (페로브스카이트, CeO₂, Co/Ce, MnOx 등 다른 촉매로 Cl-VOC 처리) → 최대 3점

### Few-shot 예시 추가 (기존 9개 + 4개 신규)
[예시 10 — 할루시 방지] 제목 "Innovative Surface Wave Plasma Reactor for PFC", abstract 없음
→ {"score": 3, "reason": "abstract 부재. surface wave plasma는 일반적으로 촉매 없는 기술이며 제목에 catalyst 토큰 없음.", "matched_mechanism_tokens": ["PFC", "plasma only (inferred from title)"]}

[예시 11 — 할루시 방지 한도 5] 제목 "Plasma-Catalyst Combination for CF4 Removal", abstract 없음
→ {"score": 5, "reason": "abstract 부재. 제목에 CF4 + catalyst 둘 다 있어 최대 5점.", "matched_mechanism_tokens": ["CF4", "plasma-catalyst (title only)"]}

[예시 12 — 비촉매 PFC] 제목 "Destruction and removal of NF3, SF6 in molten metal", catalyst 키워드 없음
→ {"score": 3, "reason": "molten metal 반응 매체는 촉매 가수분해와 메커니즘 다름. SF6/NF3는 다른 원자 중심.", "matched_mechanism_tokens": ["NF3", "SF6", "molten metal (non-catalytic)"]}

[예시 13 — Cl-VOC 비-zeolite] 제목 "P-Co-LaCoO3 perovskite for dichlorobenzene catalytic destruction"
→ {"score": 2, "reason": "페로브스카이트 기반 Cl-VOC. zeolite 아니므로 5점 룰 미적용. C-Cl과 C-F는 메커니즘 다름.", "matched_mechanism_tokens": ["perovskite", "dichlorobenzene", "non-zeolite"]}

## 작업 3 — 실제 실행 분리
스크립트 v2 작성 후 자동 실행 금지. 사용자가 직접 다음 순서로 실행:
1. python scripts/recalibrate.py --collection CF4 --dry-run
2. dry-run 결과 확인
3. python scripts/recalibrate.py --collection CF4

## 작업 4 — 산출물
- backend/scripts/recalibrate.py (v2, 이름 변경)
- backend/scripts/recalibrate_50.py (구버전 — 안전을 위해 삭제 금지, deprecation 주석만)
- backend/services/llm/prompts.py — RELEVANCE_SYSTEM v2
- docs/PHASE_D_V2_DONE.md — 변경 표 + 사용자 검증 가이드

## 금지
- 실제 DB 변경 금지 (사용자가 명시 실행)
- collection 필터 없는 호출 가능한 인터페이스 유지 금지 (필수 인자로 강제)
- 기존 backup 파일 삭제 금지
- 기존 agent_runs row 덮어쓰기 금지