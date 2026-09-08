# 04 — HANDOFF: 구현 LLM 진입점

> **매 세션 처음 읽는 파일이다.** 다른 무엇보다 먼저 읽어라.
> 이 문서는 "무엇을 아는가 / 무엇을 하면 안 되는가 / 지금 어디인가" 를 준다.
> 작업 내용은 여기 없다 — `02-stages.md` 의 해당 Stage 에 있다.

---

## 0. 착수 30초 체크 (건너뛰지 마라)

```bash
# 1) 기준 커밋 확인 — D-30 규범. 불일치하면 즉시 에스컬레이션하고 착수하지 마라.
git rev-parse HEAD
#    브리프가 적어 준 해시와 다르면 STOP. 브랜치 이름(main)은 기준으로 쓰지 않는다.

# 2) 워크트리 상태
git status --porcelain          # dirty 면 왜 그런지 먼저 파악한다
pwd                             # 워크트리 루트인지 확인. 원본 레포로 cd 하지 마라

# 3) 게이트 기준선 — 착수 전 green 인지 확인한다.
./scripts/verify-done.sh; echo "exit=$?"
#    착수 전 red 면, 그 red 가 내 작업 때문인지 아닌지 나중에 분간할 수 없다.
```

**왜 1번이 규범인가.** 직전 배치에서 워커 5기가 11커밋 뒤처진 트리에서 감사를 수행해
거짓 양성이 나왔다(설계문서 §10.2). 브랜치 이름은 낡을 수 있고 해시는 낡지 않는다.
이것이 D-30 이고, `control-loop` P3 의 **규범 본문**으로 들어간다(부록이 아니다).

---

## 1. 문서 지도

| 문서 | 무엇을 답하나 | 언제 읽나 |
| --- | --- | --- |
| **`review/04-handoff.md`** (이 파일) | 자격·금지선·현재 위치 | **매 세션 처음** |
| `review/01-policy.json` | **숫자와 규칙**. 예산·티어·버전·기한·게이트 플래그 | 값이 필요할 때. **산문에서 숫자를 다시 찾지 마라** |
| `review/02-stages.md` | **이번 턴의 작업 범위**. Stage 별 4블록 | 착수 직후 |
| `review/03-gate-spec.md` | **"완료"의 정의**. 명령 / 통과 조건 / 되돌려-FAIL | 완료 선언 직전 |
| `review/00-REVIEW.md` | 설계의 알려진 결함 26건 + 근거. **검수 시점 기록 — 고치지 않는다(역사)** | Stage 지시가 설계문서와 어긋나 보일 때 |
| `review/05-coverage.md` | **감사 발견 → Stage 항목 추적 매트릭스. 미배정 0건 증명** | "이건 누가 하나?" 가 떠오를 때 |
| `docs/specs/2026-09-07-hiway-program-design.md` | 원본 설계(D-1~D-33). **왜** 그렇게 결정했는가 | 결정의 근거가 필요할 때 |
| `docs/specs/2026-09-07-census/T{1..5}-findings.md` | 전수 감사 원본(222 파일). 결정의 증거 | 발견의 원문이 필요할 때 |
| `CLAUDE.md` | 레포 규약. 경로 봉쇄·게이트 통합 금지·섹션 번호·릴리스 절차 | 코드를 쓰기 전 |
| `packaging/targets.json` | 다중 하네스 실측 기록. **사실 3분류 태깅의 모범 사례** | 하네스 판정이 필요할 때 |
| `evals/policy.json` | 정책값을 데이터로 분리한 기존 사례 | 새 정책값을 둘 곳을 정할 때 |

### 충돌하면 누가 이기나

```
사용자의 직접 지시  >  이 4개 문서(01~04)  >  설계문서 D-1~D-33  >  감사 원본 T1~T5
```

**단, `00-REVIEW.md` 가 지적한 26건에 대해서는 이 문서 세트가 설계문서를 정정한다.**
Stage 지시가 설계문서와 달라 보이면 `00-REVIEW.md` 에서 해당 번호(L·E·O·R)를 찾아라 —
이유가 근거와 함께 적혀 있다. **찾지 못하면 그건 내 실수이니 에스컬레이션하라.**

---

## 2. 절대 금지선 (권한이 있어도 단독으로 하지 않는다)

> 되돌릴 수 없거나, 외부에 실제 효과를 내거나, 되돌림 자산이 없는 행위.
> **모든 Stage 지시서에 이 목록이 복사된다.** `01-policy.json` `absoluteProhibitions` 와 동일.

1. **`git push`** — 모든 원격, 모든 브랜치.
2. **`git tag` · `git push --tags`** — 릴리스 태그는 컨트롤만.
3. **`main` 으로의 머지** — 워커는 자기 브랜치에만 커밋한다(§4.2 P3).
4. **마켓플레이스 항목 생성·수정·삭제, 커뮤니티 카탈로그 제출**(27-5·27-6).
5. **플러그인 개명 실행**(27-5) — 프로브(27-1) 미완이면 외부 되돌림이 불가능하다.
   카탈로그는 익일 동기화라 잘못 나간 이름이 최소 하루 살아 있다.
6. **`~/.claude/settings.json` · `~/.claude.json` 등 사용자 전역 설정 변경** — W-025 A 트랙
   전부. **커밋이 없어 되돌림 자산이 존재하지 않는다.** 스냅샷 없이 손대지 마라.
7. **`~/.claude/plugins/cache` · `~/.claude/projects` 삭제** — 후자는 메모리·`self-improve` 의
   원천 자산이다.
8. **API 키·크리덴셜 발급·폐기** — §1.5 의 gemini·magic 키 폐기는 사용자 몫으로 남아 있다.
9. **eval 전량 실행으로 기준선 파일 덮어쓰기** — 재생성은 `regenerationCadence` 규정대로
   배치 안에서, 컨트롤 승인 후.
10. **`git stash pop` / bare `git stash`** — 스택이 다른 워크트리와 공유된다.
    설 곳이 필요하면 **임시 WIP 커밋**을 쓴다.
11. **설계문서 직접 수정** — `docs/specs/2026-09-07-hiway-program-design.md`.
    반영은 컨트롤이 한다.

**막히면 혼자 정하지 말고 에스컬레이션하라.** 답을 기다리는 동안 답과 무관한 항목을
진행하면 된다. 이것이 `control-loop` P3 의 규율이고, 이 배치가 그것을 스킬로 만든다.

---

## 3. 자격 인벤토리 — 확보된 접근 권한이 곧 범위선

### 확보됨 (이 경계 안쪽을 검증 가능하게 만든다)

| 자격 | 경계 |
| --- | --- |
| 레포 읽기·쓰기 | **워크트리 로컬 브랜치 한정.** push 불가 |
| `python3` / `pytest` / `ruff` | 핀 버전은 `.pytest-version` · `.ruff-version`. **핀과 다르면 `verify-done.sh` 가 경고한다** |
| `shellcheck` | 핀은 `.shellcheck-version`. **미설치는 로컬 yellow, red 아님** — CI 가 권위 |
| `scripts/verify-done.sh` | 전 게이트 로컬 실행 |
| `evals/run.py --validate` / `--dry-run` | 오프라인. **실제 채점은 API 비용 발생** |
| `claude` CLI | `evals/run.py:1304` 가 PATH 존재를 확인한다 |
| `git` 로컬 조작 | 브랜치 내 커밋. main 머지·tag·push 불가 |

### 미확보 (기다리지 않는다 — 경계 안쪽을 먼저 완성한다)

| 자격 | 상태 | 누가 넓히나 |
| --- | --- | --- |
| 마켓플레이스 스크래치 설치 | W-019 의 `cck-probe-marketplace` 기법이 있었다는 정황만 | **27-1(S18)** 이 프로브로 경계를 넓힌다 |
| `agy` CLI (Antigravity) | `targets.json` 에 1.1.20 실측 기록. 현재 설치 여부 미확인 | — |
| `codex` CLI | `~/.codex/plugins` 에 kit 없음(§1.2). CLI 존재 미확인 | — |
| 커뮤니티 카탈로그 제출 | 일회성 리스팅은 `clau.de/plugin-directory-submission` 경유 | 27-6(S23) · 컨트롤 |

**미확보 항목을 이유로 Stage 를 미루지 마라.** 예: "Codex 에서 검증할 수 없으니 파리티
문장을 못 쓴다" 가 아니라, **"행동 eval 은 현재 Claude Code 만 구동한다" 를 명시해서 쓴다**
(D-12). 경계선을 정직하게 그리는 것이 이 프로그램의 판단 기준 1이다.

---

## 4. 지금 어느 Stage 인가 — 판별 절차

> 세션이 끊겨도 **레포 상태만 보고** 위치를 복원할 수 있어야 한다.
> 아래를 위에서부터 실행하고, **처음으로 실패하는 줄이 현재 Stage** 다.

```bash
# ── W-025 C 트랙 ────────────────────────────────────────────────
# S1 참조 정합 + §17 게이트 (같은 커밋)
grep -q '^hdr "17\.' scripts/verify-done.sh && echo "S1 게이트 done" || echo "→ S1 미완: §17 없음"
python3 -c "
import re,pathlib,sys
bad=0
for p in pathlib.Path('plugins/common/agents').rglob('*.md'):
    t=p.read_text()
    if not t.startswith('---'): continue
    fm=t[3:t.find('---',3)]
    m=re.search(r'^references:\s*\n((?:\s+-\s+.*\n)+)',fm,re.M)
    if not m: continue
    for l in m.group(1).strip().splitlines():
        r=l.strip().lstrip('- ').strip(); r=r[5:].strip() if r.startswith('path:') else r
        if not (p.parent/r).resolve().exists(): bad+=1
sys.exit(1 if bad else 0)" && echo "S1 done" || echo "→ 현재 S1"

# S2 스킬 정리
[ ! -f plugins/common/skills/README.md ] && echo "S2 부분 done" || echo "→ 현재 S2"
[ "$(ls plugins/common/skills | wc -l | tr -d ' ')" -eq 19 ] && echo "S2 done" || echo "→ S2 미완(이관 필요)"

# S3 에이전트 축약
[ "$(grep -rl '검증 그린일 때만' plugins/common/agents/ | wc -l | tr -d ' ')" -eq 0 ] \
  && echo "S3 done" || echo "→ 현재 S3"

# S4 티어 선언 (골격)
grep -q "^tier:" plugins/common/rules/definition-of-done.md 2>/dev/null \
  && echo "S4 done" || echo "→ 현재 S4"
grep -q "ALWAYS_RULES" plugins/common/hooks/session-start.py \
  && echo "→ S4 미완: ALWAYS_RULES 아직 존재"

# S5 규범 삭제·중립화  (§17 게이트는 S1 에 흡수됐다 — 아래 S1 검사에 포함)
[ ! -f plugins/common/rules/tool-usage-priority.md ] && echo "S5 부분 done" || echo "→ 현재 S5"
[ ! -f docs/architecture/rules/tool-usage-priority.md ] && echo "S5 미러 done" || echo "→ S5 미완: 미러 잔존"
grep -q "tool-usage-priority" plugins/common/hooks/export_harness.py \
  && echo "→ S5 미완: export_harness 분류표에 유령 엔트리(§11 raise)"

# S24 untrusted-text 규범 신설 (Q2)
[ -f plugins/common/rules/untrusted-text.md ] && echo "S24 done" || echo "→ S24 미착수"
grep -q "비신뢰 텍스트" plugins/common/skills/using-claude-code-kit/SKILL.md \
  && echo "→ S24 미완: 절이 아직 SKILL.md 에 있다"
grep -q '"untrusted-text"' plugins/common/hooks/export_harness.py \
  || echo "→ S24 미완: export_harness PORTABLE 미등재(§11 raise)"
echo "규범 수: $(ls plugins/common/rules/*.md | wc -l | tr -d ' ')  (최종 목표 13 — 삭제1+신설1)"

# S6 축약 + §16 게이트 (같은 커밋)
python3 -c "
from pathlib import Path
core=['definition-of-done','loop-engineering','planning-protocol','code-quality','planning-check','ssot']
s=sum(len(Path(f'plugins/common/rules/{c}.md').read_bytes()) for c in core)
print(f'core6={s}B (여유 5857B — 총량 예산 9216B 에서 역산)')"
grep -q '^hdr "16\.' scripts/verify-done.sh && echo "S6 게이트 done" || echo "→ S6 미완: §16 없음"

# S7 릴리스
grep -m1 '\"version\"' plugins/common/.claude-plugin/plugin.json
head -3 CHANGELOG.md | grep -o '\[[0-9.]*\]'

# ── W-025 B 트랙 ────────────────────────────────────────────────
# (S8·S9 는 퇴역 번호 — 각각 S6·S1 에 흡수됐다. 번호를 재사용하지 마라.)
grep -q "about.md" scripts/check_doc_counts.py && echo "S10 부분" || echo "→ S10 미착수"
[ "$(grep -rn 'spec_from_file_location' --include='*.py' . | grep -v .venv | wc -l | tr -d ' ')" -eq 1 ] \
  && echo "S11 부분 done" || echo "→ S11 미완"
grep -q "@docs/conventions" CLAUDE.md && echo "S12a done" || echo "→ S12a 미착수"
[ ! -d docs/superpowers ] && echo "S12b 부분 done" || echo "→ S12b 미완"

# ── W-026 ───────────────────────────────────────────────────────
grep -q "class ClaudeCodeHarness" evals/run.py && echo "S13 done" || echo "→ S13 미착수"
[ -f plugins/common/skills/control-loop/SKILL.md ] && echo "S14 done" || echo "→ S14 미착수"

# ── W-027 ───────────────────────────────────────────────────────
ls docs/specs/*marketplace-probe* >/dev/null 2>&1 && echo "S18 done" || echo "→ S18 미착수"
grep -m1 '"name"' plugins/common/.claude-plugin/plugin.json    # hiway-kit 이면 S22 완료
```

**해석 규칙**: `→ 현재 SN` 이 여럿 나오면 **`02-stages.md` §0 의 의존 그래프에서 선행이 없는
쪽**을 먼저 한다. C 트랙 전체가 B 트랙보다 앞선다.

---

## 5. 매 Stage 공통 규율

### 5.1 착수

1. `02-stages.md` 의 해당 Stage **4블록 전체**를 읽는다. **전제(변경 금지)** 를 먼저 읽어라 —
   무엇을 건드리면 안 되는지가 무엇을 해야 하는지보다 중요하다.
2. 필요한 값은 **`01-policy.json` 에서만** 가져온다. 설계문서 산문에서 숫자를 다시 찾지 마라 —
   §9.1 의 측정표처럼 **틀린 숫자가 산문에 남아 있다**(`00-REVIEW.md` E1).
3. 착수 전 `./scripts/verify-done.sh` 로 기준선을 확인한다.

### 5.2 진행 중

- **읽기 집합을 넘기지 마라.** Stage 머리에 적힌 파일들이 이번 턴의 범위다. 다른 파일을
  고쳐야 할 것 같으면 그건 Stage 분해가 틀렸다는 신호다 — 에스컬레이션하라.
- **커밋을 쪼개라.** 특히 기계적 변경(가역)과 판단 변경(비가역)은 다른 커밋으로.
  S4(티어 선언) / S6(축약)이 그 예다.
- **생성물을 손으로 고치지 마라**: `AGENTS.md` · `plugins/common/plugin.json` ·
  `.codex-plugin/plugin.json` · `CHECKSUMS.sha256` · `MIRROR.sha256`.
  각각 `export-harness.sh` · `build-targets.py` · `shasum` · `sync-rule-mirror.sh` 로 재생성한다.
- **설정값으로 경로를 만들면 봉쇄한다.** 이 레포에서 **같은 결함이 세 번** 반복됐다
  (CLAUDE.md). `pathlib` 의 `a / b` 는 `b` 가 절대경로면 `a` 를 통째로 버린다.
  규칙 4개: ①한 번만 resolve ②레포 밖이면 exit 1 ③**읽기 경로도 봉쇄** ④`--check` 에도 같은 봉쇄.
  **관례를 새로 발명하지 말고** `build-targets.py` · `export_harness.py` 의 헬퍼를 그대로 따르라.
- **Python 하한은 3.9** — 훅은 소비자의 `python3` 에서 돈다(macOS 가 3.9.x 를 배포).
  `from __future__ import annotations` 를 쓰고 3.10 전용 문법을 import 시점 평가 대상에서 뺀다.
  2.12.1 에서 훅 4종이 조용히 죽어 있었다.

### 5.3 완료 선언 전 (`definition-of-done`)

1. `03-gate-spec.md` 의 해당 G 번호를 **전부** 실행한다.
2. **되돌려-FAIL 이 있는 항목은 되돌려-FAIL 을 실제로 수행한다.**
   red 를 못 본 게이트는 없는 것과 같다 — 이 레포가 반복해서 잡아온 false-green 이다.
3. `./scripts/verify-done.sh` green.
4. **보고를 믿지 않는다는 것이 컨트롤의 규율이다** — 게이트를 직접 실행한 **출력**을 보고에 붙여라.
   "통과했습니다" 는 증거가 아니다.

### 5.4 배포물을 건드렸으면 버전을 올린다 【CRITICAL】

플러그인 캐시는 `{plugin-name}/{version}` 으로 키가 잡힌다 —
**같은 버전 = 업데이트 안 받아짐 = 사용자가 영원히 고쳐진 것을 못 본다.**

```bash
scripts/bump-version.sh <version>      # SSOT + 타겟 매니페스트 재생성이 한 번에
```
**손으로 `plugin.json` 의 version 을 고치지 마라.** v2.15.0 에서 SSOT 만 올리고 재생성을
빠뜨려 Codex·Antigravity 패키지에 옛 버전이 실릴 뻔했고, §14 가 잡았다.

**어떤 Stage 가 배포물을 건드리나**: `plugins/**` 를 만지면 전부. `02-stages.md` 부록 표의
"트랙 = C" 인 Stage 들이다. **§11.4 가 추가한 25-23·25-25·25-27 은 설계문서에 트랙 배정이
없지만 `plugins/**` 를 건드린다**(`00-REVIEW.md` L9) — C 트랙으로 다뤄라.

### 5.5 에이전트/스킬 정의를 고쳐도 **이번 세션에는 반영되지 않는다**

에이전트·스킬은 **설치된 플러그인 캐시**에서 로드된다
(`~/.claude/plugins/cache/claude-code-kit/claude-code-kit/<version>/`), 이 워크트리가 아니다.

- **"정의 변경이 먹혔다" 를 세션 내 행동으로 결론짓지 마라.** 파일을 읽거나 기계 검사로 확인한다.
- 실제로 시험하려면 버전을 올리고 재설치하거나, 스크래치 설치를 워킹 트리로 가리켜야 한다.
- 훅은 `${CLAUDE_PLUGIN_ROOT}`(역시 캐시)에서 돈다. **`scripts/` 와 `evals/` 는 레포 로컬이라
  즉시 반영된다.**

이 함정은 2.14.0 개발에서 실제로 물렸다 — `review-code` 의 출력 계약이 정의 끝에서 496행
떨어진 곳에 묻혀 있었고, 리포트가 두 번 비어서 왔으며, 워킹 트리 수정을 같은 세션에서
검증할 수 없었다.

---

## 6. 이 프로그램의 판단 기준 (모든 결정에 동일 적용)

설계문서 §0 의 셋이다. 애매할 때 여기로 돌아온다.

1. **약속과 실물의 일치** — 문서·이름·매니페스트가 주장하는 것은 실측으로 뒷받침돼야 한다.
   이 레포가 반복해서 잡아온 결함은 전부 **"켜져 있다는 착각"** 계열이다.
2. **부채 없음** — 같은 질문에 답하는 컴포넌트를 둘 두지 않는다. 생성물은 SSOT 에서 파생한다.
3. **소비자 우선** — 설치하는 사람의 환경에서 동작해야 한다. 특정 플러그인·MCP·CLI 의 존재를
   가정하지 않는다.

### 반복 인용되는 결함 클래스 두 개

- **"검사 대상이 아닌 것은 결코 red 가 되지 않는다"** — W-024 가 명명. 이 프로그램에서만
  네 번째 인스턴스다(`ALWAYS_RULES` 하드코딩 · `check_doc_counts` 목록 · `consensus-builder`
  분류 · **그리고 D-8 자신**, `00-REVIEW.md` L1).
- **"게이트로 안 되는 것을 게이트라고 부르지 않는다"** — D-32. 자연어 사실성·외부 CLI 표면·
  소비자 파일은 게이트 불가이며, 각각 다른 기전이 맡는다. 목록은 `03-gate-spec.md` §8.

---

## 7. 아직 열려 있는 것 (추측으로 채우지 마라)

### 설계가 의도적으로 열어 둔 2종 (§11.3)

| 미결 | 왜 지금 닫지 않나 | 언제 닫히나 |
| --- | --- | --- |
| **D-4 개명 이행 메커니즘** | 마켓플레이스 이름 불일치 시 설치 성립 여부가 `runtime-verified` 미달. 추측으로 문서에 쓰면 그것이 곧 판단 기준 1 위반 | **27-1 / S18** |
| **D-3 네 번째 드리프트 게이트 통합 여부** | 이름 파생의 구현 형태(사본 vs 참조)가 정해져야 판단 가능. 기준은 D-26 이 제공 | **27-3 / S20** |

### Q1~Q5 — **닫혔다** (컨트롤 답신 `msg_f79d2eeb700b`)

| # | 결정 | 영향 |
| --- | --- | --- |
| **Q1** | 게이트를 **C 트랙 · 같은 커밋 · 처음부터 fail**. 검수의 warn-first 권고 **기각** (W-024: *"영구 노란 경고는 아무도 보지 않는다"*). 25-17 만 예외 | S8·S9 퇴역 → S1·S6 에 흡수 |
| **Q2** | 예산을 **총량 하나**(`alwaysInjectedMaxBytes=9216`)로. `비신뢰 텍스트 취급` 절을 **core 규범으로 승격**(검수의 reference 이관 권고 기각 — 현저성 하락 없음). 개별 상한 필드 제거 | **S24 신설** |
| **Q3** | W-025 는 이관 + 배너까지. **전면 재작성은 W-026 으로** | **S25 신설** |
| **Q4** | 25-26 기록 대상 = `docs/conventions/rules-mirror.md` | S12b |
| **Q5** | 운송 부록은 `docs/`. **`G-D6` 결정적 게이트 채택** | S15 |

### 아직 열려 있는 것 (추측으로 채우지 마라)

| 미결 | 영향 Stage | 언제 닫히나 |
| --- | --- | --- |
| **W-026 의 버전 (2.18.0 vs 2.19.0)** | S17 | 답신이 다루지 않았다. 설계문서 §5:455 제목과 D-7 1단계를 컨트롤이 v2.19.0 으로 정정해야 한다 — 문서에 두 값이 남아 있는 한 구현 LLM 이 §5 만 읽고 2.18.0 을 쓸 수 있다 |
| `control-loop` 의 `promotionCondition` 문장 | S17 | 26-4 등재 시 작성 |
| `facilitator`·`synthesizer` 의 isolation 예외 승인 | S1 | 답신이 다루지 않았다. 승인 없으면 `[unresolved]` 로 두고 보고한다 |
| `rules/VERSION`(1.4.0) 을 올릴지 | S24 | 게이트가 강제하지 않는다. 올리지 않기로 하면 근거를 커밋 메시지에 남긴다 |
| D-22 검사 ④(도구명 허용 집합) 존치 여부 | S1 | 답신이 다루지 않았다. 확인 전에는 ①②③만 구현한다 |

**미결에 부딪히면**: 답과 무관한 부분을 먼저 끝내고, 값이 필요한 지점에서
**가정을 명시하고 물어라.** 진행 불가한 것만 블로킹 질문으로 올린다.
**추측으로 채우는 것은 금지다 — 모르면 `[unresolved]` 로 둔다.**

---

## 8. 배치 전체 지도 (한 장)

```
W-025 위생·구조 정비 ── 3 트랙, 릴리스 1회(v2.18.0)
  A 환경 (커밋 없음)   S0
  C 배포물 (v2.18.0)   S1 참조정합 + §17 ⟨같은 커밋⟩ → S3 에이전트
                       S2 스킬정리(이관 + 배너)
                       S4 티어선언(골격) → S5 삭제·중립화 → S24 untrusted-text 신설
                                                         → S6 축약 + §16 ⟨같은 커밋⟩
                       → S7 릴리스
  B 레포도구 (무변경)  S10 카운트탐지(warn-first) · S11 eval인프라 · S12 문서구조
                       ※ C 트랙 완료 후 (S10 의 탐지 대상을 C 가 바꾼다)
  ⟨퇴역⟩ S8·S9 — Q1 답신으로 각각 S6·S1 에 흡수. 번호 재사용 금지

W-026 control-loop ── v2.19.0 (설계문서 정정 대기)
  S13 하네스심(3결합점) → S14 규범본문+D-30 → S15 운송부록(docs/) + G-D6
                       ├→ S16 agent-teams 예고
                       └→ S25 work-system.md 재작성
                       → S17 등재+릴리스

W-027 이름 SSOT + v3.0.0
  S18 프로브 ┐
  S19 생성기 ┼→ S20 게이트판정 → S21 파리티문장 → S22 개명(v3.0.0) → S23 카탈로그
             └  ※ S22 는 S18·S19·S20 완료 전 착수 금지 — 외부 되돌림 불가
```

### 되돌리기 비용이 가장 큰 셋 (여기서 실수하면 못 되돌린다)

1. **S22 개명** — 마켓플레이스·카탈로그·소비자 `enabledPlugins`. 레포 커밋으로 안 되돌아간다.
2. **S0 환경 위생** — 커밋이 없어 되돌림 자산이 아예 없다. **스냅샷이 유일한 안전망**이다.
3. **S6 규범 축약** — 판단 작업이라 되돌림이 파일 복원이 아니라 판단의 재수행이고,
   배포된 뒤에는 새 릴리스 없이 되돌아가지 않는다. **미러가 원문 보존처**이고,
   **eval 전량 재실행이 유일한 실증 안전망**이다(예산 게이트는 크기만 보고 행동은 안 본다).

---

## 9. 마지막 한 줄

> **보고를 믿지 않는다. 게이트를 직접 실행한다.**
> 이것이 `control-loop` P3 의 규율이고, 이 프로그램이 만들려는 것 자체다.
> 완료 선언에는 명령의 **출력**을 붙여라.
