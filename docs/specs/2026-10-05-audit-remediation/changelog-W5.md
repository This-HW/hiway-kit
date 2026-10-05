---
status: historical
as_of: 2026-10-05
---

### 외부 동향 흡수 — `claude plugin eval` 파일럿 (D15)

- **스킬 발동 eval 신설** (C-C1): `plugins/common/evals/` 에 케이스 5개 — `plan-task-fires`·`debug-fires`·`review-fires`·`brainstorming-fires`·`small-bug-no-skill`(음성). 결정적 그레이더(`tool_used: Skill`, 음성은 `min: 0, max: 0`·`regex`)가 주, `llm` 은 보조. 레포 `evals/`(에이전트 행동·기준선)와 겹치지 않는 공백(스킬 발동률·description 회귀)을 메운다
- **Codex 제출 ZIP 은 `evals/` 를 뺀다**: `scripts/build-codex-zip.py` `EXCLUDED_DIRS` 에 1줄 — 심사 표면·크기 보호
- `evals/README.md` 에 «두 개의 eval» 구분 절(레포 `evals/` vs 플러그인 `evals/`)
