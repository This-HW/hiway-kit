---
title: "Hermes 판 — H0 문서·비활성 타겟, 판 빌더, H1 격리 실측"
status: current
execution_status: in-progress
as_of: 2026-11-24
created: 2026-11-24
size: large
---

## 요구사항

설계 SSOT: `docs/specs/2026-11-24-hermes-edition/design-verdict.md`(3자 토론 판정)와
`docs/specs/2026-11-24-hermes-edition/research-integrated.md`.

- **범위**: H0 + 빌더 + H1 실측. H2(게시·`enabled:true`·README 지원 표기)는 실측 보고 뒤 다시 묻는다
  `[confirmed: 사용자 "H0+빌더+H1 실측 (추천)", 2026-11-24]`
- **배포 단위**: 생성 브랜치 `hermes` 의 Agent Plugins v1 축소판을 커밋 sha 고정으로 설치한다 `[confirmed: 판정 D1]`
  - `--ref` 는 40자 sha 만 받는다 `[researched: hermes_cli/plugins_cmd_git.py:104-108 @352b249, 2]`
- **`plugins/common` 은 이번 작업에서 한 바이트도 바꾸지 않는다** `[confirmed: 판정 D3 H0]`
  - 바꾸면 `directory` 에 새 커밋이 생겨, 사람 심사 중인 v5.9.1 이 대체된다
  - 그래서 플러그인 버전 올림도 CHANGELOG 릴리스 항목도 이번에는 없다. 스크립트·문서 변경은 다음 릴리스의 CHANGELOG 에 묶는다
- **Hermes 판 내용** `[confirmed: 판정 D2]`
  - 싣는 것: 스킬 15종(`harness-export`·`skill-forge` 제외), `agents/`·`rules/`·`tools/`·`.claude-plugin/plugin.json`
  - 빼는 것: `hooks/`·`setup/`
  - 판 변환:
    - 루트 `plugin.json` 을 AP v1 매니페스트로 바꾼다(`build_manifest` 가 생성)
    - `using-hiway-kit` description 꼬리를 교체한다(정확 일치일 때만, 아니면 exit 1)
    - 에이전트·뺀 경로 참조 문서에 Hermes 머리말을 단다
    - 수정 에이전트 4종과 호출부의 "격리 확보" 서술을 고친다
    - 판 README 를 다시 쓴다
- **H1 실측 원칙** `[confirmed: 헌장 기준 7, 메모리 sandbox-agent-fs-isolation]`
  - 쓰기를 거부한 샌드박스에서만 한다. `install.sh | bash` 는 쓰지 않는다
  - Hermes 고정 sha 소스(`352b249`, stable `caafe53`)를 임시 venv 에 설치한다. Python 3.11+ 가 필요하다 — `/opt/homebrew/bin/python3.11` 이 있다 `[researched: which, 1]`
- **H1 결정 변수**: P0·P1·P2·P3·P4·P5′·P6 + 내장 기능 공존(판정 D3 H1 절). 측정 기록에는 측정한 **트리 sha** 를 남긴다.

## 결정

- **사용자 결정**: 진행 범위는 "H0+빌더+H1 실측 (추천)" 이다(2026-11-24 응답 원문). H2 는 실측 보고 뒤에 다시 묻는다.
- **판 매니페스트 경로**: `targets.json` 에 `delivery: "edition"` 키를 두고, 경로는 빌더 상수로 둔다.
  - 두 리뷰어의 작은 불합의를 판정문에서 controller 가 이렇게 정했다
  - 경로 충돌 검사는 정규화한 경로로 한다
- **P5′(sha 설치 → `--force --ref` 이동) 실측 방법** `[unresolved]` — 기본값은 아래 순서다:
  - 레포 밖 임시 bare 저장소를 `file://` URL 로 쓴다(Hermes 가 받으면)
  - 받지 않으면 P5′ 를 H2 게시 직전 단계로 미루고, 그 사실을 기록한다
  - 공개 `hermes` 브랜치 push 는 H2(사용자 재승인) 몫이다
- **모호함 탐색** — 네 자리를 다 훑었다:
  - **상태 전이**: `enabled:false→true` 일 때 `--write` 만 enabled 를 요구한다(판정 쟁점 4-4). `hermes` 브랜치가 처음 생길 때는 부모 없이 커밋한다. 디렉토리 빌더 관례를 따른다
  - **두 규칙 동시 적용**: build-targets 원칙 "enabled = main 에 생성" 과 `delivery: edition` 이 겹친다. edition 은 main 에 파일을 만들지 않고 계산 검사만 한다(판정 쟁점 4-1·2)
  - **경계값 포함 여부**: description 교체는 정확 일치일 때만 한다. 트리 sha 는 완전 일치로 비교한다
  - **실패 후 롤백**: 판 빌더는 임시 인덱스와 ref 갱신 한 번으로 원자적이다(디렉토리 빌더 배관 재사용). Hermes 게시 실패가 directory 게시를 막지 않는다
  - 결과: **P0 없음**

## 구현 계획

유형: **리팩터(1단계) → 신규 기능(2~5단계)**. 리팩터는 기존 테스트가 green 인지 먼저 확인하고 golden 테스트로 고정한 뒤 옮긴다.

**배치 1 — 병렬(파일이 겹치지 않음)**

1. **W-B 디렉토리 빌더 배관 공통화**(리팩터, Codex 워커)
   - 바꿀 파일: `scripts/tests/test_build_directory_branch.py`, `scripts/edition_tree.py`(신규), `scripts/build-directory-branch.py` <!-- doc-ref-ok: 이 계획이 만들 파일 -->
   - 1a. 추출 **전** 커밋: golden 테스트를 넣는다
     - 픽스처 레포의 결과 트리 sha 를 고정한다
     - 실레포 오라클 `derive_tree(ab468bf):plugins/common == 364f51e6d4ef8ba952ae91301a935a3d5e70689c` 를 고정한다
     - 되돌려-FAIL 로 이 테스트가 실제로 잡는지 확인한다
   - 1b. 정책과 무관한 배관만 원문 그대로 `scripts/edition_tree.py` 로 옮긴다 <!-- doc-ref-ok: 이 계획이 만들 파일 -->
     - 대상: `_git`·`_git_bytes`·`_rev`·`_entries`·`_frontmatter_span`·`_strip_keys`·`_with_note`·커밋 체인
     - `derive_tree`·`_transform`·`_assert_*`·상수·머리말 문구는 디렉토리 빌더에 남긴다
   - 1c. `--check` 출력에 플러그인 하위 트리 sha 를 덧붙인다
2. **W-A 타겟 정책 + build-targets**(신규 기능, Claude 워커)
   - 바꿀 파일: `packaging/targets.json`, `scripts/build-targets.py`, `scripts/tests/test_build_targets.py`
   - `hermes` 타겟을 추가한다: `enabled:false`, `delivery:"edition"`, `verificationLevel:"researched-only"`, AP v1 `schemaUrl`·필드 정책, `_disabledReason`, 미확인 목록
   - `delivery:"edition"` 이면 main 에 파일을 만들지 않고 `build_manifest` 계산 + AP v1 정적 판정만 한다
     - 판정 항목: `$schema` 일치, 허용 최상위 필드, `name` 정규식, `author` 문자열 필드
   - `manifestPath`·출력 경로 충돌은 정규화한 경로로 exit 1 한다
   - edition 타겟에 `--only` 를 주면 판 빌더로 안내하는 오류를 낸다
   - `artifacts_for` 의 `manifestPath` 무조건 인덱싱(KeyError)을 막는다
   - fail-closed 불변식의 정적 대리 검사를 둔다: `plugins/common/plugin.json` 의 `$schema` ≠ AP URL, 그리고 `plugins/common/plugin.yaml` 없음 <!-- doc-ref-ok: 없어야 한다는 불변식의 대상 경로 -->
3. **W-D H0 문서**(controller 직접)
   - 바꿀 파일: `docs/harnesses.md`
   - Hermes 절을 쓴다: 지원 상태(researched-only), `AGENTS.md` 경로와 가림, 컨텍스트 기본 20,000자, `skills.external_dirs` 평가 경로(읽기 전용 클론·manual-only 노출), 이중 로드 경고, "지원 표기는 실측 뒤"

**배치 2 — 1·2 병합 뒤**

4. **W-C Hermes 판 빌더**(신규 기능, 워커 1)
   - 바꿀 파일: `scripts/build-hermes-branch.py`(신규), `scripts/tests/test_build_hermes_branch.py`(신규) <!-- doc-ref-ok: 이 계획이 만들 파일 -->
   - `edition_tree` 배관과 `build-targets.build_manifest` 를 쓴다(매핑을 두 벌 두지 않는다)
   - 판 변환과 fail-closed 판정:
     - 결과 트리에 `hooks/`·`setup/`·빼기로 한 스킬 2종이 없어야 한다
     - AP v1 매니페스트, 스킬 frontmatter 의 AP 제약을 지킨다
     - 패키지 루트 밖을 가리키는 심링크가 없어야 한다
     - 머리말이 필요한 문서에 머리말이 있어야 한다
     - description 교체가 정확 일치로 이뤄져야 한다
   - 출력 동작:
     - `--check` 는 `enabled` 와 무관하게 돌고 트리 sha 를 출력한다
     - `--write` 는 `enabled:true` 를 요구한다(이번 범위에서는 쓰지 않는다)
     - `--out <dir>` 은 로컬에 내보낸다(H1 설치 입력)
   - 실레포 `--check` 를 pytest 에 넣는다(병합 전에 돈다)
   - CI 게시 job 은 H2 에서 추가한다(이번 범위 밖)

**배치 3 — 4 병합 뒤**

5. **W-E H1 격리 실측**(워커 1, 결과는 controller 가 대조)
   - 바꿀 파일: `docs/specs/2026-11-24-hermes-edition/h1-measurement.md`(신규), `scripts/hermes-sandbox.sb`(신규 — `sandbox-exec` 프로필, 레포 밖 쓰기 금지 경로 목록) <!-- doc-ref-ok: 이 계획이 만들 파일 -->
   - 할 일: 고정 sha Hermes 를 임시 venv 에 설치한다. `build-hermes-branch.py --out` 의 트리로 P0~P6·공존을 측정하고, 원 출력과 트리 sha 를 기록한다
   - 사용자 홈·레포·`~/.claude` 에 쓰지 않는다. 측정 전후에 홈 디렉토리 변경 목록을 대조한다

## 완료 조건

- `python3 -m pytest scripts/tests/test_build_directory_branch.py scripts/tests/test_build_targets.py scripts/tests/test_build_hermes_branch.py -q` (exit 0)
- `python3 -m pytest scripts/tests -q -k "oracle or golden"` (exit 0, 1건 이상 수집)
  - 디렉토리판 오라클 `364f51e6d4ef8ba952ae91301a935a3d5e70689c` 를 재현해야 한다
- `python3 scripts/build-targets.py --check` (exit 0)
- `python3 scripts/build-directory-branch.py --check --source HEAD` (exit 0)
- `python3 scripts/build-hermes-branch.py --check --source HEAD` (exit 0)
- `git diff --quiet ab468bf3ff576ac349f1af1de6d21009626d3faa HEAD -- plugins/common` (exit 0 — 플러그인 폴더 무변경)
- `grep -q "tree_sha:" docs/specs/2026-11-24-hermes-edition/h1-measurement.md && grep -q "P6:" docs/specs/2026-11-24-hermes-edition/h1-measurement.md` (exit 0)
- `ruff check scripts/` (exit 0)
- 게이트 약화 0 (`BASE=` in-progress 전환 시 커밋):
  - `git diff --name-only --diff-filter=D "$BASE" -- scripts/tests tests` 빈 출력
  - `scripts/tests`·`tests` 에 skip·xfail 추가 0
  - 이 절의 변경 0
