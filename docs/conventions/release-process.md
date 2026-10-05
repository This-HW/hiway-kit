---
status: current
as_of: 2026-10-05
---

# 릴리스 절차 (정본)

`CLAUDE.md` 의 Release Checklist 는 이 문서를 가리키는 포인터다 — 절차는 여기에만 적는다.

**Every commit that changes plugin behavior MUST bump the version** in
`plugins/common/.claude-plugin/plugin.json` — that manifest is the single source of truth
every target manifest (Codex, Antigravity, ...) is generated from. The plugin cache is keyed by
version (`<marketplace>/hiway-kit/<version>[-<sha>]`): on the direct marketplace a same-version
push is never fetched, so users never get the fix.

- Patch bump (x.y.Z) for bug fixes and hook changes; minor bump (x.Y.0) for new agents, skills, or features
- Add a matching `## [x.y.z]` entry to `CHANGELOG.md` (the completion gate fails if the SSOT
  version and the CHANGELOG top entry diverge)
- Keep README/docs version-agnostic (link to CHANGELOG) so they can't drift
- **버전은 `scripts/bump-version.sh <version>` 로 올린다** (수동으로 SSOT를 직접 고치지 마라).
  SSOT 갱신 → 타겟 매니페스트 재생성 → 자기 검증을 한 명령으로 묶어, "SSOT만 올리고 생성물
  재생성을 잊는" 실수(v2.15.0에서 실제로 밟았다)를 예방한다. (낡은 버전 문자열 감사 도구도
  만들어 실물 레포에 돌려봤지만 뺐다 — 버전이 실리는 자리가 전부 생성물이거나 기존 게이트로
  이미 막혀 있어 지킬 게 없었다. `docs/conventions/reference-vs-judgment.md` 참고)
- **규범(`plugins/common/rules/*.md`)이나 인라인되는 규약(`export_harness.py` 의
  `CONVENTIONS_INLINE`)을 바꿨으면 진입점을 재생성한다**: `./scripts/export-harness.sh`
  (`--check` 가 드리프트를 잡는다). `plugins/common/rules/VERSION` 은 마커 줄의 표기
  버전이고 내용 변경은 마커 sha 가 추적한다 — 3.8.0 이후 올린 적이 없고, 올리는 기준은 아직 정하지 않았다.
- **Rules `.md` 를 바꿨으면 CHANGELOG 항목에 새 블록 sha256 을 적는다.**
  값은 재생성된 `AGENTS.md` 의 **마커에서 읽는다**:
  `grep -o 'kit:begin rules-v[0-9.]* sha256:[0-9a-f]*' AGENTS.md`

  > **`--stdout | shasum` 을 쓰지 마라 — 다른 값이 나온다.** 마커의 sha 는 렌더된 블록이
  > 아니라 **입력**(`rules-v` · 블록 헤더 · PREAMBLE · 룰별 이름+본문)을 덮는다. 실측:
  > 같은 시점에 `--stdout` 해시는 `3124d09d…`, 마커는 `49ae0be1…` 였다. 소비자가 대조하는
  > 것은 **마커** 이므로 마커 값을 적어야 한다.

  **왜.** 진입점 블록을 자기 레포에 **정본으로 들여간 소비자**는 상류가 바뀐 것을 알
  방법이 없다. 그쪽 드리프트 가드는 *자기 정본 ↔ 자기 라이브* 만 보고, 이 킷의 §11 은
  *이 레포* 만 본다 — 설계상 그렇게 뒀다(소비자가 킷의 플러그인 캐시 경로에 의존하는
  가드는 하네스 종속이 되고 조용히 사라진다). 그 대가로 **상류 변경 신호가 없다.**
  CHANGELOG 에 sha 를 적으면 소비자가 자기 마커와 대조해 **한 줄로** 판정할 수 있다.
  실측: 소비 프로젝트가 v3.16.0 export 를 채택했고, v3.18.0 시점에 바이트가 여전히
  같은지는 **내가 손으로 대조해서야** 알았다(2026-09-09).

- Rules `.md` 변경 시 CHECKSUMS 재생성: `(cd plugins/common/rules && shasum -a 256 *.md | grep -v CHECKSUMS > CHECKSUMS.sha256)` — 이 매니페스트는 보안 경계가 아니라 우발적 드리프트 감지기다
- 그 룰에 해설본 미러가 있으면 해설본도 함께 손보고 `scripts/sync-rule-mirror.sh --regenerate`
- **행동 eval**: 에이전트·스킬 정의를 바꾼 릴리스는 전체 행동 eval(`scripts/run-evals.sh`, 인자 없이)을
  돌려 후퇴가 없는지 본다. API 비용이 들어 per-commit 게이트(`verify-done.sh`)에는 오프라인
  스키마 검증만 들어 있다 — 상세·기준선 갱신 절차는 `evals/README.md` "릴리스 체크리스트 연동"
- Tag **the commit you push as the release**: `git tag -a vX.Y.Z <commit> -m "vX.Y.Z"`, then
  `git push --tags`. Later commits that leave the version untouched (docs, repo tooling) are
  not a new release and do not move the tag. `verify-done.sh` §6 fails when any past CHANGELOG
  release lacks a tag — the practice lapsed silently once (20 untagged releases between 2.10.4
  and 2.12.3), so it is a machine check now. Caveats on existing tags: the 2026-08-17 backfill
  could not recover which commit was actually pushed as each old release, so it used the last
  commit carrying that version; tags predating v2.11.0 were placed ad hoc. Every tag does point
  at a commit whose `plugin.json` matches it.
- Run `scripts/verify-done.sh` (green) before claiming a release ready (definition-of-done)
- 배포 채널(직접 마켓플레이스·Claude 디렉토리·OpenAI 디렉토리)별 전파와 상태는
  `docs/marketplace-submission.md` 상단 요약표가 소유한다
