---
title: "Archify 로 레포 아키텍처·흐름 도식 업그레이드 (프로젝트 전용 설치)"
status: current
execution_status: in-progress
as_of: 2026-11-25
created: 2026-11-25
size: medium
---

## 요구사항

- **사용자 요청**(2026-11-25, 원문): "Archify 우리 프로젝트에만 적용해서 모든 아키텍처나 그래프 업그레이드하자. 관련 작업은 하위 워크트리 만들어서 codex에게 진행해. 검수는 당연히 너가 하고."
- **Archify**: tt-a1i/archify, 커밋 `62f3a995eb26`, 패키지 3.3.1, Apache-2.0
  - 아키텍처·워크플로·시퀀스·데이터 흐름 도식을 검증된 단독 HTML 로 만든다
  - 같은 결과를 SVG 로 내보낼 수 있다
  - Mermaid 를 입력으로 받는다
- **사본**: 다른 프로젝트의 컨트롤 세션이 검토한 사본을 그대로 복제해 `~/.cache/hiway-kit-tools/archify-3.3.1-62f3a99/` 에 고정했다
  - 원본과 `diff -r` 결과 0, `git fsck` 결과 0 을 확인했다
  - 네트워크 접근은 업데이트 조회(`ARCHIFY_UPDATE_CHECK_DISABLED=1` 로 끈다)와 Code Analysis 의 PR 리뷰 가져오기(GitHub API, 쓰지 않는다)뿐이다
  - 런타임 의존성은 없다

## 결정

- **설치 범위 = 이 레포의 로컬 작업 트리만**
  - 각 워크트리에 `.claude/skills/archify` 심볼릭 링크를 둔다. 대상은 위 캐시 사본이다
  - 레포는 `.claude/skills/` 를 추적하므로 `.git/info/exclude` 에 `/.claude/skills/archify` 를 넣는다. 이 파일은 공통 git dir 에 있어 모든 워크트리에 적용되고, 커밋되지 않는다
  - 전역 설치(`~/.claude/skills`·`~/.agents/skills`)는 하지 않는다
  - `plugins/common` 에도 넣지 않는다. 배포물이 아니다
- **설명 페이지 자동 생성 끄기**
  - Archify 의 explainer 기본값은 묻지 않아도 페이지를 만드는 `proactive` 다
  - 로컬 규칙 `.claude/rules/archify.md` 에 `[archify explainer: on-demand]` 를 둔다. `.gitignore` 의 `.claude/*` 규칙으로 이미 무시되는 경로다
- **대상 = 사람이 읽는 현행 문서의 도식**: `README.md`, `docs/` 의 현행 문서
  - 제외 1: `plugins/common/**` — 디렉토리 심사 중에는 고정이고, 배포물이다
  - 제외 2: `CLAUDE.md`·`AGENTS.md` — 에이전트가 텍스트로 읽는다
  - 제외 3: 지위가 historical·superseded 인 문서와 `CHANGELOG.md` — 기록이다
- **산출 형식**: `docs/architecture/diagrams/<slug>/` 아래에 세 파일을 둔다
  - `candidate.json`: 정본
  - `<slug>.html`: 인터랙티브판
  - `<slug>.svg`: 정적판. 테마는 `auto` 다. Archify 의 README 규칙도 정적 SVG 다
  - 문서는 SVG 를 Markdown 이미지로 싣고 HTML 링크를 단다
  - 도식을 대체할 때는 같은 내용을 텍스트로 요약한 문단을 남긴다. 이미지를 못 보는 독자와 에이전트를 위해서다
- **게이트를 약화하지 않는다**
  - `check_doc_refs.py` 의 도식 블록 검사는 README 의 `mermaid`·`skills` 펜스에 걸려 있다. 펜스 안의 `/스킬` 이름은 실재해야 하고, 개수는 넣지 않는다
  - 그 펜스를 SVG 로 바꾸면 이 검사가 사라진다
  - 그러므로 같은 두 규칙을 `docs/architecture/diagrams/*/candidate.json` 의 라벨에도 적용한다
  - SVG·HTML 이 정본 `candidate.json` 과 조용히 어긋나지 않도록 Node 없이 도는 결정적 검사를 둔다(예: Archify 가 산출물에 박는 출처 해시와 정본의 대조)
  - 위 둘 모두 되돌려-FAIL 로 증명한다
- **Code Analysis(의존 그래프)는 조사만 한다**
  - 대상은 `scripts/`·`plugins/common/hooks`·`plugins/common/tools`
  - 결과 HTML 은 레포 밖에 둔다. 발견 요지만 보고서에 쓴다
  - 커밋 여부는 결과를 보고 정한다
- **버전 올림 없음**: 문서와 레포 전용 스크립트만 바뀐다. 플러그인 동작은 바뀌지 않는다

## 구현 계획

1. **A-1 설치·인벤토리**(Codex 워커, 브랜치 `This-HW/archify-diagrams`)
   - 위 결정대로 설치한다
   - 대상 문서의 도식을 전수 조사해 표로 만든다. 열: 파일:줄, 형식(mermaid / ASCII / 표), 무엇을 그리나, 대체 여부와 그 이유
2. **A-2 게이트 선작성**
   - `candidate.json` 라벨에 대한 스킬 실재·개수 금지 검사를 만든다
   - 산출물과 정본의 드리프트 검사를 만든다
   - 테스트가 먼저 실패하는 것을 확인한다
3. **A-3 도식 작성**
   - 인벤토리의 대체 대상마다 Archify 절차를 따른다: Type router → schema·example → candidate → `finalize --quality showcase`
   - 그다음 `export-svg.mjs` 로 SVG 를 내보낸다
   - 모든 노드·관계는 레포 근거(경로:줄)에 묶는다. 근거가 없으면 그리지 않는다
4. **A-4 문서 교체**: README·docs 에 SVG 를 넣고 HTML 링크를 달고 텍스트 요약을 남긴다
5. **A-5 Code Analysis 조사**: 레포 밖에서 실행한다
6. **검수(controller)**
   - 도식을 직접 열어 확인한다
   - 근거 표를 대조한다
   - 게이트를 독립 실행한다
   - 통과하면 main 에 반영한다

## 완료 조건

- `PATH=~/.cache/hiway-kit-tools/venv-pinned/bin:$PATH ./scripts/verify-done.sh` → 41 개 이상 pass / 0 fail
- `python3 -m pytest scripts/tests -q` → rc 0. 새 도식 검사 테스트를 포함한다
- 되돌려-FAIL 확인 둘: 정본 라벨에 없는 `/스킬` 이름을 넣으면 rc 1, SVG 를 정본과 다르게 바꾸면 rc 1
- `git diff --quiet origin/main -- plugins/common` → exit 0 (플러그인 무변경)
- `git check-ignore -q .claude/rules/archify.md && git status --porcelain .claude/skills | grep -c archify` → 0 (설치 흔적 미추적)
- 검수 결과를 `docs/specs/2026-11-25-archify-diagrams/review.md` 에 남긴다 <!-- doc-ref-ok: 검수 단계가 만들 보고서 -->
