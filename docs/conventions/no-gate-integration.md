---
status: current
as_of: 2026-10-05
---

This repo's completion gate has **several** checks that ask "does the generated artifact or copy
match its source of truth?" — e.g. the `AGENTS.md` marker block vs `rules/` (sha256), eval
scenarios vs baseline (set comparison + tier coverage), target manifests vs the plugin SSOT
(regenerate + content diff). **Which checks those are is owned by `scripts/verify-done.sh`** — this
document does not count or list them. They look like the same question, but **the input, the
pass/fail criteria, and the failure message are different for each.**

**They are not merged into one shared abstraction.** A common primitive would have to bend to fit
every case — more branching parameters, harder-to-read gate code. A gate only works if whoever
reads a failure trusts it enough to act; a gate nobody can follow gets ignored when it goes red.

Duplication here is reduced through **convention, not code** — e.g. the path-containment pattern,
followed the same way in every place a config value becomes a file path, is exactly that.
Rule-of-three isn't "merge at the third instance," it's "the third instance is still not
necessarily a pattern."

## 새 드리프트 게이트가 필요한지 판별하는 법 (2026-09-07)

> **생성물이 사본이면 게이트가 필요하고, 참조면 필요 없다.**

`CLAUDE.md` 가 규약 절들을 `@docs/conventions/*.md` **import** 로 바꿨을 때 게이트를 신설하지
않았다 — import 는 참조이지 사본이 아니므로 **드리프트할 대상이 없다**. 반대로 `AGENTS.md`·
타겟 매니페스트·이름 파생은 전부 **사본을 만든다**. 그래서 각각 게이트가 있다.

## 재검토 기록 (2026-09-10)

원래 약속은 "네 번째가 필요해지면 재검토한다"였다. 그 시점은 조용히 지났고, 게이트가
일곱째까지 늘어난 뒤에야 다시 읽었다. 통합 판정은 **유지** 한다 — 판정 방식이 제각각이고,
통합으로 줄어드는 것은 이미 공유 중인 `hdr`/`green`/`red` 껍데기뿐이다.

바뀐 것은 서술 방식이다. 이 판정을 적은 문단들이 게이트를 **열거** 하고 있었고, 게이트가
늘 때마다 아무도 고치지 않아 낡았다(`rules/definition-of-done.md` 의 *"기계 검사 목록은
게이트가 소유한다 — 열거하면 낡는다"*, `warning-signal.md` §5 *"대상을 나열하지 말고 제외를
나열한다"* 를 자기 문서가 어긴 것이다). 그래서 목록과 개수를 지웠다. 남기는 것은 **판정과
그 근거** 뿐이고, 그 둘은 게이트가 몇 개든 변하지 않는다.
