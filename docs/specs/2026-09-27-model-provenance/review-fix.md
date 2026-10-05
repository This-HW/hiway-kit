---
status: historical
as_of: 2026-09-27
---

# W-045 리뷰 반영 — 공통 전제와 트랙 (2026-09-27)

`/hiway-kit:review`(3.39.1 후보, 51b3f25..50a1274) 결과: 코드 배치 [CONDITIONAL] H1·M3·L5, 규범 배치 [CONDITIONAL]
H1·M5·L5, 보안 스캔 C/H/M 0. 리뷰 원문 요지는 각 브리프에 ATK 번호로 인용한다(C-=코드 배치, N-=규범 배치).

## 가장 큰 발견 — 스킬 frontmatter `effort` 가 세션 effort 를 덮어쓴다 `[confirmed]`

- 관측: W-045 워커 3명(및 이전 워커 14명) 모두 `--effort high` 로 떴는데 `child-session` 스킬 로드 직후부터 세션 끝까지
  `effort: medium` (child-session frontmatter 값). 전환 시점에 `command_permissions` 첨부가 `model: claude-sonnet-5` 를 싣는다.
- **양성 대조(2026-09-27, 컨트롤 실행)**: 같은 프롬프트·`--model opus --effort high` 로 (A) 스킬 없이 → 3턴 모두 high,
  (B) `hiway-kit:child-session` 로드 → 로드 턴 high, 이후 전부 **medium**. 모델은 두 쪽 모두 `claude-opus-5-5` 유지
  (frontmatter `model` 은 메인 스레드에 적용되지 않음). 재현 디렉토리 `/private/tmp/effprobe-1790451869/{a,b}`.
- 함의: 킷 스킬 19종 중 17종이 `effort:` 를 선언한다 — `/test`(medium)는 세션을 조용히 낮추고 `/plan-task`(max)는 세션
  끝까지 max 로 올린다. "모델·effort 는 사용자/호스트 설정의 몫"(control-loop) 원칙과 정면 충돌.
- **결정(컨트롤)**: 모든 스킬 frontmatter 에서 `model`·`effort` 를 제거하고 게이트로 고정한다. 에이전트 frontmatter 는
  유지(별도 컨텍스트에서 돈다 — eval 이 그 깊이를 측정한다).

## 워커 공통 지시

- **`child-session` 을 Skill 로 로드하지 마라** — 로드하면 위 결함으로 effort 가 medium 으로 떨어진다. 대신
  워크트리의 `plugins/common/skills/child-session/SKILL.md` 를 Read 로 읽고 그 규율을 따른다(마커 기록 포함).
- 기준 커밋: 디스패치 spec 의 해시. 착수 시 대조.

## 트랙 (파일 소유권 disjoint)

| 트랙 | 모델 | 소유 |
| --- | --- | --- |
| R1 evals | opus | `evals/run.py`, `evals/tests/test_runner.py` |
| R2 skills-rules-hooks | opus | `plugins/common/skills/**`, `plugins/common/rules/**`(+CHECKSUMS·미러), `plugins/common/hooks/**`, `scripts/check_skill_frontmatter.py`(신설), `scripts/verify-done.sh`, `.github/workflows/validate.yml`, `docs/architecture/rules/**` |
| R3 docs | opus | `docs/control-loop-transport.md`, `README.md`, `docs/codex-submission-checklist.md` |

컨트롤 소유: `CHANGELOG.md`(3.39.1 서술 정정 포함), `AGENTS.md`/`GEMINI.md` 재생성, 버전, 기준선, `CLAUDE.md`, `docs/specs/**`.
보류(후속 기록): C-ATK-007 Codex 에서 AGENTS.md 와 훅 주입의 이중 도달·버전 불일치.
