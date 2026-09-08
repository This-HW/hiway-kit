This repo's completion gate has **three** checks that ask "does the generated artifact match its
source of truth?" — `AGENTS.md` marker block vs `rules/` (sha256), eval scenarios vs baseline (set
comparison + tier coverage), and target manifests vs the plugin SSOT (existence + content diff).
They look like the same question, but **the input, the pass/fail criteria, and the failure message
are all different for each.**

**They are not merged into one shared abstraction.** A common primitive would have to bend to fit
all three cases — more branching parameters, harder-to-read gate code. A gate only works if
whoever reads a failure trusts it enough to act; a gate nobody can follow gets ignored when it goes
red.

Duplication here is reduced through **convention, not code** — e.g. the path-containment pattern
above, followed the same way in every place a config value becomes a file path, is exactly that.
A fourth "does the generated thing match its source" gate is the point to reconsider this — not
before. Rule-of-three isn't "merge at the third instance," it's "the third instance is still not
necessarily a pattern."

## 새 드리프트 게이트가 필요한지 판별하는 법 (2026-09-07, 27-3)

> **생성물이 사본이면 게이트가 필요하고, 참조면 필요 없다.**

`CLAUDE.md` 가 규약 절들을 `@docs/conventions/*.md` **import** 로 바꿨을 때 게이트를 신설하지
않았다 — import 는 참조이지 사본이 아니므로 **드리프트할 대상이 없다**. 반대로 `AGENTS.md`(§11)·
타겟 매니페스트(§14)·이름 파생(§18)은 전부 **사본을 만든다**. 그래서 각각 게이트가 있다.

그리고 게이트가 넷이 돼도 **통합하지 않는다**. 판정 방식이 넷 다 다르고(sha256 대조 · 집합
양방향 대조 · 파일 존재+내용 대조 · 문자열 파생 대조), 통합으로 줄어드는 것은 이미 공유 중인
`hdr`/`green`/`red` 껍데기뿐이다. rule of three 는 세 번째에 묶으라는 뜻이 아니다.
