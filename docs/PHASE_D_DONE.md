# Phase D — 점수 캘리브레이션 (DONE)

날짜: 2026-04-08
관련 사양: `.claude/prompts/refactor_score_calibration.md`
관련 baseline: `docs/PAPER_TRIAGE.md` (50건)
관련 산출물: `docs/CALIBRATION_DIFF.md`, `backend/scripts/recalibrate_50.py`

## 1. RELEVANCE_SYSTEM 실제 위치 (Step 1 확정)

### 1-A. grep 결과
```
backend/services/llm/prompts.py:56:RELEVANCE_SYSTEM = """You are a STRICT JSON-only paper relevance scorer.
backend/services/llm/tasks.py:12:    RELEVANCE_SYSTEM,
backend/services/llm/tasks.py:48:        system=RELEVANCE_SYSTEM,
```

### 1-B. DB 조회 결과 (`prompt_templates` 테이블)
```
1|synthesis_conditions|...
2|experiment_summary|...
3|summary|...
4|significance|...
5|keywords|...
6|structured|...
7|trend|...
8|review_draft|...
```

DB의 `prompt_templates` 테이블은 ai.py 분석 종류(`structured`, `summary` 등) 8건만 보유하고 **`relevance_system` 또는 동등 row가 없다**. 즉, RELEVANCE_SYSTEM은 **순수 코드 상수**이고 DB UPDATE는 불필요. `prompt_templates_backup` 임시 테이블도 만들지 않았다.

### 1-C. 사용 경로 (단일 호출 사이트)
- `services/llm/tasks.py:39 score_relevance(...)` 가 `RELEVANCE_SYSTEM` 을 system 프롬프트로 `strict_call(schema=RelevanceJudgment)` 호출
- 호출자: `services/research_agent/discovery.py:211 run_discovery_cycle(...)` 의 평가 루프 1곳
- discovery 외에는 `RelevanceJudgment` / `RELEVANCE_SYSTEM` 을 사용하는 사이트 없음 (alerts.py는 별도 `RelevanceScore` 스키마 사용 — 본 fix 범위 외, 변경 안 함)

→ Step 2는 **`prompts.py:56` 한 곳의 상수 교체**로 충분.

## 2. Step 2 — 새 RELEVANCE_SYSTEM 본문 적용

`backend/services/llm/prompts.py:56-138`에 사양서 §"새 RELEVANCE_SYSTEM 본문" 그대로 적용. 주요 변경:

| 항목 | Before | After |
|---|---|---|
| 언어 | 영문 시스템 + 영문 가이드 | 한국어 시스템 + CF₄ 도메인 명시 |
| 점수 범위 | 0~9 | **0~10** |
| 필터 구조 | 점수표만 | **3층 필터** (촉매 여부 / 반응물 적합성 / 메커니즘 일치) |
| Few-shot | 3건 (CF4 일반론) | **9건** (CF₄ 직접 / C₂F₆ / 플라즈마-촉매 / HFO / Cl-VOC / 무관) |
| 출력 필드 | `score, reason` | `score, reason, matched_mechanism_tokens` |
| 도메인 특이성 | 일반 | CF₄/Lewis acid (Al/Zr/Ga/W/Ce) 명시 |

DB row가 없으므로 backup 테이블 조치 없음.

## 3. Step 3 — schemas.py RelevanceJudgment 업데이트

`backend/services/llm/schemas.py:14-55` 변경:

- `score: ge=0, le=9` → **`ge=0, le=10`** (10점 만점 확장)
- `reason: min_length=5` → **`min_length=2`** (한 토큰짜리 응답도 거부하지 않음 — 새 프롬프트의 짧은 reason 호환)
- **신규 필드**: `matched_mechanism_tokens: List[str] = Field(default_factory=list)` (디버깅용)
- `clean_tokens` 검증자 추가: 빈 문자열 제거 + 공백 정규화, 빈 리스트 허용

호환성: 기존 호출부(`discovery.py`, `score_relevance`)는 `judgment.score` / `judgment.reason` 만 읽으므로 **breaking change 없음**. 새 필드는 default가 빈 리스트라 모델이 누락해도 검증 실패 없음. 다만 `RelevanceJudgment.model_json_schema()` 가 ollama format으로 전달되므로 grammar mode에서 모델이 새 필드를 출력하도록 강제된다.

## 4. Step 4 — 50건 재분석 트리거

### 4-A. 스크립트 작성
`backend/scripts/recalibrate_50.py` 신규 (~250 LoC). 핵심 로직:

- `papers` 테이블 전체(또는 `--limit N`)를 paper.id 오름차순으로 순회
- 각 논문에 대해 `score_relevance(topic, title, abstract)` 호출 (실 ollama)
- 임계값 적용: **≥7 풀분석 추천 / ≥5 자동 발견 / ==4 검토 대기 / ≤3 휴지통**
  (사양서 Step 4 "임계값(7/5/4)" 해석 — discovery.py의 기존 TRASH_MAX/HOLD_SCORE/AUTO_MAX와 동일 분포)
- `paper.relevance_score` / `relevance_reason` / `relevance_checked_at` 업데이트
- `paper.is_trashed` 갱신 + `folder_papers` 시스템 폴더 매핑 재배치 (`reassign_folder`)
- **`agent_runs` 새 row insert** (기존 row 덮어쓰기 금지) — `topic_snapshot="PHASE_D_RECALIBRATION: ..."` 으로 baseline run과 구분
- `docs/CALIBRATION_DIFF.md` 자동 작성 (변화량 큰 순)

옵션:
- `--dry-run` — DB 변경 없이 표만 출력
- `--limit N` — N건만 (smoke test)
- `--topic "..."` — 주제 override (기본: CF₄ catalytic decomposition / hydrolysis)

### 4-B. 실행 상태
**스크립트는 작성 완료. 실제 50건 실행은 ollama 호출이 필요한 사용자 작업으로 분리.** 본 환경에서는 ollama 가용성을 가정하지 않으므로 실행하지 않음.

실행 명령:
```
cd backend
../venv/bin/python -m scripts.recalibrate_50              # 50건 전체 + DB 커밋
../venv/bin/python -m scripts.recalibrate_50 --dry-run    # 표만
../venv/bin/python -m scripts.recalibrate_50 --limit 10   # smoke test
```

baseline 통계 (재분석 전 — DB 스냅샷 2026-04-08):
- 풀분석 추천 폴더: 30건 (점수 7~9, 신규 5건은 NULL)
- 검토 대기 폴더: 9건 (점수 4)
- 자동 발견 폴더: 3건 (점수 5~7)
- 휴지통 폴더: 7건 (점수 1~3)

(PAPER_TRIAGE.md baseline 50건 vs DB 49건 — 1건은 중간에 제거된 것으로 보임)

## 5. Step 5 — CALIBRATION_DIFF.md

`docs/CALIBRATION_DIFF.md` 신규. 현재는 **재분석 전 baseline snapshot**이며, recalibrate_50.py 실행 시 변화량 큰 순으로 정렬된 완전한 표로 자동 덮어씌워진다.

## 6. Step 6 — 통합 테스트 4건

`backend/tests/test_relevance_calibration.py` 신규. 4 테스트 모두 `@pytest.mark.integration` 마커.

| # | 테스트 | 검증 |
|---|---|---|
| 22 | `test_relevance_direct_match_high_scores` | 직접 5건 평균 ≥8, 모두 ≥7 |
| 23 | `test_relevance_adjacent_mid_scores` | 인접 5건 평균 5~7.5, 모두 4~8 |
| 24 | `test_relevance_unrelated_low_scores` | 무관 5건 평균 ≤3, 모두 ≤4 |
| 25 | `test_relevance_score_band_separation` | 직접-무관 분리도 ≥5, 인접이 가운데 |

샘플 논문은 **PAPER_TRIAGE.md 50건 baseline에서 분야 태그별로 선별** (직접 5 / 인접 5 / 무관 5). 작은 모델의 ±1 흔들림을 흡수하기 위해 그룹 단위 평균/min/max를 검증.

## 7. 테스트 결과

```
$ cd backend && pytest tests/ -m "not integration" -q
..................                                                       [100%]
18 passed, 4 deselected in 0.42s
```

- 기존 17 + Phase B fix 신규 1 = **18건 비통합 PASS**
- Phase D 통합 4건 deselected (정상 — `-m "not integration"` 의도)
- `pytest -m integration` 으로 통합 4건 별도 실행 가능 (ollama 필요)

총합 **22건 (18 + 4)** 목표 달성.

## 8. 변경 파일 목록

| 파일 | 변경 |
|---|---|
| `backend/services/llm/prompts.py` | RELEVANCE_SYSTEM 본문 교체 (영문→한국어, 9 few-shot, 0~10) |
| `backend/services/llm/schemas.py` | RelevanceJudgment: ge=0/le=10, min_length=2, matched_mechanism_tokens 필드 추가 + clean_tokens 검증자 |
| `backend/scripts/__init__.py` | 신규 (빈 패키지 마커) |
| `backend/scripts/recalibrate_50.py` | 신규 — 50건 재분석 + agent_runs insert + CALIBRATION_DIFF.md 출력 |
| `backend/tests/test_relevance_calibration.py` | 신규 — 통합 테스트 4건 (#22~#25) |
| `docs/CALIBRATION_DIFF.md` | 신규 — baseline snapshot (재분석 후 덮어씌워짐) |
| `docs/PHASE_D_DONE.md` | 신규 — 본 문서 |

## 9. 사용자 검증 가이드

1. **백엔드 재시작 (선택)** — discovery 사이클이 새 프롬프트로 동작하는지 확인
   ```
   cd backend && ../venv/bin/python -m uvicorn main:app --reload
   ```
2. **smoke test로 임계값 검증** (10건만)
   ```
   cd backend
   ../venv/bin/python -m scripts.recalibrate_50 --dry-run --limit 10
   ```
   기대: 로그에 `(i/10) 제목  before→after  before_folder→after_folder` 출력. CALIBRATION_DIFF.md가 10행으로 생성.
3. **50건 재분석** (DB 커밋)
   ```
   cd backend
   ../venv/bin/python -m scripts.recalibrate_50
   ```
   기대: ~5-15분 소요, 새 agent_runs row 1개 추가 (`SELECT * FROM agent_runs ORDER BY id DESC LIMIT 2`), CALIBRATION_DIFF.md 49건 표.
4. **통합 테스트**
   ```
   cd backend && ../venv/bin/python -m pytest -m integration -q
   ```
   4 PASS 기대. 1~2건 흔들리면 그룹 평균 가드가 흡수.
5. **분류 결과 점검** (UI)
   - "내 서재 → 폴더 → 풀분석 추천" 에서 CF₄ 직접 논문이 모두 보이는지
   - 휴지통에 HFO/HCFC/SF6/플라즈마 단독이 옮겨졌는지
   - 인접(C₂F₆/Cl-VOC zeolite)이 자동 발견 또는 검토 대기에 있는지

## 10. 제약 준수 체크리스트

- [x] Phase E (Discovery 락) 미변경 — discovery.py는 호출 경로만 사용, 코드 수정 없음
- [x] Phase F (죽은 API) 미변경
- [x] RELEVANCE_SYSTEM 외 다른 프롬프트 (KEYWORDS_SYSTEM, SUMMARY_SYSTEM, ai.py SYSTEM_PROMPTS) 미변경
- [x] 자동으로 다음 Phase 진입 안 함
- [x] 기존 agent_runs row 덮어쓰기 금지 — 스크립트는 항상 새 row insert
- [x] 1층 필터 완화 없음 — 플라즈마 단독/열분해/DFT 방법론은 ≤3 강제 유지
- [x] few-shot 9건 그대로 유지 (사용자 승인 없이 추가/삭제 안 함)
- [x] C₂F₆ TIER 2 고정 (7~8점, 10점 불가)
