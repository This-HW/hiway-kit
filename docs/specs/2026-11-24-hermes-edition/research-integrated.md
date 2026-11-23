---
status: historical
as_of: 2026-11-24
---

# Hermes Agent × hiway-kit — 통합 보고서

- 작성 2026-11-24, 통합: plan-control 세션(Claude Opus 5.5)
- 원 보고서(독립 조사, 서로 열람 안 함):
  - `claude-report.md` — Claude Opus high, Orca task `task_5200402aea41`
  - `codex-report.md` — Codex gpt-6.2-sol xhigh, Orca task `task_6f0770402e63`
- 두 조사 모두 같은 스냅샷을 읽었다: `NousResearch/hermes-agent` @ `352b249`(main, 2026-11-23), stable v0.23.3, 킷 `5164e82`(v5.9.1)
- 두 조사 모두 **소스·문서만 읽었다.** Hermes 설치·실행은 하지 않았다. 아래 판정은 전부 런타임 미실측이다

## 0. 결론 5줄

1. 대상은 Nous Research 의 `hermes-agent` 다. 두 엔진이 독립적으로 같은 결론을 냈고, 스타는 약 26.5만이며 주 단위로 릴리스된다.
2. **규칙은 지금도 전달된다.** `/harness-export` 의 `AGENTS.md` 를 Hermes 가 시스템 프롬프트와 서브에이전트 프롬프트에 싣는다.
   - 단, 프로젝트에 `.hermes.md`·`HERMES.md`·`AGENTS.override.md` 가 있으면 `AGENTS.md` 가 가려진다.
   - 인젝션 스캐너에 한 줄이라도 걸리면 파일 전체가 BLOCK 된다.
3. **스킬 17종은 패키징만 정하면 옮길 수 있다.** 패키징 방식에서 두 엔진의 의견이 갈렸고(§3), 어느 쪽을 고를지는 샌드박스 실측으로 정해야 한다.
4. **에이전트 15종과 훅 5종은 그대로는 옮겨지지 않는다.**
   - 에이전트: 에이전트 정의를 읽는 로더가 없다. `delegate_task` 의 goal/context 로 강등된다.
   - 훅: 이벤트는 대응된다. 다만 셸 훅은 사용자 `config.yaml` 에서만 켤 수 있고, 입력 페이로드가 달라 어댑터 코드가 필요하다.
5. **권장 순서**: ① 문서와 비활성 타겟만 추가 → ② 격리 샌드박스에서 결정 변수 3개를 실측 → ③ 패키징 방식 확정 후 스킬 배포 → ④ 훅·역할 어댑터는 수요가 생기면.

## 1. 두 조사가 일치한 사실 (교차 확인)

| 항목 | 내용 | 근거(양쪽) |
| --- | --- | --- |
| 확장 면 | 네이티브 플러그인(`plugin.yaml` + `register(ctx)`), Agent Plugins v1 포터블(`plugin.json` + `skills/` + `mcp.json`), 사용자 `config.yaml` 의 MCP·셸 훅, Gateway 이벤트 훅 | `developer-guide/plugins/index.md`, `hermes_cli/agent_plugins.py` |
| 매니페스트 우선순위 | 같은 디렉토리에 `plugin.yaml` 이 있으면 `plugin.json` 은 보지 않는다 | `plugins_discovery.py` |
| AP v1 요건 | `$schema` 가 `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` 이어야 한다. 킷 `plugins/common/plugin.json` 은 Antigravity `$schema` 라 **그 경로를 Hermes 용으로 쓸 수 없다** | `agent_plugins.py:46-262` |
| 스킬 형식 | 킷 17종의 frontmatter 가 AP v1 제약(이름 정규식, description ≤1024자 등)을 통과한다(정적) | 양쪽 로컬 파서 |
| manual-only | `disable-model-invocation` 을 Hermes 가 해석하지 않는다. 그래서 `harness-export`·`skill-forge`·`using-hiway-kit` 이 자동 호출될 수 있다 | 로더 코드 |
| 플러그인 스킬 노출 | 문서는 "인덱스에 안 들어간다"고 쓰지만 코드(`prompt_builder.py:1198`)는 넣는다. **둘 다 코드를 따랐다** — 실측으로 닫을 항목 | 같은 sha |
| 규칙 경로 | 프로젝트 컨텍스트 우선순위: `.hermes.md`/`HERMES.md` → `AGENTS.override.md` → `AGENTS.md` → `CLAUDE.md` → Cursor 규칙. 시스템 프롬프트 섹션 등록은 4,000자/8,000자 상한이라 규범 전문(약 7,100자)은 들어가지 않는다 | `context-files.md`, `prompt_builder.py` |
| 위임 | `delegate_task(goal, context)` 를 쓴다. 자식은 부모 도구를 상속하고, 에이전트별 `model`·`tools`·`isolation` 은 적용되지 않는다. 모델은 `delegation` 의 `model_map`·`profile_routes`(사용자 설정), 워크트리 격리는 전역 옵션이다 | `delegation.md` |
| 훅 대응 | `pre_tool_call`↔protect-sensitive, `post_tool_call`↔auto-format, `pre_verify`↔stop-validator(Claude Code Stop 응답 형태를 받는다), `pre_llm_call`↔session-start 의 계획·LESSONS. `on_session_start` 는 반환값을 무시한다 | `hooks.md` |
| 설치 | `hermes plugins install This-HW/hiway-kit/plugins/common --ref <40자 sha> --no-enable` 로 하위 디렉토리를 설치할 수 있다. 설치할 때 정적 보안 스캔을 하고, dangerous 판정이면 설치가 막힌다 | `plugins_cmd.py:301`, `features/plugins.md` |

## 2. 한쪽만 찾은 것

- **Claude 만 찾음**:
  - **설치 스캐너가 걸 수 있는 구체 지점** — `hooks/protect-sensitive.py:59` docstring 의 `` `cat .env` `` 가 `skills_guard.py` 의 `read_secrets_file`(critical) 근사 대조에 걸렸다. dangerous 로 판정되면 `--force` 로도 넘길 수 없다. 근사 대조라 판정은 미확인이다.
  - Hermes 가 `.claude-plugin` 등 다른 하네스 매니페스트 디렉토리를 명시적으로 건너뛴다(`_FOREIGN_HARNESS_MANIFEST_DIRS`).
  - 레퍼런스 구현: `obra/superpowers` 의 `.hermes-plugin`.
- **Codex 만 찾음**:
  - Gateway 는 프로젝트 `./.hermes/plugins/` 를 로드하지 않는다 → 배포 경로는 사용자 프로필 설치로 잡는다.
  - `delegation.worktree_isolation` 은 격리 생성에 실패하면 공유 CWD 로 진행할 수 있다 → 수정 역할의 격리를 보장하는 데 쓸 수 없다.
  - `plugins.isolation: host` 와 `host.launcher` 로 외부 샌드박스를 붙일 수 있다.
  - 기준선: `build-targets.py --check`·`export-harness.sh --check`·`verify-done.sh` 41/0 을 실행해 확인했다.

## 3. 갈린 판단 — 패키징 경로

| | Claude 안 | Codex 안 |
| --- | --- | --- |
| 1차 형식 | **AP v1 포터블** — 루트 `plugin.json` 을 "AP v1 상위집합" 하나로 통일하고 Antigravity 와 공유 | **네이티브** — `plugins/common/plugin.yaml` + 작은 `__init__.py`(`register(ctx)` 로 스킬 등록) |
| 장점 | 파이썬 코드를 싣지 않는다. 생성기(SSOT→매니페스트) 관례 안에 있다 | Antigravity 를 건드리지 않는다. manual-only 3종을 등록에서 뺄 수 있다 |
| 위험 | agy 가 AP `$schema`·추가 필드를 받는지 재실측이 필요하다. 거부하면 무너진다 | 공유 트리에 `.py` 가 생긴다. Claude 디렉토리 축소판 빌더가 비허용 형식에서 멈추므로 제외 목록에 넣어야 하고, Codex ZIP 도 함께 확인해야 한다. 코드 유지보수 부담이 생긴다 |
| 대안 | 3단계 네이티브는 보류 | AP v1 을 고르면 **별도 생성 루트**(`dist/hermes/...`)에 패키지를 만든다 |

**통합 판단**: 두 안 모두 `plugins/common` 을 통째로 설치하므로, 설치 스캐너가 공유 트리(Claude 용 훅 `.py`)를 막으면 함께 무너진다. 그래서 형식보다 먼저 정할 것은 **"공유 트리를 그대로 설치할지, Hermes 전용 생성 루트를 만들지"** 이고, 이는 샌드박스 실측 한 번으로 갈린다.

- 스캐너가 공유 트리를 통과시키면: Codex 안(네이티브, agy 무변경)이 변경 범위가 가장 작다.
- 스캐너가 막으면: 별도 생성 루트 + AP v1(파이썬 없음)이 낫다. 디렉토리 축소판 빌더와 같은 "축소본 생성" 관례를 재사용할 수 있다.

## 4. 권장 실행 순서

**① 지금 할 수 있는 것 (문서·정책만, 실측 불필요, 0.5일)** — 두 안 공통
- `packaging/targets.json` 에 비활성 타겟 `hermes`(`enabled:false`, `verificationLevel: researched-only`, 사유·관측 키)를 추가한다. 생성기 동작은 바뀌지 않는다.
- `docs/harnesses.md` 에 Hermes 절을 추가한다:
  - `AGENTS.md`(harness-export)와 `.hermes.md`·`AGENTS.override.md` 가림 주의
  - 빠른 평가용 `skills.external_dirs`(클론은 읽기 전용으로 — `skill_manage` 가 고칠 수 있다)
  - 두 경로를 동시에 켜면 스킬이 이중 로드된다는 경고
- `harness-export` SKILL.md 의 하네스 표에 Hermes 행을 추가한다.
- README 기능표·Quick Install 에는 **아직 넣지 않는다**("약속 ≠ 실물").

**② 샌드박스 실측 (결정 변수 3개, 1~2일, 사용자 승인 후)**
- 환경: 메모리 규칙("서드파티 하네스는 쓰기부터 deny")대로 `sandbox-exec` 또는 폐기 VM 을 쓴다. `install.sh | bash` 는 쓰지 않고, 고정 sha 소스를 임시 venv 에 설치한다.
- 결정 변수:
  1. `hermes plugins validate` 의 보안 스캔이 `plugins/common` 에 내리는 판정(safe/caution/dangerous)과 원인 파일
  2. 플러그인 스킬이 `<available_skills>` 와 `skills_list` 에 실제로 나오는지(문서·코드 불일치를 닫는다)
  3. agy 가 AP v1 `$schema` 를 받는지(Claude 안을 고를 때만)
- 양성·음성 대조를 함께 돌린다: 최소 AP 패키지는 통과해야 하고, 현 `plugin.json` 은 `manifest_invalid` 로 막혀야 한다.

**③ 스킬 배포 (②의 결과로 경로를 고른 뒤, 1.5~3일)**
- 생성기 분기와 테스트, `path-containment` 봉쇄, 드리프트 게이트를 갖춘다.
- manual-only 3종의 처리를 정한다: 네이티브는 등록에서 빼고, 포터블은 문서로 한계를 명시한다.
- 실측에서 확인된 칸만 README 에 "지원"으로 올린다.

**④ 훅·역할 어댑터 (수요가 생기면, 3~6일+)**
- 페이로드 프로브(실물 `pre_tool_call`·`pre_verify` 입력 원문)를 먼저 확보한다.
- 첫 대상은 읽기 전용인 `review-code` 브리프 위임, 또는 opt-in `post_tool_call` 포매터.
- 차단 훅은 `fail_closed` 와 실행면별(terminal·execute_code·MCP) 도달 범위를 실측한 뒤에 한다.

## 5. 위험 (통합)

- **발견 ≠ 호출 ≠ 집행** — `plugins list` 에 보이는 것과 모델이 스킬에 도달하는 것, 보호가 실제로 작동하는 것은 각각 따로 관측해야 한다. (Codex)
- **설치 스캐너 dangerous 는 우회할 수 없다** — 공유 트리 설치의 최대 위험이다. (Claude)
- **`AGENTS.md` 전체 BLOCK** — 소비자 문장 하나가 스캐너에 걸려도 킷 블록까지 사라진다. 킷이 통제할 수 없으므로 한계로 문서화한다.
- **이중 로드** — 포터블(`hiway-kit:` 네임스페이스)과 `external_dirs`(네임스페이스 없음)를 함께 켜면 스킬이 34개가 된다.
- **변경 속도** — Hermes 는 v0.23 이고 하루에도 여러 번 커밋된다. 네이티브 코드는 유지보수 부채가 된다.

## 6. 남은 미확인 (양쪽 합집합, 중복 제거)

1. 설치 스캐너의 실제 판정과 원인 파일
2. 플러그인 스킬의 인덱스 노출 여부
3. agy 의 AP v1 수용 여부
4. 포터블 단독 카탈로그 등재 요건 — 문서의 "plugin.yaml + entrypoint" 와 `0bull.yaml` 등재 사실이 어긋난다
5. `agent-importers` 가 Claude Code 플러그인 캐시의 스킬을 가져오는지
6. 셸 훅 `pre_llm_call` 의 `extra.is_first_turn` 실재 여부와 각 이벤트 페이로드 원문
7. 모델 호출 없이 로드된 컨텍스트를 확인하는 방법
8. manual-only 에 해당하는 Hermes 쪽 필드 존재 여부
9. CLI·TUI·Desktop·Gateway·cron 별 플러그인 진입점 차이
10. 최소 지원 Hermes 버전과 킷 행동 eval 의 Hermes 어댑터
