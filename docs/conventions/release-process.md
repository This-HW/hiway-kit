---
status: current
as_of: 2026-11-21
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
- **The entry opens with what changes for the user** — see [사용자에게 알리기](#사용자에게-알리기) below
- Keep README/docs version-agnostic (link to CHANGELOG) so they can't drift
- **Claude 디렉토리는 `main` 이 아니라 `directory` 브랜치를 추적한다**(5.7.1~, 디렉토리가 command 훅을
  Verified 조직에게만 받는다). 그 브랜치는 CI `directory-branch` 작업이 검증을 통과한 `main` push 마다
  `scripts/build-directory-branch.py` 로 다시 만든다 — 손으로 만들거나 고치지 않는다. 훅 선언 파일의
  이름·위치를 바꾸면 그 스크립트의 `EXCLUDED` 도 같이 고친다(안 고치면 스크립트가 exit 1 로 멈춘다)
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

## 사용자에게 알리기

CHANGELOG 는 정확하지만 밀도가 높다 — 소비자는 자기에게 닿는 변화를 본문 속에서 놓친다.
5.7.1 이 그 사례다: 디렉토리판에서 훅이 통째로 빠졌는데, 그 사실은 `### Changed` 의 두 번째
불릿에 있었다. 그래서 버전 머리를 두 줄로 연다.

1. **사용자 요약 한 줄** — `## [x.y.z]` 바로 아래, 첫 `###` 보다 먼저. *설치한 사람에게 무엇이
   달라지나*를 사용자 언어로 한 문장. 내부 리팩터·게이트·문서만 바뀐 릴리스는
   *"No change in behavior for installed users."* 라고 그렇게 쓴다 — 줄을 빼지 않는다.
2. **`**Action required:**` 표지** — 사용자가 무언가를 **해야** 이전과 같은 결과를 얻는 릴리스에만.
   무엇을, 누가(어느 설치 경로·하네스), 어떤 명령으로 하는지 적는다. 할 일이 없으면 표지를 달지
   않는다 — 매번 붙는 표지는 상시 참인 경고와 같아서 진짜 표지를 죽인다
   (`warning-signal.md` §검토 1).

```markdown
## [5.7.1] — 2026-11-06

Directory installs no longer run the kit's hooks; skills, agents and rule files are unchanged.

**Action required:** if you installed from Anthropic's directory and want rule injection, the
sensitive-path guard, auto-format or stop-time checks, uninstall it and install from this repository
(`/plugin uninstall hiway-kit@anthropic-plugin-directory`, then `/plugin install hiway-kit@hiway-kit`).
```

(위는 형식 예시다 — 5.7.1 의 실제 항목은 이 규약 이전에 쓰였고 고쳐 쓰지 않는다.)

## 발행 직전 체크 — 주장이 실측보다 앞서면 발행하지 않는다

태그·push·디렉토리 제출·사이트 반영 **직전에** 이번 릴리스가 사용자에게 하는 주장을 훑는다:
CHANGELOG 요약 줄, README·`docs/` 에서 바뀐 문장, 그리고 제품 사이트(`thishw/hiway`, 이 레포 밖)가
같은 기능을 어떻게 말하는지.

- **주장마다 근거가 있는가.** 측정(날짜·버전·n), 테스트, 게이트 출력, 코드 경로 중 하나를 댈 수
  있어야 한다. 못 대면 문장을 고치거나 *미측정* 이라고 쓴다 — 발행은 그 뒤다.
- **설치 경로마다 참인가.** 경로 A(디렉토리판, 훅 없음)에서 거짓인 문장을 경로를 밝히지 않고 쓰지
  않는다. 5.7.1 이후 사이트가 디렉토리 설치를 권하면서 *"훅이 python3 로 돈다"* 고 적은 것이 이
  결함이다 — 그 시점에 공개 디렉토리판이 아직 훅 있는 버전이라 참이었고, 갱신이 승인되는 순간
  거짓이 된다. **승인 시점에 거짓이 되는 문장**도 앞선 주장이다.
- **효과 주장인가.** 규칙·훅·스킬이 결과를 *좋게 한다* 는 문장은 정확성 주장과 다르다 —
  [`effect-measurement.md`](effect-measurement.md) 의 절차를 밟은 결과가 없으면 "효과" 를 쓰지 않는다.
- **사이트는 이 레포의 게이트가 보지 않는다.** `check_doc_refs.py` 는 레포 안 문서만 본다. 사이트 문장의
  확인은 이 체크에서 사람이 한다 — 사이트 쪽 게이트가 생기기 전까지 이 한계를 그대로 적어 둔다.
