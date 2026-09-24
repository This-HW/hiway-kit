# Decisions: prompt-audit 적용 — 정의 파일 cruft 제거

> Work ID: W-044
> Last Updated: 2026-09-25

## 의사결정 기록

### D-1 Work ID 를 W-025 → W-044 로 재발급 (2026-09-25)

`work.sh new` 가 W-025 를 발급했으나 `git grep` 결과 W-025(v2.18.0 배치)·W-026·W-027·
W-032·W-036·W-040·W-042·W-043 이 이미 스펙·CHANGELOG-archive 에서 쓰인 ID 였다
(`docs/works/` 디렉토리로만 세는 발급기의 결함 — `warning-signal.md` 검토 절차 3:
"이미 있으면 실제 충돌이므로 멈춘다"). 최대 사용 ID 다음인 W-044 로 재발급(`git grep W-044` 0건).
**후속**: `scripts/work.sh` 의 ID 발급이 트래킹된 전체 텍스트를 대조하도록 고치는 것은
별도 항목 — 이 Work 범위 밖.

### D-2 트랙 분할은 파일 소유권 기준, 공유 생성물은 컨트롤이 병합 후 재생성

`AGENTS.md`/`GEMINI.md` 는 룰(T1)과 using-hiway-kit(T3) 양쪽의 export 본이라 어느 한
트랙에 줄 수 없다 → 컨트롤이 병합 후 `export-harness.sh` 로 한 번 재생성. 워커의
`verify-done.sh` 에서 §11 red 는 **예상된 것**이고 보고 대상이지 수정 대상이 아니다.

### D-3 eval 회귀 측정은 컨트롤이 병합 후 1회

`run-evals.sh`(인자 없음)는 API 비용이 든다. 워커는 `--validate`/`--dry-run` 만 돌리고,
행동 회귀는 통합 브랜치에서 컨트롤이 `--compare evals/baseline/2026-09-20.json` 로 잰다.
