# W-046 — Work 시스템을 걷어내고 계획 파일 규약으로 교체 (+ Aside 웹 사용 안내)

> 결정: 컨트롤(2026-09-28, 사용자가 판단을 위임 — *"work는 현재 시스템이 효율적인지 범용적으로
> 잘 작동될지 검토해보고 너가 결정해"*). 버전: **4.0.0**(소비자 동작 변경 — Work 시스템 제거).

## 1. 실측한 사실 (결정의 근거)

| # | 사실 | 등급 |
| --- | --- | --- |
| F1 | 배포 스킬 `plan-task`(L60-66)·`auto-dev`(L27,41,57-59,180)가 `./scripts/work.sh new/start/next-phase` 를 실행하라고 지시한다. `work.sh` 는 **레포 전용** — `git ls-files plugins \| grep work.sh` 0건, `setup.sh` 도 설치하지 않는다 | confirmed |
| F2 | 그 대체로 `plan-task/references/work-system.md` 가 안내하는 채번은 `ls docs/works/idea/ \| ... \| tail -1` — **idea 폴더만** 봐서 active/completed 의 ID 와 충돌한다 | confirmed |
| F3 | Work 는 `docs/works/` 가 **있을 때만** 켜지는 opt-in 인데, 킷은 그 디렉토리를 만들지 않는다 → 대부분의 소비자에게 기능이 한 번도 실행되지 않는다. 켜는 순간 F1 로 실패한다 | confirmed |
| F4 | 이 레포에서 `docs/works/` 는 gitignore — 원장이 워커 워크트리에 보이지 않아 W-044 는 산출물을 `docs/specs/` 로 옮겼고 progress.md 는 읽는 사람 없이 갱신됐다. **W-045 는 work.sh 를 쓰지 않았다**(W-045 디렉토리 없음). 실제 SSOT 는 `docs/specs/` + CHANGELOG 였다 | confirmed |
| F5 | `work.sh` 발급기가 gitignore 된 디렉토리 + 레지스트리만 세서 기존 ID(W-025)를 재발급했다 | confirmed |
| F6 | 표면 크기: `plan-task` 9.0KB + `work-system.md` 10.9KB + `auto-dev` 17.8KB + `task-resume` 2.5KB, 배포 파일 16개가 Work 를 참조 | confirmed |
| F7 | 하네스 무관하게 가치가 있는 조각은 둘 — (a) 루프가 요약 대신 다시 읽는 **계획 원문**(`loop-engineering` 재앵커), (b) `verify` 명령 exit 0 일 때만 닫히는 **checklist**(`hooks/checklist.py`, DoD 직결). Claude Code 네이티브 Tasks 는 완료를 명령 결과로 막지 못하고, Codex 에는 영속 Tasks 가 없다 | confirmed(소스) |

## 2. 결정

**Work 시스템(ID·단계 폴더·phase 상태기계·work.sh·progress/decisions 분리)을 제거하고,
아래 "계획 파일" 규약 하나로 교체한다.**

### 2.1 계획 파일 규약 — 인터페이스 계약 (세 트랙이 공유, 변경 금지)

```
docs/plans/<YYYY-MM-DD>-<slug>/
├── plan.md          # 필수
└── checklist.json   # 선택 — 실행 단계에서 hooks/checklist.py 가 만든다
```

- **식별자 = 디렉토리 이름.** 발급기 없음. 같은 이름이 있으면 `-2`, `-3` 을 붙인다.
- `plan.md` frontmatter — 키 이름 고정:
  ```yaml
  ---
  title: "<한 줄 제목>"
  status: planning        # planning | in-progress | done
  created: 2026-09-28     # YYYY-MM-DD
  size: medium            # small | medium | large
  ---
  ```
- `plan.md` 본문 절 — 이 순서: `## 요구사항` · `## 결정` · `## 구현 계획` · `## 완료 조건`(실행 가능한 명령) ·
  `## 검증 결과`(auto-dev 가 끝에 추가).
- **활성 계획** = `docs/plans/*/plan.md` 중 `status` 가 `done` 이 아닌 것.
- 상태(`status`)·checklist 쓰기는 **메인 세션만**(parallel-worktree 규범 그대로).
- 파일을 만드는 시점: `plan-task` 가 **Medium/Large** 로 판정한 작업. Small 은 대화 안에서 끝낸다.
  (opt-in 디렉토리 감지 방식은 폐기 — F3: 아무도 켜지 않는 기능이 됐다.)
- `docs/plans/` 를 트래킹할지는 소비자가 정한다. 킷은 gitignore 하지 않는다(F4 의 교훈: 워커가 봐야 한다).

### 2.2 구버전 소비자

`docs/works/active/` 에 디렉토리가 하나라도 있으면 session-start 가 **한 줄** 안내를 낸다
(구 원장을 읽지는 않는다). 정상 운영(구버전 흔적 없음)에서는 거짓이라 상시 소음이 아니다
(`warning-signal.md` 검토 1). 이전 방법은 CHANGELOG 4.0.0 에 적는다.

### 2.3 Aside 웹 사용 안내 (사용자 요청 2026-09-28)

*"우리 플러그인에 aside 활용에 대한것도 추가하자. 있다면 웹 사용시 그거 쓰라고."*
`web-research` 스킬에 "로그인된 브라우저가 필요한 웹 작업" 경로를 추가한다 — **`command -v aside` 로
있을 때만** `aside guide` 를 읽고 `aside exec` 로 위임, 없으면 기존 경로(MCP/WebFetch)로 폴백.
킷은 그 존재를 가정하지 않는다(CLAUDE.md interoperability 3원칙). 에이전트 `tools:` 에는 넣지 않는다.

## 3. 트랙 (파일 소유권 disjoint)

| 트랙 | 모델 | 소유 파일 |
| --- | --- | --- |
| T1 hooks-gates | opus | `hooks/session-start.py`, `hooks/checklist.py`, `hooks/tests/test_session_start.py`, `hooks/tests/test_checklist.py`, `scripts/verify-done.sh`(§8 만), `scripts/checklist.sh`, `scripts/work.sh`(삭제), `scripts/tests/test_work_sh.py`(삭제), `scripts/check_registry_describe.py`(메시지 1줄), `scripts/feedback.sh`(주석 1줄) |
| T2 skills | opus | `skills/plan-task/**`, `skills/auto-dev/SKILL.md`, `skills/brainstorming/SKILL.md`, `skills/skill-forge/SKILL.md`, `skills/using-hiway-kit/SKILL.md`, `skills/web-research/SKILL.md`, `plugins/common/README.md` |
| T3 rules-docs | sonnet | `rules/task-resume.md`, `rules/parallel-worktree.md`, `rules/CHECKSUMS.sha256`, `docs/architecture/rules/task-resume.md`, `docs/architecture/rules/MIRROR.sha256`, 루트 `README.md` |

**컨트롤 소유**: `CHANGELOG.md`, 버전(4.0.0) + 타겟 매니페스트, `AGENTS.md`/`GEMINI.md`(export-harness),
`CLAUDE.md`, eval 기준선, `docs/specs/**`.

## 4. 완료 조건 (통합 브랜치에서 컨트롤이 실행)

1. `git grep -n -E 'docs/works|work\.sh|W-XXX|Work ID' -- plugins` → 구버전 안내 1곳(session-start)과
   feedback_ledger 의 구 원장 이관 경로 외 0건
2. `./scripts/verify-done.sh > out 2>&1; echo $?` → 0
3. `python3 -m pytest -q` → rc 0
4. `claude plugin validate plugins/common` → 통과
