역할: paper-research RELEVANCE_SYSTEM 프롬프트 개정 + 저장된 50건 재분석.

## 단일 진실원
- docs/REFACTOR_PLAN.md §"Phase D — 점수 캘리브레이션"
- docs/PAPER_TRIAGE.md — 현재 baseline 50건
- 본 프롬프트의 §"새 RELEVANCE_SYSTEM 본문" — 최종 프롬프트 텍스트

## 제약
- Phase E 작업 금지 (Discovery 락)
- Phase F 작업 금지 (죽은 API)
- RELEVANCE_SYSTEM 외 다른 프롬프트 변경 금지
- 자동으로 다음 Phase 진입 금지

## 작업 순서

### Step 1 — RELEVANCE_SYSTEM 실제 위치 확정
PLAN §D.1에 "확인 필요"로 남아있음. 먼저 grep으로 확정:
  grep -rn "RELEVANCE\|relevance.*system\|관련도\|score.*paper\|scoring.*prompt" backend/ --include="*.py"
  sqlite3 data/papers.db "SELECT id, name, substr(system_prompt,1,80) FROM prompt_templates" 2>/dev/null
결과를 docs/PHASE_D_DONE.md §1에 기록.

### Step 2 — 새 RELEVANCE_SYSTEM 본문 적용
아래 "새 RELEVANCE_SYSTEM 본문" 섹션을 확정된 위치에 적용.
- 코드 상수면 파일 교체
- DB row면 UPDATE + 변경 전 row를 prompt_templates_backup 임시 테이블에 저장
- services/llm/tasks.py 또는 prompts.py 경유면 그 파일 수정

### Step 3 — schemas.py RelevanceScore 업데이트
backend/services/llm/schemas.py의 RelevanceScore 모델에 matched_mechanism_tokens: list[str] 필드 추가 (디버깅용).

---

## 새 RELEVANCE_SYSTEM 본문 (아래 내용을 그대로 적용)
당신은 환경촉매/화학공학 분야 논문의 관련도를 0~10으로 평가한다.
사용자의 주 연구 분야: CF₄ (tetrafluoromethane, PFC-14) 촉매 분해, 
특히 Lewis acid 기반 가수분해 (Al/Zr/Ga/W/Ce 산화물 조합).

## 평가 원칙 (우선순위 순)

### 1층 필터 — 촉매 여부 (절대 조건)
- 촉매가 반응의 핵심이어야 한다.
- 다음은 촉매 연구가 아니므로 점수 3점 이하로 강제한다:
  * 플라즈마 단독 분해 (DC arc, microwave plasma, surface wave plasma 등)
  * 열분해 단독 (thermal decomposition without catalyst)
  * DFT 계산 방법론 논문 (촉매 설계가 아닌 계산법 보고)
  * 냉매/절연가스 안정성 평가 (분해가 아닌 안정성)
- 예외 — "플라즈마-촉매 결합 (NTP + catalyst, plasma-catalyst synergy)"은 촉매 역할이 명확하면 합격.

### 2층 필터 — 반응물 적합성
다음 반응물에 대한 촉매 분해/가수분해만 점수 6점 이상 가능:
- CF₄ (tetrafluoromethane, PFC-14) — 직접 일치, 10점 가능
- C₂F₆ (hexafluoroethane, PFC-116) — 같은 메커니즘, 7~8점
- CHF₃ (trifluoromethane, HFC-23) — 같은 메커니즘, 7점
- 기타 C1~C2 perfluoro with catalytic hydrolysis — 6점

다음 반응물은 F를 포함하지만 탈락 (최대 4점):
- SF₆, NF₃ (다른 원자 중심)
- HFO (1234ze, 1336mzz 등), HCFC — 냉매 평가, 분해 목적 아님
- C₃+ perfluoro alcohol/ketone
- C4F7N, C6F12O — 전기 절연가스 계열
- HFC-134a류 DFT — 방법론 참고 정도

다음은 할로겐이지만 탈락 (최대 4점):
- Cl-VOC (dichlorobenzene, chloromethane, chlorobenzene 등) — Cl 활성화는 F 활성화와 메커니즘 다름
- 단, zeolite 기반 할로겐 처리 일반론은 5점 (참고 가능)

### 3층 필터 — 촉매 메커니즘 일치
가산 요건 (있으면 +1~2점, 상한선 내에서):
- Lewis acid site catalysis (Al³⁺, Zr⁴⁺, Ga³⁺, W⁶⁺)
- Sulfated metal oxide / super acid
- Metal oxide composite (특히 Al-Zr-W 계열 — 사용자 연구 시스템)
- C-F bond hydrolysis / activation / cleavage 메커니즘 명시

감산 요건 (있으면 -2~3점):
- 지지체만 공유하고 반응이 다름 (γ-Al₂O₃ on CO oxidation, TWC, PDH, methane reforming 등)
- 같은 지지체라도 반응물이 탄화수소, 메탄올, 바이오매스 등이면 탈락 (1~2점)

## 점수 구간 정의

- 10: CF₄ 직접 + 촉매 설계 + 메커니즘 명시 + 리뷰/1st-tier 저널
- 8~9: CF₄ catalytic hydrolysis/decomposition 연구, 촉매 성능 보고
- 7: CF₄ 리뷰 일반론 / C₂F₆ catalytic hydrolysis / PFC-14 hydrolysis engineering
- 6: Plasma-catalyst synergy for CF₄ / Sulfated super acid on Al/Zr 일반론 (CF₄ 직접 언급 없어도)
- 5: Zeolite 기반 할로겐 organics 처리 / Ga/Zr/Al 조합 on other halogens
- 3~4: 다른 F-화합물 (HFO, HCFC, HFC, 절연가스) 분해 / DFT 방법론 / 열분해
- 1~2: 같은 지지체 쓰는 완전 다른 반응 (CO oxidation, TWC, PDH, reforming, VOC 산화)
- 0: 탄화수소 일반, 바이오매스, 의학, 무기화학, AI/ML, 3D 모델링

## Few-shot 예시 (반드시 이 분포를 따를 것)

[예시 1] "Hydrolytic decomposition of CF4 over alumina-based binary metal oxide catalysts"
→ {"score": 10, "reason": "CF₄ 직접 + Al 기반 촉매 + hydrolysis 메커니즘", "matched_mechanism_tokens": ["CF4", "hydrolytic decomposition", "alumina", "catalyst"]}

[예시 2] "Catalytic hydrolysis of C2F6 over Al2O3-ZrO2"
→ {"score": 7, "reason": "C₂F₆는 CF₄와 같은 메커니즘. Al-Zr 조합 촉매.", "matched_mechanism_tokens": ["C2F6", "catalytic hydrolysis", "Al2O3-ZrO2"]}

[예시 3] "Ce/Al2O3 plasma-catalytic removal of CF4"
→ {"score": 9, "reason": "CF₄ 직접 + 플라즈마-촉매 결합. 촉매 역할 명확.", "matched_mechanism_tokens": ["CF4", "plasma-catalytic", "Ce/Al2O3"]}

[예시 4] "High-Efficiency PFC Abatement via Microwave Plasma"
→ {"score": 2, "reason": "플라즈마 단독, 촉매 없음. 1층 필터 탈락.", "matched_mechanism_tokens": ["PFC", "plasma only, no catalyst"]}

[예시 5] "Thermal decomposition of HFO-1234ze(Z)"
→ {"score": 3, "reason": "HFO는 냉매, CF₄ 메커니즘 아님. 열분해로 촉매 없음.", "matched_mechanism_tokens": ["HFO", "thermal, no catalyst"]}

[예시 6] "Promoted adsorption of methyl mercaptan by γ-Al2O3 with Cu/Mn"
→ {"score": 1, "reason": "γ-Al₂O₃ 지지체만 공유. 반응물이 CH₃SH로 완전 다름.", "matched_mechanism_tokens": ["gamma-Al2O3", "unrelated reaction: mercaptan"]}

[예시 7] "Effective toluene oxidation under ozone over mesoporous MnOx/γ-Al2O3"
→ {"score": 1, "reason": "VOC 산화. 지지체만 공유, 메커니즘 무관.", "matched_mechanism_tokens": ["toluene oxidation", "shared support only"]}

[예시 8] "H-zeolite multi-interface for chlorinated organics abatement"
→ {"score": 5, "reason": "제올라이트 기반 할로겐 처리 일반론. Cl은 F와 다르지만 촉매-할로겐 활성화 원리 참고 가능.", "matched_mechanism_tokens": ["zeolite", "chlorinated organics", "halogen abatement"]}

[예시 9] "Deep learning for protein folding"
→ {"score": 0, "reason": "완전 무관 분야.", "matched_mechanism_tokens": []}

## 출력 형식 (엄격)
반드시 JSON 단일 객체. markdown fence 금지.
{"score": <0~10 정수>, "reason": "<한 문장 한국어>", "matched_mechanism_tokens": ["<토큰1>", "<토큰2>", ...]}
---

### Step 4 — 재분석 트리거
저장된 50건을 새 프롬프트로 재평가. 수단:
- 기존 "전체 분석" 엔드포인트가 재분석 지원하면 그거 사용
- 없으면 backend/services/research_agent/discovery.py의 score_relevance를 루프로 호출하는 일회성 스크립트 backend/scripts/recalibrate_50.py 생성
- 결과는 agent_runs에 새 row로 기록 (기존 row 덮어쓰지 말 것 — baseline 비교 가능하게)
- paper.relevance_score 컬럼 업데이트, paper.folder_id는 임계값(7/5/4)에 맞춰 자동 재배치

### Step 5 — baseline 비교 생성
docs/CALIBRATION_DIFF.md 신규:
| 제목 | 이전 점수 | 이전 폴더 | 신규 점수 | 신규 폴더 | 변화 |
50건 전부. 변화 큰 순으로 정렬.

### Step 6 — 테스트 추가
PLAN §A.2의 "Phase D 종료 시 추가 (4건)" 테스트 #22~#25 작성.
- 통합 테스트로 마커: @pytest.mark.integration
- 실제 ollama 호출 (mock 아님)
- sample_papers.py의 분야 태그 사용 — CF₄ 직접 5건 / 인접 5건 / 무관 5건을 본인 TRIAGE 50건에서 선별
- 기대 분포: 직접 ≥8, 인접 5~7, 무관 ≤3

## 산출물
1. docs/PHASE_D_DONE.md — Step 1 확정 위치 + Step 2 적용 결과 + Step 4 재분석 통계
2. docs/CALIBRATION_DIFF.md — 50건 before/after 표
3. backend/scripts/recalibrate_50.py (필요시)
4. 신규 테스트 4건 (@pytest.mark.integration 마커)
5. 테스트 결과: 18 (기존) + 4 (Phase D) = 22건 목표. 단 통합 테스트 4건은 ollama 필요하므로 pytest -m "not integration"으로 18건만 돌려도 PASS여야 함

## 금지
- 기존 agent_runs row 덮어쓰기 금지 (baseline 비교 보존)
- 1층 필터를 완화하는 방향의 프롬프트 변경 금지
- few-shot 예시 추가/삭제 사용자 승인 필요
- C2F6을 TIER 1로 올리기 금지 — TIER 2 고정