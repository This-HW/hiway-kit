---
title: "Hermes 판을 main 으로 통합 — hermes 브랜치 폐지(준비는 지금, 적용은 디렉토리 심사 뒤)"
status: current
execution_status: in-progress
as_of: 2026-11-25
created: 2026-11-25
size: medium
---

## 요구사항

- **사용자 결정**(2026-11-25, 원문): "준비는 지금, 적용은 심사 뒤 (추천)"
  - 근거는 업계 조사 두 건이다(아래)
  - 이번 계획은 **준비**까지 한다:
    - 전환 커밋을 별도 브랜치 `This-HW/hermes-unify` 에 만든다
    - 핵심 가정을 샌드박스에서 실측한다
  - **main 적용**은 Claude 디렉토리 v5.9.1 심사가 끝나거나 Verified 가 승인된 뒤에 한다
  - 적용 전까지 `plugins/common` 은 바꾸지 않는다. 바꾸면 심사 중인 v5.9.1 이 대체된다
- **업계 근거**:
  - Hermes 공식 카탈로그 2,632건 중 96.3% 가 기본 브랜치에서 배포한다. 배포용 브랜치를 쓰는 곳은 약 1%(eachlabs `dist/hermes`, Kinprove 등)다. 별 수 상위 40개는 전부 기본 브랜치다 `[researched: hermes-agent plugin-catalog @4c84e786 전수, 2026-11-25]`
  - 유명 멀티 하네스 저장소 13곳(superpowers·ECC·addyosmani·figma·context7 등) 중 하네스별 배포 브랜치는 0곳이다. obsidian-skills·NVIDIA/skills 는 한 폴더에 AP v1 `plugin.json` + `.claude-plugin/` 등 + `skills/` 를 함께 둔다 `[researched: gh api, 2026-11-25]`
  - 루트 `plugin.json` 충돌은 Antigravity 공식 규칙으로 푼다: `.antigravity-plugin/plugin.json` 이 루트보다 우선한다 `[researched: antigravity.google/docs/build-plugins, 미실측 → U-0]`
- **목표 구조**:
  - `plugins/common/plugin.json` = Agent Plugins v1(Hermes 가 읽는다)
  - `plugins/common/.antigravity-plugin/plugin.json` = Antigravity 매니페스트
  - Hermes 사용자는 `hermes plugins install This-HW/hiway-kit/plugins/common` 으로 main 을 설치하고 `update` 로 갱신을 받는다
  - `hermes` 브랜치·`build-hermes-branch.py`·CI `hermes-branch` 는 폐지한다
- **감수하는 것**:
  - Hermes 사용자는 전체 트리를 받는다(훅은 Hermes 가 무시한다)
  - Hermes 는 수동 전용 표시를 해석하지 않는다 → `harness-export` 를 모델이 부를 수 있다 → 아래 결정의 안전장치로 막는다

## 결정

- **`harness-export` 쓰기 안전장치**:
  - 현재 등록부상 동의는 "호출 자체"다(`docs/conventions/consumer-footprint.md`). Hermes 에서는 모델이 자동 호출할 수 있다
  - 그래서 SKILL.md 에 하네스 중립 규칙을 넣는다: "이번 대화에서 사용자가 명시적으로 내보내기를 요청하지 않았으면 쓰지 않는다. `--stdout`/`--check` 로 보여 주고 먼저 묻는다"
  - consumer-footprint 규칙 1(자동 트리거는 트리를 바꾸지 않는다)과 맞는다
- **fail-closed 불변식("main 은 Hermes 가 거부") 폐기**:
  - 목표 구조에서는 main 이 곧 Hermes 패키지다
  - 대체 판정은 "`plugins/common/plugin.json` 이 AP v1 판정 통과 + `plugin.yaml` 없음"이다
- **버전**: 적용 시점에 올린다(플러그인 내용 변경). 준비 브랜치에서는 올리지 않는다

## 구현 계획

유형: 동작 변경(배포 구조). 정책·생성기 테스트를 새 스펙으로 먼저 고친다.

1. **U-0 Antigravity 우선순위 실측**(Codex 워커, 지금 병렬)
   - 바꿀 파일: 레포 밖 산출물만 쓴다. 결과는 `docs/specs/2026-11-25-hermes-unify/u0-antigravity.md`
   - 최소 플러그인으로 `agy` 1.5.15 를 쓰기 거부 샌드박스에서 비교한다:
     - (a) 루트 AP v1 + `.antigravity-plugin/plugin.json`
     - (b) 루트 AP v1 만
     - (c) 루트 Antigravity 형식만(현재 구조, 대조군)
   - 비교 항목: validate/install/list/uninstall 결과, 인식된 name·version·스킬
2. **U-A 전환 커밋 준비**(Claude 워커, 지금 병렬, 브랜치 `This-HW/hermes-unify`)
   - 바꿀 파일:
     - `packaging/targets.json`(antigravity `manifestPath` 이동, hermes 를 main 배포 타겟으로)
     - `scripts/build-targets.py` 와 테스트(불변식 교체)
     - `scripts/build-codex-zip.py`(`.antigravity-plugin/` 제외)
     - `plugins/common/plugin.json`·`plugins/common/.antigravity-plugin/plugin.json`(생성물)
     - `plugins/common/skills/harness-export/SKILL.md`(쓰기 안전장치)
     - `docs/conventions/consumer-footprint.md`
     - `scripts/build-hermes-branch.py`·`scripts/tests/test_build_hermes_branch.py` 삭제
     - `.github/workflows/validate.yml`(`hermes-branch` job 삭제)
     - `docs/harnesses.md`·`README.md`·`packaging/README.md`
     - `scripts/edition_tree.py` 는 디렉토리 빌더가 계속 쓴다
3. **U-B 준비 트리 실측**(U-0·U-A 뒤): 쓰기 거부 샌드박스에서 확인한다
   - Hermes 에 `This-HW/hiway-kit/plugins/common`(준비 브랜치의 file:// 미러)을 설치해 보안 판정·스킬 17·enable/remove·AGENTS.md 를 본다
   - `harness-export` 자동 호출 경로는 SKILL.md 지시 확인으로 갈음한다(모델 실행 없음)
   - `agy` 로 준비 트리를 실측한다
4. **적용**(심사 종료 또는 Verified 승인 뒤, 사용자에게 알리고 진행):
   - 준비 브랜치를 rebase 하고 버전을 올린다
   - 게이트를 돌리고 main 에 push 한다
   - Hermes 로 main 설치를 재실측한다
   - `hermes` 브랜치를 삭제한다

## 완료 조건 (준비 범위)

- `python3 -m pytest scripts/tests -q` (준비 브랜치, exit 0)
- `python3 scripts/build-targets.py --check` (준비 브랜치, exit 0)
- `python3 scripts/build-codex-zip.py --check` (준비 브랜치, exit 0)
- `test -f docs/specs/2026-11-25-hermes-unify/u0-antigravity.md && grep -q "결론:" docs/specs/2026-11-25-hermes-unify/u0-antigravity.md` (exit 0)
- `git diff --quiet origin/main -- plugins/common` (이 계획 동안 main 의 plugins/common 무변경, exit 0)
- 게이트 약화 0(BASE = 이 계획 커밋): 삭제 테스트는 폐지 대상(`test_build_hermes_branch.py`)뿐이고 `## 결정` 에 근거가 있다. skip 추가 0
