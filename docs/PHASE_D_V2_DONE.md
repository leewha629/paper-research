# Phase D v2 — Collection 격리 + 할루시 방지 + 룰 강화 (DONE)

날짜: 2026-04-08
사양: `.claude/prompts/refactor_score_calibration_v2.md`
선행: `docs/PHASE_D_DONE.md` (v1, RELEVANCE_SYSTEM 첫 캘리브레이션)

## 0. 진단된 문제 4가지 (요약)

1. **Collection 격리 부재 (가장 심각)** — `recalibrate_50.py`가 컬렉션 필터 없이
   모든 paper에 CF4 RELEVANCE_SYSTEM 적용. CPN/CPL 등 타 프로젝트 자료가 휴지통 위험.
2. **할루시네이션** — abstract NULL인 논문에 LLM이 촉매 조성/메커니즘을 추측해 점수 인플레이션.
3. **NF3/SF6 함정** — molten metal 같은 비촉매 PFC abatement 논문이 7점.
4. **Cl-VOC zeolite 룰 over-application** — 페로브스카이트/CeO₂도 5점 받음.

## 1. 변경 표

| 산출물 | 변경 | 비고 |
|---|---|---|
| `backend/scripts/recalibrate.py` | **신규** (v2) | `--collection` 필수, dry-run 진짜 동작, 자동 백업 |
| `backend/scripts/recalibrate_50.py` | deprecation 주석만 | 삭제 금지 (사양). 원본 코드 그대로 보존 |
| `backend/services/llm/prompts.py` | RELEVANCE_SYSTEM 패치 | 0층 추가 / 2층·3층 보강 / few-shot 4건 추가 |
| `docs/CALIBRATION_DIFF_<collection>_<ts>.md` | 출력 경로 변경 | collection 별 + 타임스탬프로 분리 |
| `data/backups/papers_pre_recalibrate_<ts>.db` | 실행 시 자동 생성 | dry-run 시 미생성 |

## 2. RELEVANCE_SYSTEM v2 — 핵심 룰 변화

### 2-A. 0층 필터 — Abstract 가용성 (신규, 1/2/3층보다 우선)

abstract 없거나 50자 미만 → 절대 5점 이상 금지. 추측 금지.

| 제목 토큰 | 0층 점수 상한 |
|---|---|
| CF4 + catalyst/catalytic 둘 다 | **5점** |
| CF4만 (catalyst 없음) | **4점** |
| 그 외 | **3점** |

`reason`에 반드시 "abstract 부재로 메커니즘 확인 불가" 문구.

### 2-B. 2층 보강 — 비촉매 PFC abatement

제목/abstract에 다음 키워드가 있고 catalyst 토큰이 함께 명시되지 않으면 **최대 4점**:
- molten metal / molten salt
- destruction and removal (촉매 명시 없음)
- scrubber / wet scrubber
- thermal abatement 단독
- incineration / combustion abatement 단독

→ "PFC abatement"라는 표면 키워드 매칭만으로 7점 이상 주는 것 금지.

### 2-C. 3층 보강 — Cl-VOC zeolite 5점 룰 좁히기

5점 적용은 **아래 두 조건 모두** 만족 시:
1. 제목/abstract에 zeolite 골격 명시 (zeolite / ZSM-5 / BEA / MFI / FAU / Y / mordenite 등)
2. 동시에 chlorinated organics 처리 (DCB, CB, TCE, chloromethane, vinyl chloride 등)

미충족 시 (LaCoO₃, CeO₂, Co/Ce, MnOx, spinel, hydrotalcite 등) → **최대 3점**.

### 2-D. Few-shot 예시 신규 4건

| # | 시나리오 | 기대 점수 |
|---|---|---|
| 10 | "Surface Wave Plasma Reactor for PFC", abstract 없음 | 3 (0층, 비촉매) |
| 11 | "Plasma-Catalyst Combination for CF4 Removal", abstract 없음 | 5 (0층 상한) |
| 12 | "Destruction and removal of NF3/SF6 in molten metal" | 3 (2층 보강) |
| 13 | "P-Co-LaCoO3 perovskite for DCB destruction" | 2 (3층 보강) |

## 3. recalibrate.py v2 — 인터페이스 변경

### 3-A. CLI

```
python -m scripts.recalibrate --collection <NAME> [--dry-run] [--limit N] [--topic "..."]
```

| 옵션 | 기본 | 동작 |
|---|---|---|
| `--collection` | **(필수)** | Collection.name 으로 paper_collections 조회 → paper.id 목록만 처리. 미지정 시 stderr에 `ERROR: --collection is required` 출력 후 exit 1. |
| `--dry-run` | False | folder_papers 변경 없음 / agent_runs row 없음 / paper.relevance_score 갱신 없음 / 백업 생략 / **CALIBRATION_DIFF md만 작성** |
| `--limit` | None | smoke test (예: `--limit 5`) |
| `--topic` | CF₄ Lewis acid 기본 | 평가 주제 override |

### 3-B. 안전장치

- 비-dry-run 시 자동 백업: `data/backups/papers_pre_recalibrate_<ts>.db` (shutil.copy2).
- 시스템 폴더 (풀분석/자동/검토/휴지통) 매핑만 갱신. 사용자 컬렉션 폴더는 건드리지 않음.
- agent_runs는 새 row insert (덮어쓰기 금지). topic_snapshot에 `PHASE_D_V2_RECALIBRATION[<collection>]` prefix 기록.

### 3-C. 산출물 경로

- `docs/CALIBRATION_DIFF_<collection>_<YYYYmmdd_HHMMSS>.md`

## 4. 사용자 검증 가이드 (스크립트는 자동 실행하지 않음)

**Step 1 — dry-run으로 변화량만 먼저 확인**

```bash
cd backend
../venv/bin/python -m scripts.recalibrate --collection CF4 --dry-run
```

→ `docs/CALIBRATION_DIFF_CF4_<ts>.md` 열어서:
- Δ가 큰 (절댓값 ≥3) 행 우선 검토
- 0층 룰이 걸린 abstract NULL 논문이 5점 이하로 내려갔는지
- molten metal / SF6 / NF3 행이 4점 이하인지
- LaCoO3 / CeO2 / MnOx 등 비-zeolite Cl-VOC 행이 3점 이하인지
- before_folder가 "휴지통"인데 after가 "풀분석 추천"으로 튄 행이 있다면 reason 확인

**Step 2 — 다른 collection도 dry-run 권장**

```bash
../venv/bin/python -m scripts.recalibrate --collection CPN --dry-run
../venv/bin/python -m scripts.recalibrate --collection CPL --dry-run
```

(CPN/CPL collection은 현재 RELEVANCE_SYSTEM의 도메인 밖이므로 결과가 대부분 ≤3점일 것 — 이 결과를 그대로 commit하면 안 된다. CF4 외 collection은 별도 RELEVANCE_SYSTEM이 마련될 때까지 보류.)

**Step 3 — CF4만 commit**

```bash
../venv/bin/python -m scripts.recalibrate --collection CF4
```

→ 자동으로 `data/backups/papers_pre_recalibrate_<ts>.db` 생성됨.
→ 결과 이상 시 백업으로 복구:
```bash
cp data/backups/papers_pre_recalibrate_<ts>.db data/papers.db
```

## 5. 회귀 / 미해결

- **회귀 테스트**: `backend/tests/test_relevance_calibration.py` (PAPER_TRIAGE 50건 통합 테스트)는 v1 분포 가정. v2 룰로 일부 케이스의 기대 점수 범위가 좁아져야 하지만 본 작업 범위 외 — 사용자가 dry-run 결과 검토 후 별도 작업으로 조정 권장.
- **CPN/CPL 등 타 collection 전용 RELEVANCE_SYSTEM**: 미작성. 현 RELEVANCE_SYSTEM은 CF4 전용. 다른 collection은 dry-run으로만 진단해야 함.
- **alerts.py 의 별도 RelevanceScore 평가 경로**: 본 작업 범위 외 (Phase D v1과 동일).

## 6. 금지 사항 (사양 §금지) — 준수 체크리스트

- [x] 실제 DB 변경 금지 — 본 작업에서 스크립트 자동 실행 안 함
- [x] collection 필터 없는 호출 가능 인터페이스 유지 금지 — `--collection` 필수, 미지정 시 exit 1
- [x] 기존 backup 파일 삭제 금지 — 백업 디렉토리 mkdir 만 수행
- [x] 기존 agent_runs row 덮어쓰기 금지 — 항상 새 row insert
- [x] `recalibrate_50.py` 삭제 금지 — deprecation 주석만 추가, 본문 보존
