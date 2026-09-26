# W-045 — 실행 모델 기록 + Codex 규범 도달성 (2026-09-27)

## 왜

W-044 운영 중 확인한 사실 `[confirmed 2026-09-27, 세션 로그 실측]`:

- Orca 워커는 `--model opus|sonnet` **별칭**으로만 띄웠다. `launch.effective` 는 요청값을 되울릴 뿐이라
  버전 증거가 아니다. 실제 버전은 세션 로그에만 있었다 — Claude JSONL `message.model`
  (`claude-opus-5-5`, `claude-sonnet-5`), Codex rollout `turn_context.model`/`effort`
  (이 레포에서 돈 Codex 세션 15건: `gpt-6-astra`/medium 등 — 설정이 바뀔 때마다 조용히 변했다).
- `docs/control-loop-transport.md:67` 의 "requested ↔ effective 대조"는 둘 다 별칭이라 **항상 일치**하는
  검사다(`warning-signal.md` 검토 4 — 결함이 있을 때도 발화하지 않는다).
- eval 측정 축(`models`)도 별칭(`opus`/`sonnet`/`haiku`)만 기록한다 — 별칭이 다음 세대로 넘어가도
  `--compare` 는 같은 축으로 본다. 시나리오 실행이 `--output-format text` 라 실제 ID 를 못 받는다.
- 킷의 Codex 타겟은 에이전트를 싣지 않는다 — Codex 에서 frontmatter `model`/`effort` 는 무의미하고
  전부 사용자 Codex 설정 모델로 돈다. 이 사실이 문서에 없다.
- 스킬이 SSOT 로 가리키는 `rules/delegation-contract.md`(8곳)·`rules/child-marker.md`(2곳)는
  `tier: reference` 인데 `indexLine` 이 없어 **어느 하네스에서도 주입도 경로 안내도 없다**.
  AGENTS.md 는 "본문은 킷 레포에서 읽어라"라고 적는다 — 소비자에겐 킷 레포가 없다.
- Codex 는 `hooks-codex.json`(SessionStart `--portable-only` + PostToolUse auto-format)을 실제로
  돌린다(README·`~/.codex/config.toml` trusted_hash 로 확인) — 그런데 AGENTS.md 한계표·`child-session`
  파리티 절·`docs/codex-submission-checklist.md` 는 "Codex 엔 훅 없음"이라 적는다.

## 결정 (컨트롤)

**고정하지 말고 기록한다.** 배포 에이전트 frontmatter 는 별칭 유지(소비자에게 현 세대가 가야 하고,
버전을 박으면 플러그인 안에서 낡는다). 실제로 돈 모델·effort 를 **읽어서 남기는 절차**를 만든다.

## 트랙 (파일 소유권 disjoint)

| 트랙 | 모델 | 브리프 |
| --- | --- | --- |
| M1 provenance-docs | opus | `brief-M1-provenance-docs.md` |
| M2 eval-model-axis | opus | `brief-M2-eval-model-axis.md` |
| C codex-parity | opus | `brief-C-codex-parity.md` |

**컨트롤 소유(워커 편집 금지)**: `AGENTS.md`·`GEMINI.md`(병합 후 `export-harness.sh`), 플러그인 버전·
`CHANGELOG.md`·타겟 매니페스트, eval 기준선, `docs/works/**`, `docs/specs/**`.
