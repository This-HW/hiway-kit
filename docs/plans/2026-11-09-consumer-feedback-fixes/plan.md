---
title: "외부 설치 피드백 반영 — ruff 훅 동의 조건·민감 경로 오탐·훅 끄기 스위치·지침 우선순위"
status: current
execution_status: in-progress
as_of: 2026-11-09
created: 2026-11-09
size: medium
---

## 요구사항

다른 사용자가 디렉토리판 v5.5.1(훅 포함)을 설치한 노트북에서 받은 분석(2026-11-09, Snowflake SP·SQL·PySpark
배치 레포)을 실물과 대조해 확인한 결함을 고친다. 판정 근거는 plan-control 세션 실측:

1. **auto-format 이 ruff 를 쓰지 않는 레포에서도 ruff 를 돌린다.** 설정 없는 레포의 PySpark 파일에 v5.5.1 훅을
   실제로 돌리자 손대지 않은 `import os, sys` 가 지워지고 따옴표·공백이 전부 바뀌었다. prettier·eslint 는
   "프로젝트 설정·로컬 바이너리가 있을 때만" 도는데 ruff 만 그 조건이 없다. 부작용 import(UDF 등록 등)면 동작이 바뀐다.
2. **stop-validator 도 같은 조건 없이 `ruff check`/`--fix` 를 돈다**(auto-format 이 못 본 파일 대상).
3. **protect-sensitive 의 이름 패턴이 소스·SQL·문서를 막는다.** v5.5.1 판정 함수 실측:
   `etl/collectors/credential_collector.py`·`sql/sp/SP_UPDATE_USER_CREDENTIALS.sql`·`docs/credential-rotation.md`· <!-- doc-ref-ok: 외부 사용자 레포의 예시 경로 -->
   `src/auth/secret_manager.py` 차단. 오탐은 에이전트를 Bash `cat` 우회로 민다 — 보호가 오히려 약해진다. <!-- doc-ref-ok: 외부 사용자 레포의 예시 경로 -->
4. **훅을 끄는 공식 방법이 없다.** 분석은 "캐시의 hooks.json 에서 Stop 절을 지워라"를 권했다 — 업데이트로 사라진다.
5. **킷 규칙과 사용자·프로젝트 지침의 우선순위가 어디에도 없다**("의사결정은 PM", "트레일러 금지" 같은 메모리와 충돌).

## 결정

- 사용자(2026-11-09): "개선은 진행하되 너가 권장하는 방안으로 진행하자." — 구현·검증은 지금 이 브랜치에서,
  **main push 는 디렉토리 v5.7.1 판정 직후** `fd7d612`(C/C++ 완결성 수정)과 함께 5.7.2 로 낸다. 지금 push 하면
  `directory` 브랜치가 재생성돼 심사 중인 v5.7.1 을 대체한다. 피드백 제공자는 디렉토리 사용자이고 v5.7.1 은 무훅이라
  승인되는 순간 훅 불편이 사라진다.
- ruff 동의 신호 = 파일에서 레포 루트까지의 `ruff.toml`·`.ruff.toml`·`[tool.ruff` 를 가진 `pyproject.toml`.
  전역 `~/.config/ruff/ruff.toml`(setup.sh 가 설치)은 동의로 보지 않는다 — 남의 레거시 레포를 다시 포맷하는 것은
  설치 경로와 무관하게 결함이다. 3.9 floor 라 `tomllib` 없이 줄 앵커 정규식으로 찾는다.
- 민감 경로: 기본 차단을 유지하고 **소스·문서 확장자만 제외**한다(제외 나열 — 새 확장자는 기본 차단). 제외는 이름
  키워드(`credential`·`secret(s)`·`private…key`)에만 적용하고 `/secrets/`·`.aws/`·`.ssh/`·`.env`·키 확장자는
  그대로 막는다. `secrets_manager.py` 차단을 고정하던 기존 테스트는 의도적으로 뒤집는다. <!-- doc-ref-ok: 외부 사용자 레포의 예시 파일명 -->
  **통과시킨 파일은 읽기·쓰기 모두 이 훅의 보호 밖이다** — 콘텐츠 스캔은 env 템플릿 쓰기에만,
  gitleaks 는 이 레포 CI 에만 있다(독립 리뷰 2건이 같은 지적, 처음 적은 "받친다" 는 틀렸다). 그래서
  이름이 키워드·수식어뿐인 시크릿 모듈(`secrets.py`·`config.secret.ts`)과 `secret(s)/`·`credential(s)/` <!-- doc-ref-ok: 외부 사용자 레포의 예시 파일명 -->
  디렉토리·노트북은 확장자와 무관하게 막고, 복합어만 통과시킨다.
- ruff 는 `--force-exclude` 로 부른다 — 경로를 직접 받으면 설정의 `exclude` 를 무시한다.
- 끄기 스위치 = 환경 변수 `HIWAY_KIT_DISABLE_HOOKS`(쉼표 목록 또는 `all`). 프로젝트 `.claude/settings.json` 의
  `env` 가 플러그인 훅 프로세스에 전달됨을 실측(2026-11-09, Claude Code 2.1.319, SessionStart·Stop 둘 다).
- 우선순위 문장은 WORKFLOW 로 주입되는 `using-hiway-kit` 첫 문단과 `AGENTS.md` 내보내기 머리말에 둔다.
- 범위 밖(후속 후보): 계획 파일 위치 설정, 주입량 축소, prompt 형 훅으로 디렉토리판 민감 경로 보호 복원.

- 사용자(2026-11-09, 자문 취합 후): 5.7.2 범위 확대 — *"당연히 함께 넣어야지"*. 행동 eval 은 *"필요하다면
  해야하는거고"*, 원격 probe 브랜치는 *"필요없다면 없애버려"*(삭제 완료). 자문 2건(Claude Opus xhigh·Codex
  gpt-6.1-sol max)을 취합했다.
  확대분: plan-task 위치·승인 게이트, write-tests 기존 배치, sync-docs 기존 문서·지침 파일 지정 시만,
  verify-code 무설치, pre-commit 동의·부분 스테이징, 원장 자동 이관 제거·비-git 무기록, prettier 설정 조건,
  checklist 봉쇄, 정책 `docs/conventions/consumer-footprint.md`, 게이트 §30, eval `path_absent`·`glob_contains`.
  5.8 로 미룸: setup.sh 전역 opt-in 분리, Go/Rust 포맷 동의 조건, 계획 폴더 위치 설정.

- 사용자(2026-11-09 15시): *"자문 2 에이전트랑 너까지 해서 3에이전트가 최적이라고 생각하는 방향으로 개선 진행해.
  내 선택은 3 에이전트 선택을 신뢰하는것으로 일임할게"*. 자문 원문의 입장과 plan-control 판단으로 정했다 —
  모두 결함 수정이라 5.7.2 에 같이 묶고, push 는 그대로 v5.7.1 판정 뒤 한 번(두 자문 모두 한 번의 push 권고).
  - setup.sh: 전역 ruff.toml 설치 **삭제**(5.7.2 훅·pre-commit·review 가 프로젝트 설정만 동의로 보므로 킷에 효과가
    없다), `autoMemoryDirectory` 주입 **삭제**(킷과 무관 — Claude 자문 "삭제", Codex "opt-in" → 2:1),
    `init.templateDir` 는 Codex 단계처럼 **물어서**(두 자문 모두 opt-in). session-check 의 누락 경고 2종은
    선택이 된 조건이라 제거(상시 참 경고 방지).
  - gofmt 는 `go.mod`, rustfmt 는 `rustfmt.toml`·`.rustfmt.toml` 을 동의로 — Codex "Go/Rust 채택 조건", Claude
    정책 1항("바이너리 존재는 동의가 아님", gofmt 수용 의견과 충돌), 이 레포 정책 규칙 2. gofmt 는 설정 파일이
    없어 Go 모듈 여부를 쓴다.
  - `/review` 의 ruff 를 프로젝트 설정 아래 파일로 한정 + `--force-exclude`(Claude P3, 같은 결함 클래스).
  - 계획 폴더 위치 설정은 **하지 않는다** — 두 자문 모두 최하위 후속, 위치는 이미 지침·질문으로 정하고 자동 발견
    한계를 그 자리에서 알린다(Codex 최소 요구 충족). 설정을 더하면 session-start·task-resume·주입 바이트까지
    바꿔야 한다. `--dry-run`(Claude 단독)도 하지 않는다 — 남은 전역 변경이 질문 하나뿐이다.
  - 추가 발견(plan-control): pre-commit 의 엄격한 JSON 검사가 `tsc --init` tsconfig·VS Code 설정 같은 JSONC 를
    막았다 — 제외 목록으로 건너뛴다. 이 머신의 전역 템플릿(`~/.claude/git-templates`, 2026-04 개명 전 판)이
    설정 없이 `ruff --fix` 를 돌리는 것을 스크래치 레포 커밋에서 실측(사용자 환경이라 손대지 않고 보고).

## 구현 계획

1. `hooks/utils.py` — `has_ruff_config(file_path)`·`hook_disabled(name)` 추가.
2. `auto-format.py` `_ruff` — 설정 없으면 건너뜀(디버그 로그).
3. `stop-validator.py` — 린트 대상에서 설정 없는 프로젝트의 파일 제외.
4. `protect-sensitive.py` — 이름 키워드 패턴을 분리하고 소스·문서 확장자 제외.
5. 네 훅(+ `setup/session-check.py`) 진입부에 끄기 스위치.
6. `using-hiway-kit` SKILL·`export_harness.py` BLOCK_HEADER 에 우선순위 문장 → `AGENTS.md`·`GEMINI.md` 재생성.
7. README·`plugins/common/README.md` — 훅 범위(Python·ruff 설정 있을 때만·경로 기준·Bash 미검사)와 끄는 법.
8. 테스트(각 수정 되돌리면 FAIL) + 실물 재현(PySpark 파일 바이트 불변, 경로 표) + 버전 5.7.2·CHANGELOG.

## 완료 조건

- `./.venv/bin/python -m pytest -q tests/hooks/test_auto_format.py tests/hooks/test_stop_validator.py tests/hooks/test_protect_sensitive.py tests/hooks/test_hook_switch.py` rc 0
- `scripts/verify-done.sh` rc 0
- 실물: 설정 없는 레포의 PySpark 파일에 auto-format 훅 실행 후 바이트 불변, `ruff.toml` 추가 시 포맷됨
- 실물: 피드백 레포 유형 경로 표 통과 + 실제 비밀 저장소 표 차단 유지

## 검증 결과

2026-11-09, 브랜치 `consumer-feedback-fixes`(push 전, 5.7.2 = 이 수정 + `fd7d612`).

- `tests/hooks/` 전체 통과(py3.12), py3.9 로드 스모크 통과, `scripts/verify-done.sh` rc 0(세션 주입 6,770B ≤ 7,168B).
- 되돌림 변이 19건 전부 지정 테스트 FAIL — ruff 동의 조건(auto-format·stop 두 곳·빈 목록 가드·pyproject 앵커·레포 루트
  정지), `--force-exclude` 4곳, 민감 경로(소스 예외·파일명 단위 private key·시크릿 모듈·키워드 디렉토리·노트북), 끄기 스위치 5훅.
- 실물: 설정 없는 레포의 PySpark 파일에 auto-format 훅 실행 → 바이트 불변, `ruff.toml` 추가 시 포맷. 실제 훅 프로세스 Read 로
  피드백 레포 유형 경로 5개 통과, 시크릿 저장소·모듈·디렉토리·노트북 8개 차단.
- 독립 리뷰: review-code CONDITIONAL(H1 거짓 보완 통제 문구, M 시크릿 모듈 통과·`exclude` 무시, L 테스트 env 오염·Codex 끄기·자기 해제),
  security-scan 조건부(M 시크릿 모듈, L 스위치) — 전부 반영. 남긴 것: Codex 에서의 스위치 동작 미검증(문서에 명시).

## 후속 후보 (이번 범위 밖)

- 이 변경 전부터 통과하던 비밀 저장소: 서비스 계정 키 JSON·`kubeconfig`·`.pgpass`·`.my.cnf`·`*.jks`/`*.keystore`·`id_dsa`·
  `terraform.tfvars`·Windows `\secrets\` 구분자(보안 점검 목록). 막으면 새 오탐이 생길 수 있어 따로 평가한다.
- 디렉토리판(무훅)에서 prompt 형 훅으로 민감 경로 보호를 되살리는 안. (계획 파일 위치 설정은 `## 결정` 에서 하지 않기로.)

### 확대 범위 검증 (2026-11-09, 커밋 663a712·bf4dbcc + 기준선)

- 픽스처 레포 테스트 `tests/hooks/test_consumer_footprint.py` 11건 — 결함 재현 테스트는 전부 수정 전 코드에서
  FAIL 확인 후 green(양성 대조: ruff 프로젝트의 통째 스테이징 파일은 여전히 고쳐 재스테이징).
- 게이트 §30 `check_consumer_footprint.py` — 수정 전 verify-code 에서 7곳 검출, 현재 0(금지문 2줄은 이유 붙은 표시).
- 독립 리뷰(663a712) CONDITIONAL H2 M5 L3 → 반영(bf4dbcc). ATK-001 무한 루프는 재현되지 않음 — 따옴표 경로가
  `.py` 필터에서 빠져 루프에 닿지 않았다. 대신 그 원인(비-ASCII 경로 린트 누락)을 고치고 테스트로 고정.
- 행동 eval: 새 시나리오 4건. 수정 전 정의 대조 — sync-docs FAIL(CLAUDE.md 변조), verify-code FAIL(npm ci 로
  node_modules 생성), write-tests 2건은 수정 전에도 pass(변별 못 함, 회귀 방지용). 수정 정의 3/3씩 pass.
  전량 기준선 29/29 pass(`evals/baseline/2026-11-08.json`), 10-05 대비 통과율 후퇴 0. haiku 4종은 모델이
  4.5 → 5.5 로 바뀌어 비교 불성립(새 축에서 100%).
- `scripts/verify-done.sh` rc 0 — 38 pass / 0 fail, 세션 주입 6,822B ≤ 7,168B.
- 남은 것: main push 는 디렉토리 v5.7.1 판정 뒤(결정대로). 5.8 후속은 `## 결정` 참조.

### 후속 묶음 검증 (2026-11-09 15시대)

- 결함 재현 테스트는 전부 이전 코드에서 FAIL 확인: `TestGoRustNeedProjectConsent` 음성 3건(gofmt 모듈 밖·레포 밖
  go.mod·rustfmt 무설정), pre-commit JSONC 1건. 양성 대조(go.mod 아래 gofmt·rustfmt.toml 아래 rustfmt·깨진
  package.json 차단)는 신·구 모두 pass.
- 실물: gofmt 1.x 로 훅 실행 — 모듈 밖 파일 불변, `go.mod` 아래 파일만 포맷. rustfmt 는 이 머신에 없어 모의 테스트만
  (미검증으로 남긴다).
- `/review` 스니펫을 SKILL.md 에서 그대로 뽑아 bash·zsh 로 픽스처 레포에서 실행 — 설정 아래 파일만 린트,
  설정 없으면 "스킵됨 (프로젝트 ruff 설정 없음)", 하위 디렉토리에서 실행해도 같음.
- 독립 리뷰(review-code, 적대적): ACCEPT, M6 L6. 전부 반영 — ATK-001 전부 exclude 면 ruff rc 0 "All checks passed!"
  (실측 재현) → 스킵으로 보고 · ATK-002 낡은 전역 템플릿 사본 경고·`--force` 갱신 · ATK-003 절대경로 인자 무한 루프 ·
  ATK-004 README 의 "settings.json 안 건드림"(user 범위 설치가 enabledPlugins 를 쓴다) 정정·등록부 보강 ·
  ATK-005 JSONC 를 이름 목록 + "주석 있으면 주석·끝 쉼표 걷고 재파싱" 두 겹으로 · ATK-006 워크트리(`--git-path hooks`)·
  `core.hooksPath` · ATK-007 quotePath · ATK-008 BASE 를 스니펫 안에서 재계산 · ATK-009 0.5단계 같은 호출·exclude ·
  ATK-010 탐색 범위 독스트링 · ATK-011 gofmt 를 `go fmt ./...` 범위로(testdata·vendor·`.`/`_`) · ATK-012 테스트 보강.
  반영 중 추가 실측: `$( )` 안 `case` 패턴을 macOS bash 3.2 가 구문 오류로 읽는다 → `/review` 스니펫은 if 로,
  pre-commit 의 JSONC 검사기는 함수 + stdin 으로. 스니펫은 bash 3.2·zsh·sh 에서 하위 폴더·한글 경로·전부 exclude·
  절대경로 인자 4경우 실행 확인. 새 setup.sh 테스트 4건·JSONC·template 조회 테스트는 이전 코드에서 FAIL 확인.
- 디렉토리 사전 Validate(2026-11-09 17~19시): 후보의 무훅 트리가 v5.7.1 과 같은 경고 5·보류 2 이지만 자격증명 보류 근거가
  `write-tests` 본문으로 옮겨 감 → 이분 탐색 13판으로 "에이전트 본문에서 코드 스팬을 `·` 로 잇는 줄"(항목 1 첫 줄)로 확정,
  코드 스팬 없이 다시 써 바닥 복귀 확인(`probe-572m`). 기록: `docs/marketplace-submission.md` §v5.7.2 사전 검증.
- 부수 발견: 지운 setup 폴더의 `ruff.toml` 이 그 폴더의 가장 가까운 ruff 설정이라 `session-check.py` 는
  루트 룰셋(lint-single-ruleset)을 받지 않고 있었다. 지우자 EXE001·UP036·UP031 이 드러나 고쳤다(실행 비트, 하한
  검사 예외 표시, f-string).
