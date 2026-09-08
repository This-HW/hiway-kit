# 03 — 게이트 규격 (층 4): 수용 테스트 32개 → 실행 가능한 명령

> 기준 커밋 **`3f85f47`**. **규격만 적는다 — 스크립트를 실제로 작성하지 않는다**(브리프 금지 조항).
>
> 각 항목: **명령 / 통과 조건 / 되돌려-FAIL(그 검사가 실제로 red 를 내는지 증명하는 법)**.
> 명령으로 바꿀 수 없는 항목은 **그 사실과 이유를 명시**하고 대체 검증을 제시했다 —
> 자연어 사실성처럼 원리적으로 게이트 불가인 것이 실제로 있다(D-32).

## 0. 규약

### 0.1 `verify-done.sh` 섹션 번호

```
현행:  1  2  3  3b  4  5  6  7  8  9  10  11  13  14  15      (실측: grep -c '^hdr ' → 15)
비움:  12                                                      (W-022 R1 폐기 — 영구 결번)
신설:  16 (주입 예산, D-20)   17 (상호 참조 실재, D-22)
```

**§12 는 재사용하지 않는다.** 스펙·decision-log 47곳 이상이 섹션 번호로 게이트를 참조한다.
다음 신설은 §18 이다.

### 0.2 되돌려-FAIL 의 정의

*"검사를 통과하는 상태에서 **의도적으로 결함을 심어** red 를 확인하고, 되돌려 green 을 확인한다."*
red 를 못 보면 그 게이트는 **없는 것과 같다** — 이 레포가 반복해서 잡아온 false-green 이다.
아래에서 되돌려-FAIL 이 **불가능**한 항목은 그 이유를 적었다.

### 0.3 3분류 표기

- **[결정적]** — 명령의 종료 코드로 통과/실패가 갈린다. 게이트에 넣는다.
- **[비결정]** — LLM 출력에 의존한다. **고정 평가셋 + 임계값**으로 다루고, 결정적 게이트에 넣지 않는다.
- **[게이트 불가]** — 원리적으로 명령으로 판정할 수 없다. 대체 검증을 명시한다.

> **금지 행위 위반은 임계값이 아니라 0 이고 결정적 게이트다.** 비결정 시나리오라도
> `output_not_contains` 류의 금지 어구 위반은 임계값 대상이 아니다.

---

## 1. W-025 — §7 수용 테스트 1~4

### G1 — 경로 없는 projects 항목 0건 【결정적 / A 트랙】

```bash
python3 - <<'EOF'
import json, os, sys
p = os.path.expanduser("~/.claude.json")
d = json.load(open(p))
ghosts = [k for k in d.get("projects", {}) if not os.path.isdir(k)]
print(f"projects={len(d.get('projects', {}))} ghosts={len(ghosts)}")
for g in ghosts[:20]: print("  GHOST", g)
sys.exit(1 if ghosts else 0)
EOF
```

- **통과**: exit 0 (ghosts == 0).
- **되돌려-FAIL**: `projects` 에 `/nonexistent/path-xyz` 키를 하나 넣으면 exit 1,
  지우면 exit 0. **사용자 전역 설정을 만지므로 스냅샷 후 수행**하고 즉시 원복한다.
- **주의**: 이 검사는 `verify-done.sh` 에 **넣지 않는다** — 소비자의 홈 디렉토리를 읽는
  게이트는 consumer-first 위반이고, A 트랙은 레포와 무관하다. **1회성 확인 명령**이다.
- **건수 불일치**: §1.4(26건) vs D-10/25-1(28건). 착수 시 위 명령의 실측값을 기록한다.

### G2 — eval 회귀 가드가 실제로 경고를 낸다 【결정적, 되돌려-FAIL 필수】

```bash
# (a) 정상 경로
python3 evals/run.py --dry-run >/dev/null && echo "dry-run OK"
# 가드 자체의 단위 검증 (권고 구현: 델타 비교 함수를 분리해 테스트에서 직접 호출)
python3 -m pytest tests/ -k "projects_delta" -q
```

- **통과**: 델타 0 인 입력에서 경고 없음, 델타 > 0 인 입력에서 경고 문자열 출력.
- **되돌려-FAIL**: 테스트가 **인위적으로 증가시킨 before/after 쌍**을 주입해 경고를 확인한다.
  실제 `~/.claude.json` 을 오염시키지 말 것 — **델타 비교를 순수 함수로 분리**해야
  이 되돌려-FAIL 이 안전해진다. 이것이 25-2 의 구현 제약이다.
- **연계 결함**: 이 가드는 `evals/run.py` 에 `~/.claude.json` 문자열을 추가한다 →
  **G16 의 문자열 스캔 구현과 충돌**한다(`00-REVIEW.md` O8). G16 을 호출 스캔으로 쓰면 해소.

### G3 — `verify-done.sh` green 【결정적】

```bash
./scripts/verify-done.sh; echo "exit=$?"
```

- **통과**: exit 0, `기계 검사 결과: N pass / 0 fail`.
- **되돌려-FAIL**: 임의 게이트를 깨면(예: `plugin.json` 에서 `license` 제거) exit 1.
- **주의**: shellcheck 미설치 시 §3b 는 **yellow(로컬 한정)** 이고 red 가 아니다.
  CI(핀 버전)가 권위다. *"never reports green when it could not check"* — 로컬 green 을
  CI green 의 증거로 쓰지 마라.

### G4 — bypass off 상태에서 축소된 allowlist 로 일상 작업 성립 【게이트 불가】

**이 항목은 명령으로 바꿀 수 없다.** 이유:
1. **"일상 작업" 이 정의되지 않았다** — 무엇을 실행하면 성립인가.
2. **관측 기간이 없다** — 하루? 한 배치? 판정 시점이 없다.
3. **판정 주체가 없다** — 실패하면 누가 무엇을 근거로 red 를 선언하는가.
4. `permissions` 는 **사용자 전역 설정**이라 레포 게이트의 대상이 아니다.

**결과적으로 이 항목은 W-025 의 완료를 무기한 막는다** — `rules/definition-of-done.md` 가
요구하는 "게이트 통과 후 완료 선언" 형태와 맞지 않는다.

**대체 검증** (수용 테스트에서 **강등**, A 트랙 산출물로):
```bash
# 1) 제거 전후 allowlist 목록을 보고서에 기록
python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.claude/settings.json')));print('\n'.join(d.get('permissions',{}).get('allow',[])))"
# 2) bypass 를 끈 1세션의 실행 로그(권한 프롬프트 발생 지점 포함)를 보고서에 첨부
```
- **산출물 기준**: before/after 목록 + 1세션 로그. **"성립함" 이라는 판정 문장을 쓰지 않는다** —
  관측을 남기고 사용자가 판단한다.

---

## 2. W-026 — §7 수용 테스트 5~8

### G5 — `control-loop` 규범 본문에 `orca` 0건 【결정적】

```bash
! grep -qi "orca" plugins/common/skills/control-loop/SKILL.md && echo PASS || { echo FAIL; grep -ni orca plugins/common/skills/control-loop/SKILL.md; }
```

- **통과**: `PASS`.
- **원문 명령의 문제**: 설계문서 §7-5 는 `git grep -c orca …` 를 적었는데, `git grep -c` 는
  매치가 0이면 **아무것도 출력하지 않고 exit 1** 이다 — "0건" 을 확인하려는 명령이
  실패 코드로 끝난다. 위 형태로 바꾼다.
- **되돌려-FAIL**: SKILL.md 에 `orca` 한 줄을 넣으면 FAIL, 지우면 PASS.
- **【검수 R4 — 스코프 한계】** 이 검사는 **파일 하나만** 본다. 운송 부록이
  `plugins/common/skills/control-loop/` 안에 놓이면 **D-6 이 근거로 삼은
  "`plugins/` 안 orca 0건" 불변식이 깨지는데 이 게이트는 잡지 못한다.** 부록을 `docs/` 에
  두기로 하면 아래 G-D6 을 추가한다.

### G-D6 — 배포물 전체에 `orca` 0건 【결정적 · **Q5 답신으로 채택 확정**】

```bash
CNT=$(grep -ril "orca" plugins/ | wc -l | tr -d ' '); [ "$CNT" -eq 0 ] && echo PASS || { echo "FAIL: $CNT"; grep -ril orca plugins/; }
```

- **통과**: 0건 (실측 @`3f85f47` = 0 — 현재 불변식이 성립하므로 **신설 즉시 green**).
- **되돌려-FAIL**: `plugins/` 아무 파일에 `orca` 를 넣으면 FAIL, 지우면 PASS.
- **채택 확정**: Q5 답신 — 운송 부록은 `docs/` 에 두고 *"`G-D6`(배포물 전체 `orca` 0건)을
  **결정적 게이트로 채택**한다"*. 근거 셋: ① D-6 의 불변식 유지 ② 부록은 비규범이라 배포물에
  실릴 이유가 없다 ③ 소비자 대부분은 orca 를 쓰지 않으므로 배포물 크기만 늘린다.
- **왜 G5 로는 부족한가**: G5 는 `control-loop/SKILL.md` **한 파일만** 본다. 부록이
  `plugins/common/skills/control-loop/transports.md` 로 들어가면 G5 는 green 인데
  D-6 의 근거 불변식은 깨진다. G-D6 이 그 구멍을 막는다.
- **소속 Stage**: S15.

### G6 — `check_classification_complete` 경고 없이 통과 【결정적, 단 D-8 의 증거가 아님】

```bash
python3 scripts/check_eval_coverage.py; echo "exit=$?"
```

- **통과**: exit 0, 경고 라인 0.
- **되돌려-FAIL**: 새 에이전트 `.md` 를 `plugins/common/agents/dev/` 에 임시 생성하면
  미분류 경고 출력(현재 `classificationCompleteEnforceFail: false` 이므로 **warn**), 지우면 원복.
  `evals/policy.json` 의 그 플래그를 `true` 로 바꾸면 fail 까지 확인 가능.
- **⚠ 이 green 을 `control-loop` 등재의 증거로 쓰지 마라**(`00-REVIEW.md` L1).
  `_discover_all_agents`(`scripts/check_eval_coverage.py:302-309`)는
  `plugins/common/agents/**/*.md` 만 열거하고 판정은 `all_agents - covered` **단방향**이다.
  `control-loop` 은 스킬이므로 **등재하든 안 하든 이 게이트는 green 이다.**
- **등재 확인은 별도 명령**:
  ```bash
  python3 -c "import json;c=json.load(open('evals/policy.json'))['tiers']['_tier2Classification'];e=c.get('control-loop');print(e);assert e and e['grade']=='C' and e.get('promotionCondition')"
  ```
  - 통과: 등급 C + 사유 + **승격 조건 문자열이 비어 있지 않음**.
  - 되돌려-FAIL: `promotionCondition` 을 `null` 로 바꾸면 AssertionError.

### G7 — `agent-teams` 호출 시 `control-loop` 로 안내 【결정적 절반 + 비결정 절반】

**원문은 게이트 불가다** — "호출하면 안내됨" 은 LLM 행동이다. 둘로 나눈다.

**[결정적]**
```bash
grep -q "control-loop" plugins/common/skills/agent-teams/SKILL.md \
  && grep -qE "폐기|deprecat" plugins/common/skills/agent-teams/SKILL.md \
  && echo PASS || echo FAIL
```
- 통과: 폐기 예고 문구 ∧ `control-loop` 참조가 둘 다 존재.
- 되돌려-FAIL: 둘 중 하나를 지우면 FAIL.

**[비결정]** — 실제 안내 행동은 eval 시나리오로만 관측 가능하나, `agent-teams` 는 스킬이라
현행 러너(에이전트 단일 출력 채점)의 대상이 아니다. **측정하지 않고, 측정하지 않는다는
사실을 기록한다** — D-8 이 `control-loop` 에 대해 취한 것과 같은 정직한 처리.

### G8 — 문서 카운트 게이트 green (스킬 19 유지) 【결정적】

```bash
python3 scripts/check_doc_counts.py; echo "exit=$?"
```
- 통과: exit 0, `33 agents / 19 skills / **13** rules` (W-025 후).
  **주의**: 규범 수는 13 → 12 → **13** 으로 돌아온다 — D-18 이 `tool-usage-priority` 를 삭제(S5)하고
  Q2 답신이 `untrusted-text` 를 신설(S24)하기 때문이다. 설계문서 §9.4 가 전제한 "13 → 12" 는
  **중간 상태**이고 최종값이 아니다. S5 단독 커밋 시점에는 이 게이트가 red 이므로
  **S5 와 S24 는 같은 릴리스 안에** 있어야 한다.
- 되돌려-FAIL: `README.md` 의 `Skills (19)` 를 `(18)` 로 바꾸면 exit 1.

---

## 3. W-027 — §7 수용 테스트 9~12

### G9 — 프로브가 D-4 질문 3종에 `runtime-verified` 답을 남김 【결정적 형식 + 게이트 불가 내용】

**형식은 검사 가능하고 내용의 진위는 불가능하다.** 분리한다.

**[결정적 — 형식]**
```bash
F=docs/specs/2026-09-07-marketplace-probe-findings.md
test -f "$F" && for q in Q1 Q2 Q3; do grep -q "^### $q" "$F" || { echo "FAIL: $q 없음"; exit 1; }; done
grep -c "runtime-verified" "$F"   # 3 이상
grep -qE '^\$ |^```' "$F"          # 실행 로그 블록 존재
```
- 통과: 세 질문 절이 존재하고 각각 `runtime-verified` 태그 + 실행 로그 블록을 갖는다.
- 되돌려-FAIL: 한 질문 절을 지우면 exit 1.

**[게이트 불가 — 내용]**: 프로브 결과가 **사실인지**는 명령으로 판정할 수 없다. 재현 명령이
로그에 남아 있는지가 유일한 대체 검증이고, 그것이 이 레포의 `runtime-verified` 기준이다.

### G10 — `name` 만 바꾸고 생성기를 돌리면 문서·사이트가 따라옴 【결정적, 되돌려-FAIL 필수】

```bash
# 워크트리가 clean 한 상태에서
python3 scripts/build-names.py --check || echo "drift"     # 생성기 이름은 구현 시 확정
# 왕복 증명:
cp plugins/common/.claude-plugin/plugin.json /tmp/pj.bak
python3 - <<'EOF'
import json,pathlib
p=pathlib.Path("plugins/common/.claude-plugin/plugin.json"); d=json.loads(p.read_text())
d["name"]="probe-rename-xyz"; p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n")
EOF
python3 scripts/build-names.py --write
git diff --name-only | wc -l          # 0 이면 생성기가 아무것도 안 한 것 = FAIL
grep -rl "probe-rename-xyz" README.md site/ CLAUDE.md plugins/common/README.md | wc -l
# 원복
cp /tmp/pj.bak plugins/common/.claude-plugin/plugin.json && python3 scripts/build-names.py --write
git diff --quiet && echo "왕복 복원 OK" || echo "FAIL: 잔재 남음"
```

- **통과**: 이름 변경 시 대상 문서가 전부 따라오고, **되돌리면 `git diff` 가 공집합**이다.
- **되돌려-FAIL**: 생성기가 아무 파일도 바꾸지 않으면(`git diff --name-only` 가 0) FAIL —
  이것이 "생성기가 실제로 동작하는가" 의 증명이다.
- **왕복 복원 검사가 핵심**이다. 단방향만 보면 생성기가 문서를 **망가뜨리면서** 통과할 수 있다.

### G-PATH 【검수 추가 · 결정적】 — 생성기의 경로 봉쇄

CLAUDE.md: *"설정값으로 경로를 만들면 반드시 봉쇄한다"* — 같은 결함이 세 번 반복됐다.

```bash
for BAD in "/etc/passwd" "../../../tmp/escape.md" "$(mktemp -d)/symlink-out.md"; do
  python3 scripts/build-names.py --check --target "$BAD"; echo "  $BAD → exit=$?"
done
```
- **통과**: 세 케이스 전부 **exit 1**. 절대경로 · `..` · 심링크.
- **`--check` 에도 같은 봉쇄를 건다** — 2.14.1 은 쓰기에만 걸어 구멍이 남았다.
- **읽기 경로도 봉쇄한다** — `check_eval_coverage.py` 의 세 번째 인스턴스가 읽기 전용인데도
  거짓 green 을 냈다.
- 되돌려-FAIL: 봉쇄 코드를 주석 처리하면 exit 0 이 나온다(= 게이트가 살아 있다는 증명).

### G11 — 세 매니페스트의 `name` 이 SSOT 와 일치 【결정적 — 기존 §14】

```bash
python3 scripts/build-targets.py --check; echo "exit=$?"
```
- 통과: exit 0.
- 되돌려-FAIL: `plugins/common/plugin.json` 의 `name` 을 손으로 바꾸면 exit 1
  (이 게이트는 v2.15.0 릴리스에서 실제로 잡았다).

### G12 — README 파리티 문장과 매니페스트 `description` 이 "같은 약속" 【게이트 불가】

**원리적으로 게이트 불가다.** 자연어 동치는 명령으로 판정할 수 없다 —
D-32 3행이 인정한 *"자연어 사실성은 게이트 불가"* 범주에 정확히 속하는데, 수용 테스트에는
그 인정 없이 남아 있다.

**대체 검증 — 마커 문자열 동일성** (사본이 아니라 **동일 리터럴**을 강제):
```bash
PROMISE="규범과 절차(L0·L1)는 모든 하네스 공통"
grep -qF "$PROMISE" README.md \
  && python3 -c "
import json,sys
d=json.load(open('plugins/common/.claude-plugin/plugin.json'))
sys.exit(0 if '$PROMISE'[:20] in d['description'] else 1)" \
  && echo PASS || echo FAIL
```
- **통과**: 같은 문자열이 양쪽에 존재.
- **한계 명시**: 이것은 *"같은 약속을 말한다"* 가 아니라 *"같은 문장을 담는다"* 를 검사한다.
  의미 동치는 사람이 판단한다. **이 한계를 게이트 코드 주석에 적는다** — 적지 않으면
  green 이 의미 동치를 보증한다는 오해가 남는다(D-32 3행의 미러 체크섬과 같은 함정).

---

## 4. §8.4 수용 테스트 13~17 — 구조 감사

### G13-a — 어서션 타입 추가 시 한 곳만 고치면 반영 【결정적, 실증형】

```bash
# 레지스트리 통합 후: 표에 임시 타입을 1줄 추가하고 스키마 검증 + 채점이 둘 다 인식하는지
python3 -m pytest tests/ -k "assertion_registry" -q
python3 evals/run.py --validate; echo "exit=$?"
```
- **통과**: 레지스트리에 1줄 추가 → `--validate` 가 그 타입을 수용 ∧ 채점 디스패치가 인식.
- **되돌려-FAIL**: 레지스트리에서 한 타입을 지우면 그 타입을 쓰는 시나리오의 `--validate` 가 exit 1.
- **구현 제약**: `KNOWN_ASSERTION_TYPES` 와 `check_assertion` 이 **같은 표를 읽어야** 한다.
  §11.2(a)가 "동기화 테스트가 아니라 레지스트리" 로 확정했다.

### G14 — `spec_from_file_location` 이 레포에 1곳만 【결정적】

```bash
CNT=$(grep -rn "spec_from_file_location" --include="*.py" . | grep -v "^./.venv" | wc -l | tr -d ' ')
[ "$CNT" -eq 1 ] && echo PASS || { echo "FAIL: $CNT"; grep -rn spec_from_file_location --include="*.py" . | grep -v "^./.venv"; }
```
- 통과: 정확히 1(헬퍼 `load_module_by_path` 안).
- 되돌려-FAIL: 아무 테스트에 보일러플레이트를 복원하면 2가 되어 FAIL.
- **주의**: `.venv` 제외를 빠뜨리면 서드파티 코드가 잡혀 영구 red 다.

### G15 — 경로 헬퍼 4벌이 동일 적대 케이스 표를 통과하고 이름이 통일 【결정적】

```bash
# 이름 통일
grep -rn "_safe_join\|_resolve_target" --include="*.py" . | grep -v "^./.venv" | wc -l   # 0 이어야 함
grep -rln "_resolve_in_repo" --include="*.py" . | grep -v "^./.venv" | wc -l             # 4 이어야 함
# 공유 케이스 표
python3 -m pytest tests/ -k "path_containment" -q
```
- 통과: 옛 이름 0건 · 새 이름 4파일 · 공유 표 테스트 green.
- **되돌려-FAIL**: 케이스 표에서 심링크 케이스를 지우고 한 헬퍼의 심링크 방어를 제거하면
  **테스트가 여전히 green** 이 된다 → 이것이 "표가 계약" 이라는 설계의 증명이자,
  **표를 지우는 것이 곧 방어를 지우는 것**임을 보여준다. 표 항목 삭제를 금지하는 것은
  `test-ratchet`(§9)의 몫이다.
- 케이스 표에는 최소 4종: 절대경로 · `..` · 심링크 · TOCTOU(검사와 사용이 각각 resolve).

### G16 — `run.py` 의 하네스 결합이 `ClaudeCodeHarness` 안에만 【결정적 — 원문 재작성 필요】

**원문(`"claude"` 리터럴 스캔)은 통과 불가능하다.** 실측 `grep -c claude evals/run.py` = 14 이고,
그중 `"type": "claude_exit"`(1196) · `description="claude-code-kit agent evals runner"`(1376)
같은 무관한 문자열이 있으며, 25-2 의 회귀 가드가 `~/.claude.json` 을 추가한다.

**재작성 — 호출 스캔**:
```bash
python3 - <<'EOF'
import ast, sys, pathlib
src = pathlib.Path("evals/run.py").read_text()
tree = ast.parse(src)
# ClaudeCodeHarness 클래스의 라인 범위
rng = None
for n in ast.walk(tree):
    if isinstance(n, ast.ClassDef) and n.name == "ClaudeCodeHarness":
        rng = (n.lineno, n.end_lineno)
assert rng, "ClaudeCodeHarness 없음"
bad = []
for n in ast.walk(tree):
    hit = False
    # subprocess.run([...,"claude",...]) / shutil.which("claude")
    if isinstance(n, ast.Call):
        for c in ast.walk(n):
            if isinstance(c, ast.Constant) and c.value == "claude":
                hit = True
    if hit and not (rng[0] <= n.lineno <= rng[1]):
        bad.append(n.lineno)
if bad:
    print("FAIL: ClaudeCodeHarness 밖의 claude CLI 호출:", sorted(set(bad))); sys.exit(1)
print("PASS")
EOF
```
- **통과**: `claude` 를 **인자로 갖는 호출**이 `ClaudeCodeHarness` 클래스 범위 밖에 0건.
- **현재 위반 3곳**(실측 @`3f85f47`): `1049`(LLM judge) · `1077`(build_claude_command) ·
  `1304`(`shutil.which`). **D-12 는 1077 하나만 안다**(`00-REVIEW.md` L2).
- **되돌려-FAIL**: 클래스 밖에 `shutil.which("claude")` 한 줄을 넣으면 FAIL.

### G16-b 【검수 추가 · 결정적】 — 심 추출이 동작을 바꾸지 않았음의 증명

```bash
git stash list >/dev/null   # (bare stash 금지 — WIP 커밋으로 세워 둘 것)
# 추출 전 커밋에서
python3 evals/run.py --dry-run > /tmp/before.txt
# 추출 후 커밋에서
python3 evals/run.py --dry-run > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt && echo "PASS: 조립 명령 동일" || echo "FAIL"
```
- **통과**: diff 가 공집합. `evals/run.py:1383` 이 `--dry-run` 을 이미 지원한다.
- **이것이 S13 의 유일한 실증 안전망이다** — 심이 명령을 미세하게 바꾸면 eval 결과가 조용히
  달라지고 기준선이 신뢰 불가가 된다.

### G17 — README 파리티 문장이 "행동 eval 은 Claude Code 만 구동" 명시 【결정적】

```bash
grep -qE "행동 eval.*Claude Code|behavior eval.*Claude Code" README.md && echo PASS || echo FAIL
```
- 통과: 문장 존재.
- 되돌려-FAIL: 그 줄을 지우면 FAIL.
- **함께 검사할 한계 4종**(`01-policy.json` `parityContract.requiredDisclosures`) —
  네 번째(비-CC 하네스의 L0 는 `/harness-export` opt-in)는 검수가 추가한 항목이다:
  ```bash
  for P in "행동 eval" "harness-export" "에이전트·훅은" "1회 실측 검증"; do
    grep -qF "$P" README.md || echo "MISSING: $P"
  done
  ```

---

## 5. §9.5 수용 테스트 18~21 — 주입 예산

### G18 — 주입 총량이 예산 안이고, 넘기면 §16 이 red 【결정적, 되돌려-FAIL 필수】

> **Q2 답신으로 형태가 바뀌었다.** 예산은 **총량 하나**(`alwaysInjectedMaxBytes = 9216`)이고
> core/WORKFLOW 개별 상한은 **제거**됐다. 이유: 절이 파일 사이를 옮겨다니면 개별 상한은
> **이동만으로 통과시킬 수 있다**(게이밍). 총량 하나면 그게 불가능하다.
> 검수가 제안한 `perRuleMaxBytes`(X1)도 같은 이유로 기각됐다.

```bash
python3 - <<'EOF'
import importlib.util, json, sys
from pathlib import Path
s = importlib.util.spec_from_file_location("ss", "plugins/common/hooks/session-start.py")
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
root = Path("plugins/common")
# core 티어만. conditional 은 신호가 있을 때만 주입되므로 총량에 넣지 않는다.
total = len(m.load_rules(root, include_task_resume=False).encode()) \
      + len(m.load_workflow_skill(root).encode())
pol = json.load(open("evals/policy.json"))          # 또는 예산 전용 정책 파일
cap = pol["injection"]["alwaysInjectedMaxBytes"]
print(f"alwaysInjected={total}/{cap}")
sys.exit(0 if total <= cap else 1)
EOF
```

- **통과**: 총량 ≤ 9,216 B.
- **측정 정의**(34,062 B 기준선과 같아야 사과-대-사과다): 섹션 래퍼(`=== RULES ===` 등)와
  규범 간 `\n---\n` 구분자를 **포함**한다. `conditional` 티어는 제외.
- **현재 실측(축약 전)**: **34,062 B** = 예산의 **370%**. 게이트를 지금 켜면 red 다 —
  S4·S5·S24·S6 이 선행이며, **Q1 답신에 따라 §16 은 S6 과 같은 커밋**이라 중간 red 가 없다.
- **되돌려-FAIL**: core 규범 하나에 더미 텍스트 2KB 를 붙이면 red, 지우면 green.
- **예산 수치를 셸에 하드코딩하지 마라** — 데이터에서 읽는다(`evals/policy.json` 의
  `_comment`: *"산문에 티어 목록이나 숫자를 중복 기재하지 말 것"*).
- **수용 테스트 18 의 문구는 이제 정확하다**. 구 설계(core+WORKFLOW 분리)에서는
  "총량"이라는 표현이 부정확했으나, Q2 가 예산을 실제로 총량 하나로 바꿨다.
  다만 `conditional` 이 켜진 세션의 실측 총량은 이보다 크다는 점은 여전하다 —
  게이트가 보는 것은 **always-injected** 부분이다.

### G18-b 【검수 추가 · 결정적】 — 예산 배분 실측 기록

축약 목표를 세울 때 쓸 수치. **게이트가 아니라 Stage 완료 조건의 기록 항목**이다.

```bash
python3 - <<'EOF'
from pathlib import Path
core6 = ["definition-of-done","loop-engineering","planning-protocol",
         "code-quality","planning-check","ssot"]
s = sum(len(Path(f"plugins/common/rules/{c}.md").read_bytes()) for c in core6)
ut = Path("plugins/common/rules/untrusted-text.md")
print(f"core6={s}  untrusted={len(ut.read_bytes()) if ut.exists() else 'N/A'}")
print(f"→ core6 여유 = 9216 - untrusted - (WORKFLOW+38) - 62")
EOF
```

- **예상 배분**: `untrusted-text` 2,152 + WORKFLOW(1,107+38) + core 래퍼·구분자 62
  → **core 6종 여유 = 5,857 B** (현재 13,282 의 **44.1%**).
- **컨트롤 스케치(6,144 B)보다 287 B 타이트하다.** 총량 상한이라 배분은 유연하지만,
  다른 항목을 줄이지 않는 한 이 값이 실질 여유다.

### G-UT 【검수 추가 · 결정적】 — 비신뢰 텍스트 절의 core 규범 승격 (Q2)

```bash
# 절이 SKILL.md 에서 빠지고 규범 파일로 존재하는가
! grep -q "비신뢰 텍스트 취급" plugins/common/skills/using-claude-code-kit/SKILL.md \
  && test -f plugins/common/rules/untrusted-text.md \
  && grep -qE "^tier:\s*core" plugins/common/rules/untrusted-text.md \
  && echo PASS || echo FAIL

# 【중요】 분류표 등재 — 빠뜨리면 export 가 raise 하고 §11 이 red 다
grep -q '"untrusted-text"' plugins/common/hooks/export_harness.py \
  && echo "PORTABLE 등재 OK" || echo "FAIL: export_harness 분류표 미등재"
./scripts/export-harness.sh --check
```

- **통과**: 절 이동 + `tier: core` + `PORTABLE` 등재 + `--check` green.
- **되돌려-FAIL**: `PORTABLE` 에서 `untrusted-text` 를 빼면 `export-harness.sh --check` 가
  `ClassificationError: 이식 가능성 미분류 룰` 로 실패한다(`export_harness.py:497-503`).
- **왜 이 검사가 필요한가**: `export_harness.py` 는 **양방향으로 실패한다** —
  미분류(`unknown`)와 유령(`ghost`) 둘 다 raise 한다. Q2 의 규범 신설과 D-18 의 규범 삭제가
  **양쪽 실패 조건을 하나씩 건드린다.** 설계문서 §9.4 의 연쇄 영향 목록에 이 파일이 없다.

### G-GHOST 【검수 추가 · 결정적】 — 삭제된 규범의 분류표 잔재 (D-18)

```bash
! grep -q "tool-usage-priority" plugins/common/hooks/export_harness.py \
  && echo PASS || { echo "FAIL: PORTABLE 에 유령 엔트리"; }
./scripts/export-harness.sh --check
```

- **통과**: 분류표에서 제거됨 + `--check` green.
- **되돌려-FAIL**: `PORTABLE` 에 `"tool-usage-priority"` 를 되살리면
  `ClassificationError: 분류표에만 있고 실물이 없는 룰` 로 실패한다(`export_harness.py:504-510`).
- 에러 메시지 자신이 처방을 말한다: *"삭제·개명된 룰이다. PORTABLE / NOT_PORTABLE에서 제거하라.
  (두면 소비자 AGENTS.md가 존재하지 않는 룰을 영구히 광고한다)"*

### G19 — `tier` 선언 누락 시 fail 【결정적, 되돌려-FAIL 필수】

```bash
python3 - <<'EOF'
import sys, re
from pathlib import Path
bad = []
for p in sorted(Path("plugins/common/rules").glob("*.md")):
    txt = p.read_text()
    if not txt.startswith("---"): bad.append((p.name, "frontmatter 없음")); continue
    end = txt.find("---", 3); fm = txt[3:end]
    m = re.search(r"^tier:\s*(core|conditional|reference)\s*$", fm, re.M)
    if not m: bad.append((p.name, "tier 선언 없음/부정")); continue
    if m.group(1) == "conditional" and not re.search(r"^activates:\s*\S", fm, re.M):
        bad.append((p.name, "conditional 인데 activates 비어 있음"))
for b in bad: print("  FAIL", *b)
sys.exit(1 if bad else 0)
EOF
```
- **통과**: exit 0.
- **되돌려-FAIL**: 규범 하나에서 `tier:` 줄을 지우면 exit 1, 복원하면 0.
  새 규범 파일을 추가하고 `tier` 를 빼도 exit 1 — **이것이 §9.3 결함 1(14번째 규범이 조용히
  주입되지 않음)의 봉쇄 증명이다.**

### G20 — 규범 파일만 보고 언제 주입되는지 안다 【게이트 불가 → G19 로 대체】

**"사람이 알 수 있다" 는 명령으로 판정 불가**다. G19 가 **필요조건 전부**를 검사한다:
`tier` 선언 존재 ∧ `conditional` 이면 `activates` 가 비어 있지 않음.
**충분조건(그 서술이 실제로 이해 가능한가)은 검사하지 않으며, 그 사실을 명시한다.**

### G21 — `conditional` 규범의 조건부 주입 실증 【결정적】

```bash
python3 - <<'EOF'
import importlib.util, sys
from pathlib import Path
s = importlib.util.spec_from_file_location("ss","plugins/common/hooks/session-start.py")
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
root = Path("plugins/common")
off = m.load_rules(root, include_task_resume=False)
on  = m.load_rules(root, include_task_resume=True)
assert "task-resume" not in off or len(on.encode()) > len(off.encode()), "조건부 주입 미동작"
print(f"off={len(off.encode())}  on={len(on.encode())}  delta={len(on.encode())-len(off.encode())}")
sys.exit(0)
EOF
```
- **통과**: 신호 off 에서 conditional 본문 부재, on 에서 존재(바이트 델타 > 0).
- **되돌려-FAIL**: 훅에서 조건 분기를 제거하면 두 값이 같아져 assert 실패.
- **D-17 후 확장**: `feedback-loop` · `parallel-worktree` · `mcp-usage` 도 같은 방식으로
  각각의 신호에 대해 검사한다(현재 `task-resume` 만 조건부다).

---

## 6. §10.5 수용 테스트 22~27 — 전수 감사 반영

### G22 — §17 이 존재하지 않는 참조에 red 【결정적, 되돌려-FAIL 필수 — 검사 3종 각각】

```bash
./scripts/verify-done.sh 2>&1 | sed -n '/^== 17\./,/^== /p'
```

**되돌려-FAIL 을 세 번 한다** (검사 ①②③ 각각에 대해):

| 검사 | 심는 결함 | 기대 |
| --- | --- | --- |
| ① references 실재 | 아무 에이전트 frontmatter 에 `references:\n  - ../nope.md` 추가 | red |
| ② 에이전트명 실재 | 아무 에이전트 산문에 `→ design-database 로 위임` 추가 | red |
| ③ 스킬 경로 실재 | 아무 SKILL.md 에 `참고: docs/does-not-exist.md` 추가 | red |

**스탠드얼론 실행(§17 신설 전, S1 의 완료 조건 G17-1)**:
```bash
python3 - <<'EOF'
import re, sys, pathlib
bad=[]
for p in pathlib.Path("plugins/common/agents").rglob("*.md"):
    t=p.read_text()
    if not t.startswith("---"): continue
    fm=t[3:t.find("---",3)]
    m=re.search(r"^references:\s*\n((?:\s+-\s+.*\n)+)", fm, re.M)
    if not m: continue
    for line in m.group(1).strip().splitlines():
        rel=line.strip().lstrip("- ").strip()
        rel=rel[5:].strip() if rel.startswith("path:") else rel   # 두 형태 모두 파싱
        if not (p.parent/rel).resolve().exists(): bad.append((str(p), rel))
for b in bad: print("  MISSING", *b)
sys.exit(1 if bad else 0)
EOF
```
- **현재 실측 @`3f85f47`: MISSING 10경로 / 8파일** — dev 3종 + **meta 5종**.
  D-22 증거표는 dev 3종만 안다(`00-REVIEW.md` E3).
- **`references:` 는 두 문법이다**: 문자열 리스트(meta) / `path:` 매핑(dev). 둘 다 파싱해야 한다.

### G23 — 카운트 주장이 목록 수정 없이 검사 대상에 포함 【결정적, 되돌려-FAIL 필수】

```bash
# (a) 기전 검증 — 새 파일에 주장을 넣으면 자동 탐지되는가
echo '이 킷은 99개 스킬을 제공한다.' > site/content/probe-count.md
python3 scripts/check_doc_counts.py; echo "exit=$? (1 이어야 함)"
rm site/content/probe-count.md
python3 scripts/check_doc_counts.py; echo "exit=$? (0 이어야 함)"
```
- **통과**: 목록을 손대지 않았는데 새 파일의 주장이 탐지돼 exit 1, 지우면 exit 0.
- **되돌려-FAIL 이 곧 통과 조건**이다 — 탐지되지 않으면(exit 0) 기전이 없는 것이다.

### G23-b 【검수 추가 · **warn-first**】 — 탐지 결과 미검사 주장 0건

> **Q1 답신의 유일한 예외.** §16·§17 은 처음부터 fail 이지만 이 검사만
> `enforceFail=false` + **승격 조건 명시**로 간다 — 제외 경로 규칙의 정확도가 미지수이기
> 때문이다(E8). 조건 없는 warn 은 컨트롤이 기각한 "영구 노란 경고" 자체이므로,
> 플래그와 조건을 **함께** 넣어야 한다.
>
> **승격 조건**: 제외 경로 규칙이 한 릴리스 동안 동결 기록에 대한 오탐 0건으로 관측되면
> `enforceFail` 을 `true` 로 올린다. 코드 변경 불필요 — 데이터 플래그만
> (`classificationCompleteEnforceFail` 관례).

```bash
python3 scripts/check_doc_counts.py --report-unchecked; echo "exit=$?"
```
- **통과**: 미검사 주장 0건. warn 단계에서는 exit 0 이되 경고가 **매 실행 출력**된다.
- **현재 실측 최소 8곳**(`01-policy.json` `gates.countClaimDetection.knownStaleClaims`):
  `site/content/_index.md:18,19,20` · `_index.en.md:19,21` · `about.md:38` · `about.en.md:40` ·
  `docs/conventions/rules-mirror.md:1-3`.
- **스코프 규칙 검증**(검수 E8 — 동결 기록이 red 가 되지 않는지):
  ```bash
  python3 scripts/check_doc_counts.py --report-unchecked | grep -c "site/content/posts/"   # 0
  python3 scripts/check_doc_counts.py --report-unchecked | grep -c "docs/specs/"           # 0
  python3 scripts/check_doc_counts.py --report-unchecked | grep -c "CHANGELOG"             # 0
  ```
  - `site/content/posts/2026-07-03-auditing-your-own-gates.md:20` 의 "169개 유닛 테스트"
    (현재 455)가 red 를 내면 **스코프 규칙이 잘못된 것**이다. 제외는 **파일 목록이 아니라
    경로 규칙**이어야 한다 — 목록으로 만들면 D-23 이 금지한 열거로 회귀한다.

### G24 — `skills/references/` 잔존 파일이 전부 참조됨 【결정적】

```bash
python3 - <<'EOF'
import subprocess, sys, pathlib
d = pathlib.Path("plugins/common/skills/references")
if not d.is_dir(): print("PASS: 디렉토리 없음"); sys.exit(0)
bad=[]
for f in d.glob("*.md"):
    r = subprocess.run(["grep","-rl",f"references/{f.name}","plugins/common/skills",
                        "plugins/common/agents"], capture_output=True, text=True)
    hits=[l for l in r.stdout.splitlines() if not l.endswith(f"references/{f.name}")]
    if not hits: bad.append(f.name)
for b in bad: print("  ORPHAN", b)
sys.exit(1 if bad else 0)
EOF
```
- 통과: 잔존 파일 전부 실참조 있음(현재 실측: 10종 중 8종이 ORPHAN).
- 되돌려-FAIL: `available-tools.md` 를 복원하면 ORPHAN 으로 잡힌다.
- **참조하는 쪽의 경로가 실제로 해석되는지도 봐야 한다** — 메타 5종의
  `skills/common/...` 처럼 "참조는 있는데 경로가 깨진" 경우를 `grep -rl` 만으로는 못 잡는다.
  **G22 의 ① 검사와 함께 돌려야 완전하다.**

### G25 — CLAUDE.md 에 `docs/conventions/` 와 중복 선언된 절 0개 【결정적】

```bash
test "$(grep -c '@docs/conventions' CLAUDE.md)" -ge 6 || echo "FAIL: import 6개 미만"
for f in path-containment no-gate-integration lint-single-ruleset rules-mirror shell-lint release-process reference-vs-judgment; do
  grep -q "@docs/conventions/$f.md" CLAUDE.md || echo "MISSING import: $f"
done
# 손 복제 잔재 탐지 — conventions 본문의 특징 문장이 CLAUDE.md 에 그대로 있으면 중복
python3 - <<'EOF'
import pathlib, sys
c = pathlib.Path("CLAUDE.md").read_text()
dup=[]
for f in pathlib.Path("docs/conventions").glob("*.md"):
    lines=[l.strip() for l in f.read_text().splitlines() if len(l.strip())>60]
    if any(l in c for l in lines[:10]): dup.append(f.name)
for d in dup: print("  DUP", d)
sys.exit(1 if dup else 0)
EOF
```
- 통과: import 7개 존재 ∧ 손 복제 잔재 0.
- 현재 실측: `grep -c "@docs/conventions" CLAUDE.md` → **0** (설계와 실물이 다르다, T1 F7).
- 되돌려-FAIL: `docs/conventions/shell-lint.md` 본문 한 문단을 CLAUDE.md 에 붙여넣으면 DUP.

### G26 — 기준 커밋 고정·검증이 P3 **규범 본문**에 있음 【결정적】

```bash
S=plugins/common/skills/control-loop/SKILL.md
grep -qE "기준 (커밋|ref).*해시|rev-parse HEAD" "$S" \
  && grep -qE "에스컬레이션|escalat" "$S" \
  && grep -qE "브랜치 이름.*기준으로 쓰지" "$S" \
  && echo PASS || echo FAIL
# 부록이 아니라 본문인지: 부록 파일에는 없어야 한다(있어도 무해하나 본문에 반드시)
```
- 통과: 세 요소(해시 명시 · 워커 검증 후 에스컬레이션 · 브랜치명 금지)가 **SKILL.md** 에 존재.
- 되돌려-FAIL: 한 줄을 부록으로 옮기면 FAIL.
- **이 규격의 근거**: 이 검수 세션의 브리프 §0 이 D-30 의 첫 적용 사례이고, 실제로
  `git rev-parse HEAD` 확인이 착수 첫 행동이었다.

### G26-b 【검수 추가】 — 미러 사실성 스윕의 범위 한정 【결정적 부분 + 게이트 불가 부분】

**[결정적]** — 기계 확인 가능한 주장만:
```bash
grep -rn "3-Tier Architecture\|plugins/frontend\|plugins/infra\|plugins/ops\|plugins/data\|plugins/integration" docs/architecture/ | wc -l   # 0
python3 scripts/check_doc_counts.py     # 미러의 카운트 주장도 스코프에 포함 후
```
- 대표 대상: `docs/architecture/rules/agent-system.md:7-29` — v2.7.0(`284c801`)에 삭제된
  5개 도메인 플러그인을 현재형으로 서술하고 스킬 수를 "16"(실제 19)이라 적는다.

**[게이트 불가]** — 자연어 사실성 전반. D-32 3행이 인정한 범주다.
**대체 검증**: `docs/conventions/rules-mirror.md` 에 *"체크섬은 형식 동기화이지 내용의 사실
정확성이 아니다"* 를 **명문화**한다(문장 존재 검사만 가능):
```bash
grep -qE "사실 정확성|factual accuracy" docs/conventions/rules-mirror.md && echo PASS || echo FAIL
```

### G27 — `isolation: worktree` 규약 위반 【결정적 — 원문 재작성 필요】

**원문("33종 중 위반 0건")은 현행 트리에서 4건에 걸린다**(`00-REVIEW.md` L10).
D-28 은 2건만 안다.

```bash
python3 - <<'EOF'
import pathlib, re, sys
EXEMPT = {"facilitator", "synthesizer"}   # ← 예외는 사유와 함께 rules/ 에 기록돼야 한다
bad=[]
for p in sorted(pathlib.Path("plugins/common/agents").rglob("*.md")):
    t=p.read_text(); fm=t[3:t.find("---",3)]
    m=re.search(r"tools:\s*\n((?:\s+-\s+.*\n)+)", fm)
    tools = m.group(1) if m else fm
    mutating = any(x in tools for x in ("Write","Edit","NotebookEdit"))
    isolated = re.search(r"^isolation:\s*worktree", fm, re.M) is not None
    if mutating and not isolated and p.stem not in EXEMPT: bad.append(("MUT_NO_ISO", p.stem))
    if isolated and not mutating: bad.append(("ISO_NO_MUT", p.stem))
for b in bad: print("  ", *b)
sys.exit(1 if bad else 0)
EOF
```
- **통과**: 예외 목록 밖의 위반 0건.
- **현재 실측 @`3f85f47`**: `facilitator` · `synthesizer` · `define-business-logic` ·
  `design-user-journey` 4건.
- **예외 근거**: `facilitator`/`synthesizer` 는 중간 산출물을 메인 세션이 즉시 읽어야 하므로
  격리하면 다관점 리뷰 루프가 끊긴다. **예외는 코드에만 두지 말고
  `rules/parallel-worktree.md` 에 사유 1줄로 기록**한다 — 근거 없는 예외는 다음 감사에서
  다시 결함으로 보고된다(이번 T2 가 그렇게 보고했다).
- 되돌려-FAIL: `dev/fix-bugs.md` 의 `isolation:` 줄을 지우면 exit 1.

### G-D27 【검수 추가 · 결정적】 — worktree 프로토콜 축약 확인

```bash
CNT=$(grep -rl "검증 그린일 때만" plugins/common/agents/ | wc -l | tr -d ' ')
PTR=$(grep -rl "rules/parallel-worktree.md" plugins/common/agents/ | wc -l | tr -d ' ')
echo "4줄 프로토콜 잔존=$CNT (0 이어야 함) / 포인터=$PTR (8 이어야 함)"
[ "$CNT" -eq 0 ] && [ "$PTR" -eq 8 ]
```
- 현재 실측: 프로토콜 8건 · 포인터 8건(둘 다 존재 — 축약 전).
- 되돌려-FAIL: 4줄을 한 파일에 복원하면 CNT=1.

---

## 7. §11.4 수용 테스트 28~32

### G28 — 스킬 디렉토리 최상위 진입 == SKILL.md 보유 스킬 수 【결정적】

```bash
TOP=$(ls plugins/common/skills | wc -l | tr -d ' ')
SK=$(find plugins/common/skills -maxdepth 2 -iname SKILL.md | wc -l | tr -d ' ')
echo "top=$TOP skills=$SK"; [ "$TOP" -eq "$SK" ]
```
- **현재 실측**: top=21 · skills=19 → FAIL(정상 — 아직 정리 전).
- **D-31 후 예상**: `README.md` 삭제 + `references/` 8종 삭제 → **top=20** (references/ 디렉토리가
  잔존 2종 때문에 남는다) → **여전히 FAIL**(`00-REVIEW.md` L5).
  통과하려면 `task-tools-fallback.md`·`work-system.md` 를 `references/` 밖으로 **이관**해야 한다.
- 되돌려-FAIL: 정리 후 `skills/` 에 아무 `.md` 를 놓으면 다시 FAIL.
- **연계**: 이 게이트가 green 이 되기 전에는 `packaging/targets.json` 의 `_skillsCountNote` 를
  "해소됨" 으로 갱신하지 마라 — 실측 기록 필드에 실측되지 않은 주장을 넣는 것이 된다.

### G29 — `agent-creator` 템플릿 생성물이 frontmatter 검사 통과 【결정적, 되돌려-FAIL 필수】

```bash
# 전제: verify-done §2 의 검사 본문을 scripts/check_agent_frontmatter.py 로 추출했을 때
python3 scripts/check_agent_frontmatter.py tests/fixtures/agent-creator-template/
```
- **통과**: exit 0.
- **되돌려-FAIL**: 픽스처 템플릿에 `permissionMode: default` 를 넣으면 exit 1(금지 필드),
  `maxTurns` 를 빼면 exit 1(필수 필드).
- **【검수 L7 — 구현 제약】** D-32 1행의 *"기존 frontmatter 검사(§2)를 **그대로 돌린다**"* 는
  불가능하다. §2 는 인라인 heredoc 이고 경로가 `pathlib.Path("plugins")` 로 하드코딩돼 있으며
  `/skills/` 를 **명시적으로 건너뛴다**(`scripts/verify-done.sh:60-79`).
  **추출이 선행 조건이다.** 추출 후 `verify-done §2` · CI · 픽스처 테스트 셋이 같은 스크립트를
  호출한다 — `scripts/lint-shell.sh` 가 게이트와 CI 에 공유되는 것과 같은 관례.
- **픽스처를 `plugins/**` 아래 두지 마라** — 가짜 에이전트가 소비자에게 배포되고
  에이전트 수 33 이 34가 되어 `check_doc_counts.py` 가 red 다.

### G30 — `mcp-builder` 에 하드코딩된 CLI 사용법 0건 【결정적】

```bash
grep -nE "claude mcp (restart|status|add|get|list|remove|serve|login|logout)" \
  plugins/common/skills/mcp-builder/SKILL.md | grep -v -- "--help"
[ $? -ne 0 ] && echo PASS || echo FAIL
```
- **통과**: `claude mcp --help` 외의 하위 명령 인용 0건.
- **현재 실측**: `:134` `claude mcp restart` · `:223` `claude mcp status myproject` —
  둘 다 실존하지 않는다(`claude mcp --help` 실측: add · add-from-claude-desktop · add-json ·
  get · help · list · login · logout · remove · reset-project-choices · serve).
- **되돌려-FAIL**: `claude mcp get X` 를 다시 넣으면 FAIL — **실존하는 명령이어도 FAIL 이다.**
  처방은 "틀린 명령을 맞는 명령으로 고치기" 가 아니라 **"인용하지 않기"** 다(D-32 2행:
  *"복제하지 않으면 낡을 수 없다"*).

### G31 — `enforce-structure` 가 crash 없이 스킵을 보고 【결정적 절반 + 비결정 절반】

**원문은 게이트 불가다** — `enforce-structure` 는 LLM 에이전트이지 스크립트가 아니다. 둘로 나눈다.

**G31-a [결정적]** — 정의 파일에 폴백 서술이 존재하고 필수 입력 서술이 없다:
```bash
A=plugins/common/agents/dev/enforce-structure.md
grep -qE "없으면.*(건너|스킵|보고)" "$A" \
  && ! grep -qE "반드시 읽기|필수 입력" "$A" \
  && ! grep -q "governance-check.py" "$A" \
  && echo PASS || echo FAIL
```
- 되돌려-FAIL: `"참조 파일(반드시 읽기): project-structure.yaml"` 을 복원하면 FAIL.

**G31-b [비결정]** — 실제 행동은 eval 시나리오로 측정한다:
```bash
# 기존 시나리오 evals/scenarios/enforce-structure/misplaced-source/ 는 fixture 에
# project-structure.yaml 을 포함한다(T4 #17 실측). 파일이 없는 변형 시나리오를 신설한다.
python3 evals/run.py --agent enforce-structure --scenario no-structure-file
```
- **임계값 방식**: 고정 평가셋 1건. 통과 기준은 `output_contains_any` 로
  "스킵/건너뜀/없음" 류 판정어 존재.
- **금지 행위는 임계값이 아니라 0**: 존재하지 않는 파일을 "읽었다"고 주장하는 출력은
  `output_not_contains` 로 **결정적 fail** 처리한다.
- **주의**: `output_not_contains` 는 이 레포에서 **세 번 거짓양성**을 냈다(W-023).
  일반 어구가 아니라 **판정 형태의 값**만 넣는다.

### G32 — 버전 배정이 CHANGELOG 와 일치 【결정적】

```bash
python3 - <<'EOF'
import json, re, sys, pathlib
v = json.load(open("plugins/common/.claude-plugin/plugin.json"))["version"]
top = re.search(r"^## \[([0-9.]+)\]", pathlib.Path("CHANGELOG.md").read_text(), re.M).group(1)
print(f"plugin.json={v}  CHANGELOG top={top}")
sys.exit(0 if v == top else 1)
EOF
git tag --list 'v*' | sort -V | tail -5
```
- **통과**: 두 값 일치. 그리고 과거 릴리스마다 태그 존재(`verify-done.sh §6` 이 이미 검사 —
  20개 릴리스가 태그 없이 나간 사고 이후 기계 검사가 됐다).
- **되돌려-FAIL**: `plugin.json` 의 버전만 올리면 exit 1.
- **【검수 L3 — 이 게이트가 잡지 못하는 것】** 수용 32 는 *"W-025 C=2.18.0 / W-026=2.19.0 /
  W-027=3.0.0"* 을 요구하는데, 설계문서 자신이 W-026 을 **두 값**으로 말한다
  (§5:455 제목·D-7 = 2.18.0, §11.2(f)·수용32 = 2.19.0).
  이 게이트는 "plugin.json 과 CHANGELOG 가 같은가" 만 보므로 **잘못된 값으로 일치해도 green** 이다.
  **설계문서 정정이 선행돼야 한다** — 게이트로 막을 수 없는 종류의 결함이다.

---

## 8. 게이트로 만들 수 없는 것 — 명시적 목록

> D-32 의 규율(*"게이트로 안 되는 것을 게이트라고 부르지 않는다"*)을 그대로 적용한다.
> 아래는 **원리적으로 명령 판정이 불가능**하며, 각각 대체 기전이 배정돼 있다.

| # | 항목 | 왜 불가 | 대체 기전 |
| --- | --- | --- | --- |
| 1 | **수용 4** — bypass off 일상 작업 성립 | 대상·기간·판정 주체 미정의. 사용자 전역 설정 | 산출물 기록(before/after 목록 + 1세션 로그). **수용 테스트에서 강등** |
| 2 | **수용 12** — 두 문장이 "같은 약속" | 자연어 동치 | 마커 문자열 동일성(G12) + 한계를 코드 주석에 명시 |
| 3 | **수용 20** — frontmatter 만 보고 이해 가능 | 사람의 이해도 | G19 가 필요조건 전부 검사. 충분조건은 미검사임을 명시 |
| 4 | **수용 31** 의 행동 절반 | LLM 출력 | G31-b eval 시나리오(임계값) + 금지 행위는 결정적 0 |
| 5 | **D-32 3행** — 해설본 자연어 사실성 | 무한한 서술 공간 | 기계 확인 가능한 주장(카운트·경로·구조명)만 스윕(G26-b) + 체크섬의 보장 범위 명문화 |
| 6 | **D-32 2행** — 외부 CLI 표면 | 호스트 소유. 이 레포가 통제하지 않는다 | **인용하지 않는다**(G30). 의존을 없애는 것이 유일한 zero-debt 해법 |
| 7 | **D-32 4행** — 소비자 프로젝트 파일 존재 | 소비자 소유 | 우아한 폴백(G31-a). 존재 검사가 답이 아니다 |
| 8 | **D-22 ④** — 도구명 허용 집합 | 호스트 소유 외부 표면 + 손-유지 열거 | **금지 패턴 + 레포 내 유일 출현 토큰 탐지**로 대체 권고(`00-REVIEW.md` R1) |
| 9 | **수용 32 의 버전 값 자체** | 문서 내부 모순이라 게이트가 잘못된 값에도 green | 설계문서 §5:455·D-7 정정이 선행 |
| 10 | **G7 의 "안내됨"** | LLM 행동 + 스킬은 현행 러너 대상 아님 | 결정적 절반만 게이트. 측정하지 않음을 기록 |

---

## 9. 신설 게이트 요약 — `verify-done.sh` 반영안 【Q1·Q5 반영 확정】

```
§16  주입 예산(총량 9216B) + tier 선언   (25-14) — G18 · G18-b · G19 · G21
       트랙 C · Stage S6 · enforceFail = true (처음부터 fail)
§17  배포물 상호 참조 실재                (25-16) — G22 (①②③). ④는 재설계 권고
       트랙 C · Stage S1 · enforceFail = true (처음부터 fail)
§6   확장: 카운트 주장 탐지식 검사        (25-17) — G23 · G23-b
       트랙 B · Stage S10 · enforceFail = false + 승격 조건 (Q1 의 유일한 예외)
§2   추출: check_agent_frontmatter       (25-24) — G29 (같은 스크립트를 §2·CI·픽스처가 공유)
§7   중복 처리 방침 주석                  (25-16) — §17 과의 대상 분할을 1문장으로 기록
G-D6 배포물 전체 orca 0건                 (26-2)  — Stage S15 · 결정적 (Q5 채택)
G-UT / G-GHOST  export_harness 분류표     (S24 / S5) — §11 이 이미 강제한다(별도 섹션 불필요)
```

**§18 이후는 비워 둔다.** §12 는 영구 결번이다.

### Q1 이 이 표를 어떻게 바꿨나 — warn-first 를 기각한 근거

검수는 §16·§17 을 정책 플래그로 warn-first 도입할 것을 권고했고(`classificationCompleteEnforceFail`
선례), 컨트롤은 **기각**했다. 근거는 같은 레포의 **더 가까운 선례**다 —
W-024 가 `tier2CoverageEnforceFail` 을 도입 즉시 fail 로 놓으며 이렇게 적었다:

> 이 배치가 유일한 갭을 같은 배치에서 메우므로 승격 직후 16/16 green 이다.
> `tier1CoverageEnforceFail` 이 S1 경고 → S4 fail 로 간 것과 달리 단계를 나눌 이유가 없었다.
> **영구 노란 경고는 아무도 보지 않는다.**

지금이 정확히 그 상황이다 — §17 이 검사할 dangling 8종을 **같은 배치에서** 고친다.
따라서 **게이트를 검사 대상 정리와 같은 커밋에 넣고 처음부터 fail** 로 간다.
"같은 커밋" 이 중간 red 상태를 아예 없애므로 O1·O2 가 해소된다.
플래그를 두면 **승격을 잊을 자유**가 생기고, 그것이 저 문장이 경계한 것이다.

**25-17 만 예외인 이유**: 동결 기록을 빼는 제외 경로 규칙의 정확도가 실전에서 검증되지
않았다(E8). 근거가 다르므로 취급도 다르다 — 그 대신 **승격 조건이 데이터에 명시**된다.

### 두 선례의 차이 (다음 게이트를 세울 사람을 위해)

| 선례 | 형태 | 언제 쓰나 |
| --- | --- | --- |
| `tier1CoverageEnforceFail` | 경고 → 나중에 fail | 갭을 **이 배치에서 못 메울 때** |
| `tier2CoverageEnforceFail` | **도입 즉시 fail** | 갭을 **같은 배치에서 메울 때** ← §16·§17 |
| `classificationCompleteEnforceFail` | 경고 + 승격 조건 | 검사 **자체의 정확도가 미지수**일 때 ← 25-17 |

셋 다 살아 있는 관례다. **"어느 것을 쓰는가" 는 갭을 지금 메우는지, 검사가 믿을 만한지로
갈린다** — 편의로 고르는 것이 아니다.
