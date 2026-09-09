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
- Tag **the commit you push as the release**: `git tag -a vX.Y.Z <commit> -m "vX.Y.Z"`, then
  `git push --tags`. Later commits that leave the version untouched (docs, repo tooling) are
  not a new release and do not move the tag
- Run this project's completion gate (green) before claiming a release ready
