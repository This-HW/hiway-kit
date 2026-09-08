**Every commit that changes plugin behavior MUST bump the version** in
`plugins/common/.claude-plugin/plugin.json` — that manifest is the single source of truth
every target manifest (Codex, Antigravity, ...) is generated from.

- Patch bump (2.x.y) for bug fixes and hook changes
- Minor bump (2.x.0) for new agents, skills, or features
- Add a matching `## [x.y.z]` entry to `CHANGELOG.md` (the completion gate fails if the SSOT
  version and the CHANGELOG top entry diverge)
- Keep README/docs version-agnostic (link to CHANGELOG) so they can't drift
- **버전은 `scripts/bump-version.sh <version>` 로 올린다** (수동으로 SSOT를 직접 고치지 마라).
  SSOT 갱신 → 타겟 매니페스트 재생성 → 자기 검증을 한 명령으로 묶어, "SSOT만 올리고 생성물
  재생성을 잊는" 실수(v2.15.0에서 실제로 밟았다)를 예방한다. (낡은 버전 문자열 감사 도구도
  만들어 실물 레포에 돌려봤지만 뺐다 — 버전이 실리는 자리가 전부 생성물이거나 기존 게이트로
  이미 막혀 있어 지킬 게 없었다. `docs/conventions/reference-vs-judgment.md` 참고)
- Rules `.md` 변경 시 CHECKSUMS 재생성: `(cd plugins/common/rules && shasum -a 256 *.md | grep -v CHECKSUMS > CHECKSUMS.sha256)` — 이 매니페스트는 보안 경계가 아니라 우발적 드리프트 감지기다
- 그 룰에 해설본 미러가 있으면 해설본도 함께 손보고 `scripts/sync-rule-mirror.sh --regenerate`
- Tag **the commit you push as the release**: `git tag -a vX.Y.Z <commit> -m "vX.Y.Z"`, then
  `git push --tags`. Later commits that leave the version untouched (docs, repo tooling) are
  not a new release and do not move the tag
- Run this project's completion gate (green) before claiming a release ready
