# 00 — 적대적 검수: `2026-09-07-hiway-program-design.md` (D-1~D-33)

> 검수 기준 커밋 **`3f85f47be4997e54d275218bf64ac2c81324c2bd`** (`git rev-parse HEAD` 일치 확인).
> 대상: 설계문서 1,133행 전문 + 감사 원본 5종(T1 363 / T2 276 / T3 402 / T4 312 / T5 461행) **전부 정독**.
> 모든 지적에 위치(`§N` / `D-N` / `파일:줄`)와 **실측 재현 명령**을 붙였다.
> 이 문서는 동의 유보가 아니라 반대 의견을 포함한다 — 반대에는 근거와 실측을 붙였다.

**요약 판정.** 설계는 결정의 밀도·근거의 질이 높고, 특히 §11이 스스로 미결을 찾아 닫은 것은
드문 수준이다. 그러나 **구현 LLM에게 이대로 넘기면 최소 4건이 첫 커밋에서 게이트를 red로
만들고, 2건은 수용 테스트가 원리적으로 통과 불가능하다.** 가장 무거운 것은 다음 셋이다.

| # | 지적 | 왜 무거운가 |
| --- | --- | --- |
| **L1** | D-8의 강제 장치(`check_classification_complete`)가 **스킬을 보지 않는다** | 결정이 존재하지 않는 가드로 자기를 정당화한다 — 이 레포가 이름 붙인 결함 클래스 그 자체 |
| **E1** | §9.1 주입량 측정표가 **실측과 다르다** (23,989B 주장 vs 실측 **34,062B**) | §9 전체(진단·목표치·"AGENTS.md 상한의 98%")가 이 숫자 위에 서 있다 |
| **L2** | D-12의 전제("하네스 호출이 함수 하나에 박혀 있다")가 **사실이 아니다** — 호출 지점 3곳 | 프로그램의 자기모순을 막겠다는 항목이 자기모순을 남긴다 |

---

## 1. 논리 결함 — 결정 간 모순·근거 불성립·증거표와 처방의 불일치

### L1 — D-8의 강제 장치는 존재하지 않는다 【심각도: 높음】

**위치**: D-8 (§2), 수용 테스트 6.

D-8은 이렇게 쓴다:

> W-024 가 신설한 `check_classification_complete` 가 이 누락을 경고로 잡으므로, 등재하지
> 않으면 게이트가 운다 — **그 경고가 정확히 이 결정을 강제하는 장치다.**

**실측 반증.** 그 검사는 **에이전트 디렉토리만** 열거한다:

```
scripts/check_eval_coverage.py:302-309
  def _discover_all_agents(root):
      agents_dir = root / "plugins" / "common" / "agents"
      return {p.stem for p in agents_dir.rglob("*.md")}

scripts/check_eval_coverage.py:345-346
  covered = tier1 | tier2 | classified
  missing = sorted(all_agents - covered)      # ← 단방향. covered - all_agents 는 보지 않는다
```

`control-loop`은 **스킬**이다(`plugins/common/skills/control-loop/SKILL.md`, 26-1). 따라서
`all_agents`에 영원히 들어오지 않고, **등재하지 않아도 경고가 0건**이다. 반대로 등재해도
`covered - all_agents`를 보지 않으므로 아무 일도 일어나지 않는다 — 즉 이 검사는 D-8의
등재를 **강제하지도, 방해하지도** 않는다.

부가 사실: `evals/policy.json:141` `classificationCompleteEnforceFail: false` — 에이전트에
대해서조차 fail이 아니라 warn이다.

**이것이 왜 심각한가.** D-8은 "침묵하지 않는다"를 표방하면서, 침묵을 깨는 장치로 **그 대상을
스캔하지 않는 검사**를 지목했다. 이것이 정확히 W-024가 명명한 *"검사 대상이 아닌 것은 결코
red가 되지 않는다"* 다 — 계획 문서가 그 클래스를 인용하는 문단 안에서 그 클래스를 재현했다.

**권고**(택1, 어느 쪽이든 D-8 본문의 "강제 장치" 문장은 삭제해야 한다):
- (a) `_tier2Classification`의 등재 대상을 "에이전트"에서 "eval 채점 대상 컴포넌트"로 넓히고,
  `check_classification_complete`의 발견원(`_discover_all_agents`)에 `skills/*/SKILL.md`를
  더한다. 그러면 진짜로 강제된다. 비용: `_tier2Rationale`의 회계 문장(33종)이 52종으로 바뀜.
- (b) 스킬은 이 표의 대상이 아님을 인정하고, D-8을 **"기록은 남기되 강제 장치는 없다"**로
  정직하게 재서술한다. 이 레포의 관례상 (b)도 충분히 정당하다 — 없는 강제를 있다고 쓰는 것만이
  금지다.

---

### L2 — D-12의 전제가 사실이 아니다: 하네스 결합점은 1곳이 아니라 3곳 【심각도: 높음】

**위치**: D-12 (§8), 26-6, 수용 테스트 16.

D-12: *"`evals/run.py` 의 `build_claude_command()` 는 `claude` CLI 인자를 직접 조립한다 …
**하네스 호출 지점 하나만** 심으로 뽑는다"*.

**실측**: `evals/run.py`에 `claude` CLI에 결합된 지점이 최소 **3곳**이다.

| 위치 | 내용 | D-12 처방에 포함? |
| --- | --- | --- |
| `evals/run.py:1077` | `build_claude_command` — 시나리오 실행 | ✅ |
| **`evals/run.py:1049`** | **LLM judge**: `subprocess.run(["claude","-p",prompt,"--model","sonnet","--output-format","text"], …)` | ❌ **누락** |
| **`evals/run.py:1304`** | `if shutil.which("claude") is None: … SKIPPED` — 가용성 게이트 | ❌ **누락** |

LLM judge는 별도의 하드코딩 호출이고 **모델명(`sonnet`)까지 하네스 종속**이다. 심을 하나만
뽑으면 러너는 여전히 `claude` CLI 없이는 채점 자체를 못 한다 — D-12가 막겠다고 선언한
자기모순("하네스 중립을 주장하는데 그 주장을 검증하는 eval은 Claude Code만 구동")이 **그대로
남는다.**

**수용 테스트 16은 문자 그대로는 통과 불가능하다.** `run.py`에는 CLI 호출과 무관한 `claude`
문자열이 더 있다:

```
evals/run.py:1196-1198   "type": "claude_exit", f"claude exit {r.returncode}…"
evals/run.py:1376        argparse … description="claude-code-kit agent evals runner"
$ grep -c claude evals/run.py   → 14
```

**권고**:
1. D-12의 대상을 **세 지점 전부**로 고친다: `Harness` 프로토콜에 `run_scenario_cmd()`,
   `judge_cmd()`, `is_available()` 세 메서드를 둔다. LLM judge의 모델명도 구현체 소유로.
2. 수용 테스트 16을 문자열 스캔이 아니라 **호출 스캔**으로 재작성한다 — 03-gate-spec.md G16 참고.

---

### L3 — W-026의 버전이 문서 안에서 아직 두 값이다 【심각도: 중】

**위치**: `docs/specs/2026-09-07-hiway-program-design.md:455` (§5 W-026 제목), D-7 1단계,
§11.2(f), 수용 테스트 32.

§11.2(f)가 *"D-7 정정: 원문의 'v2.18.0 — control-loop 신설'을 v2.19.0 으로 옮긴다"*라고
**기록**했으나, 모순되는 문장 자체는 그대로 남아 있다:

```
$ sed -n '455p' docs/specs/2026-09-07-hiway-program-design.md
### W-026 — `control-loop` 스킬 (v2.18.0)
$ grep -n "v2.18.0.*control-loop\|control-loop.*v2.18" docs/specs/2026-09-07-hiway-program-design.md
   (D-7 1단계 문장도 동일)
```

§11이 잡아낸 **미결 2(자기모순)의 해법이 §9.4처럼 "정정 문장 추가"였는데, 같은 처리를
여기서 반복했다.** 구현 LLM이 §5나 D-7만 읽고 착수하면 2.18.0으로 릴리스한다 — 그리고
2.18.0은 W-025 C 트랙이 이미 쓴 번호다.

**권고**: 정정 문장을 남기는 방식은 §11.2(f)에서 이미 한 번 실패했다. **§5 제목과 D-7 본문을
직접 v2.19.0으로 고치고**, 정정 이력은 §11.2(f) 한 곳에만 둔다. (역사 보존 원칙은 *완료된*
기록에 적용되지, **아직 실행되지 않은 지시서**에는 적용되지 않는다.)

---

### L4 — D-24가 `phase-guides.md`에 서로 배타적인 두 처방을 내린다 【심각도: 중】

**위치**: D-24 (§10.3), §11.2(b).

D-24 본문:
- *"`plugins/common/skills/references/` **8종 미참조** … 순수 고아 4종은 재참조 신설 또는 삭제 중 택1"*
  → 순수 고아 4종 = `available-tools` · `model-selection` · **`phase-guides`** · `work-integration`
- 바로 다음 불릿: *"`references/work-system.md`·**`phase-guides.md`** 는 **활성 참조인데 구식** … → 재작성."*

§11.2(b)가 "순수 고아 4종 → **삭제**"로 닫았으므로, `phase-guides.md`는 **삭제와 재작성이
동시에 지시된 상태**다.

**증거 대조**: 활성 참조라는 서술이 틀렸다.

```
T3-findings.md §4.4:  phase-guides.md → 0건 (doc-coauthoring의 "단계별 가이드 작성"은 동음이의)
T3 커버리지표:        phase-guides.md | ORPHAN | 참조 0건. skills/README.md와 같은 구식 5-Phase 모델
```

**권고**: `phase-guides.md`는 **삭제**(§11.2(b) 준수). D-24의 두 번째 불릿을
"`references/work-system.md` 는 활성 참조인데 구식 → 재작성"으로 축소한다. → E4도 함께 참조.

---

### L5 — D-31의 산술이 19에 도달하지 않는다 【심각도: 높음 — 수용 테스트 28이 실패한다】

**위치**: D-31 (§11), 수용 테스트 28, 27-4(`_skillsCountNote` "해소됨" 갱신).

D-31이 제시한 계산:

```
현재 skills/ 최상위 진입 = 21 (스킬 19 + README.md + references/)
README.md 삭제 + references/ 정리(D-24) 후 = 19  ← 오집계 완전 해소
```

**실측 반증**: D-24는 `references/` **디렉토리를 없애지 않는다.** 10개 중 8개만 지운다 —
`task-tools-fallback.md`(brainstorming·plan-task·auto-dev 3곳이 실제 인용)와 `work-system.md`
(plan-task·auto-dev가 인용, D-24가 **재작성** 지시)는 **살아남는다.**

```
$ ls plugins/common/skills/references/
available-tools.md  conflict-resolution.md  deliberation-pattern.md  examples.md
model-selection.md  perspectives-guide.md   phase-guides.md
task-tools-fallback.md  work-integration.md  work-system.md      ← 10개
                                              ↑ 2개는 D-24가 보존
```

따라서 삭제 후 최상위 진입 = **19(스킬) + 1(`references/`) = 20**, 19가 아니다.
- 수용 테스트 28 *"최상위 진입 항목 수 == SKILL.md 보유 스킬 수"* → **fail**
- 27-4의 `packaging/targets.json:85` `_skillsCountNote` "해소됨" 갱신 → **거짓 기록**이 된다
  (이 레포가 가장 싫어하는 형태 — 실측 기록 필드에 실측되지 않은 주장을 넣는 것)
- D-31이 "부수 효과가 결정적이다"라고 부른 그 근거 자체가 성립하지 않는다

**권고**: 살아남는 2종을 `references/` 밖으로 옮겨야 20 → 19가 된다. 자연스러운 자리는
**실제 소비자 스킬 디렉토리**다:
- `task-tools-fallback.md` → 3개 스킬이 공유하므로 `plugins/common/skills/plan-task/` 아래로
  옮기고 나머지 둘이 상대경로로 가리킨다(현재도 상대경로 인용이므로 형태 동일), 또는
- 두 파일 모두 `plugins/common/skills/plan-task/references/` 로 이관.

어느 쪽이든 **작업 항목이 신설돼야 한다**(현재 25-18은 "8종 정리"만 지시). 이 이관 없이는
D-31의 핵심 논거와 수용 테스트 28이 함께 무너진다.

---

### L6 — D-22 ④가 D-32 자신의 판정과 모순된다 【심각도: 중】

**위치**: D-22 (§10.3) 검사 ④, D-32 (§11.1) 2행, D-23.

D-22 §17의 검사 목록:

> ④ frontmatter `tools:` 의 도구명이 **알려진 집합**에 속함

이 "알려진 집합"은 **호스트가 소유한 외부 표면**(Claude Code 내장 도구 목록)이고, 레포가
손으로 유지해야 하는 **열거**다. 그런데 같은 문서가 두 곳에서 정확히 이것을 금지한다:

| 근거 | 문장 |
| --- | --- |
| D-32 2행 | *"외부 표면은 게이트 불가이므로 **의존을 없애는 것**이 유일한 zero-debt 해법"* |
| D-23 | *"목록을 손으로 유지하지 않는다 … 세 번째 인스턴스이므로 이제 **열거를 금지**한다"* |

**게다가 이 검사가 잡으려는 대상은 단 1건이다** — `verify-integration.md:14`의 `LSP`:

```
$ grep -rn "LSP" plugins/common/agents/ plugins/common/skills/ | wc -l
1
```

**권고**: ④를 §17에서 빼고, **금지 목록(blocklist)** 방식으로 바꾼다 — `mcp__*` 금지가 이미
그 형태다(허용 집합이 아니라 금지 패턴). 구체적으로: `tools:` 값이 `mcp__*`이거나 **레포
내 다른 에이전트에서 한 번도 쓰이지 않은 단독 토큰**이면 fail. 이러면 손 유지 목록이
필요 없고(전체 33종의 사용 분포가 SSOT), `LSP` 같은 유일 출현 토큰이 정확히 잡힌다.
반대 의견이 있다면, "허용 집합을 하드코딩하는 이 한 건만은 예외"라는 근거를 D-23의
"열거 금지" 옆에 명시적으로 적어야 한다 — 침묵한 예외는 다음 사람이 지운다.

---

### L7 — D-32 1행의 "기존 검사기를 그대로 돌린다"는 불가능하다 【심각도: 중】

**위치**: D-32 (§11.1) 1행, 25-24, 수용 테스트 29.

D-32: *"스킬의 예제 템플릿을 픽스처로 두고 **기존 frontmatter 검사(§2)를 그대로 돌린다** …
새 규칙을 만들지 않고 **이미 있는 검사기를 재사용**한다."*

**실측**: `verify-done.sh` §2는 재사용 가능한 검사기가 아니다 — **인라인 heredoc**이고
**경로가 하드코딩**돼 있으며 **스킬을 명시적으로 건너뛴다**.

```
scripts/verify-done.sh:60-79
  python3 - <<'EOF' && green "manifest + frontmatter checks" || red "…"
  …
  for f in pathlib.Path("plugins").rglob("*.md"):
      if "/skills/" in str(f): continue        # ← 스킬은 건너뛴다
      …
  EOF
```

따라서 "그대로 돌린다"는 두 경로뿐이고 둘 다 D-32의 주장과 다르다:
- (a) §2를 파라미터화된 스크립트로 **추출**한다 → "새 규칙을 만들지 않고"에 반하는 실제 변경
  (게다가 CI 동등 스텝도 함께 옮겨야 한다)
- (b) 픽스처를 `plugins/**` 아래 `skills/` 밖에 둔다 → **가짜 에이전트가 소비자에게 배포된다**
  (북극성 위반이며, 에이전트 수 33이 34로 바뀌어 `check_doc_counts.py`가 red)

**권고**: (a)를 채택하되 D-32의 서술을 정직하게 고친다 — *"§2의 frontmatter 검사 본문을
`scripts/check_agent_frontmatter.py`로 추출해 경로를 인자로 받게 하고, verify-done §2·CI·
템플릿 픽스처 테스트 셋이 같은 스크립트를 호출한다"*. 이것은 이 레포의 `lint-shell.sh`
관례(한 스크립트를 게이트와 CI가 공유)와 정확히 같은 모양이라 **오히려 관례 정합적**이다.

---

### L8 — 유령 프로젝트 건수가 §1.4(26)와 D-10/25-1(28)로 갈린다 【심각도: 낮음】

**위치**: §1.4, §1.5, D-10, 25-1.

- §1.4: *"`~/.claude.json` 의 유령 프로젝트 **26건**"* … *"유령 26건은 과거 버전의 잔재다"*
- D-10: *"일회성: 유령 프로젝트 항목 **28건** 정리"*
- 25-1: *"유령 프로젝트 항목 **28건** 정리"*

두 숫자를 잇는 문장이 없다. (§1.5의 "유령 플러그인 설치 기록 8건"은 별개 항목이므로 26+2의
근거가 되지 못한다.) 수용 테스트 1이 *"경로가 없는 항목 0건"*으로 건수를 안 쓰기 때문에
게이트는 통과하지만, **산문에 같은 사실의 숫자가 둘 있는 상태**는 D-23이 금지하는 형태다.

**권고**: 둘 중 실측값 하나만 남기고(A 트랙 착수 시 재실측), 나머지는 삭제. `[unresolved]`로
남겨도 무방하다 — 숫자를 지우는 것이 두 숫자를 남기는 것보다 낫다.

---

### L9 — §11.2(f)의 트랙 분할이 W-025 28개 항목 중 22개만 덮는다 【심각도: 중】

**위치**: §11.2(f), §11.4.

§11.2(f)는 *"W-025 의 **22개 항목**은 배포물에 닿는지로 깔끔히 갈린다"*라며 A/B/C 표를
제시한다(A: 25-1·3·4·5·6 / B: 25-2·7·8·9·10·14·16·17·19·22 / C: 25-11·12·13·15·18·20·21
= 5+10+7 = 22). 그런데 **같은 §11의 11.4가 25-23 ~ 25-28 여섯 항목을 더 추가한다.** 이 여섯은
어느 트랙에도 배정되지 않았다.

배정을 실측 기준(배포물 `plugins/**`에 닿는가)으로 대입하면:

| 항목 | 대상 | 트랙 |
| --- | --- | --- |
| 25-23 `skills/README.md` 삭제 | `plugins/common/skills/README.md` + 루트 README | **C** (배포물) |
| 25-24 템플릿 픽스처 테스트 | `tests/` · `scripts/` | B |
| 25-25 `mcp-builder` CLI 인용 제거 | `plugins/common/skills/mcp-builder/SKILL.md` | **C** (배포물) |
| 25-26 미러 보장범위 명문화 | `CLAUDE.md` 또는 `docs/conventions/` | B |
| 25-27 `enforce-structure` 폴백 | `plugins/common/agents/dev/enforce-structure.md` | **C** (배포물) |
| 25-28 `docs/superpowers/` 재배치 | `docs/` | B |

**결론적으로 "릴리스는 한 번"이라는 §11.2(f)의 판정은 유지되지만**(C 추가분이 같은 2.18.0에
들어가므로), 문서에 그렇게 적혀 있지 않아 구현 LLM이 25-23/25/27을 버전 무변경 트랙으로
처리할 수 있다 — 그러면 **배포물이 바뀌었는데 버전이 안 올라간다**. 이것은 CLAUDE.md가
"CRITICAL"로 못박은 바로 그 실수다(*"same version = no update fetched = users never get the fix"*).

**권고**: §11.2(f) 표에 여섯 행을 추가하고 "22개"를 "28개"로 고친다.

---

### L10 — 수용 테스트 27은 현행 트리에서 2건이 아니라 4건에 걸린다 【심각도: 중】

**위치**: D-28 (§10.3) 2행, 수용 테스트 27.

D-28은 `isolation: worktree` 누락을 `define-business-logic`·`design-user-journey` **2종**으로
적는다(T2 발견 그대로). 수용 테스트 27은 *"배포 에이전트 33종 중 `isolation: worktree` 규약
위반 **0건**"*을 요구한다.

**실측**: 기계적 정의(`tools:`에 Write/Edit/NotebookEdit ∧ frontmatter에 `isolation:` 없음)로
전수 스캔하면 **4건**이다.

```
$ python3 <스캔>          # 03-gate-spec.md G27 에 명령 전문
MUT_NO_ISO  facilitator.md
MUT_NO_ISO  synthesizer.md
MUT_NO_ISO  define-business-logic.md
MUT_NO_ISO  design-user-journey.md
```

`facilitator`·`synthesizer`는 CLAUDE.md의 "메타 에이전트 6종"에 속하고 `tools:`에 `Write`가
있다. D-28의 처방대로 2종만 고치면 **수용 테스트 27은 여전히 fail**이다.

**그런데 나머지 2종을 그냥 고치면 안 된다** — 이건 내가 D-28에 반대하는 지점이다.
`facilitator`/`synthesizer`는 multi-perspective-review의 **중간 산출물을 메인 세션이 곧바로
읽어야** 하는 구조다. 워크트리에 격리하면 산출물이 병합 전까지 보이지 않아 다관점 리뷰
루프가 끊긴다. 즉 이 둘은 *결함*이 아니라 **의도적 예외**일 가능성이 높다.

**권고**: 수용 테스트 27을 "0건"이 아니라 **"예외 목록에 없는 위반 0건"**으로 바꾸고,
`rules/parallel-worktree.md`(또는 `docs/conventions/`)에 예외 사유를 1줄로 기록한다.
근거 없는 예외는 다음 감사에서 다시 결함으로 보고된다 — 실제로 이번 T2가 그렇게 보고했다.
(T2 자신이 *"Planning 산출물(`docs/planning/**`)이 병렬-worktree 규칙의 '소스 파일'에
해당하는지 자체가 D-1~D-21 어디에도 명시돼 있지 않다 — 컨트롤 세션의 판단이 필요"*라고
판단을 요청했는데, D-28은 그 판단을 **내리지 않고 결론만** 적었다.)

---

## 2. 증거 대조 — 감사 5종의 발견 중 설계에 반영되지 않은 것

> 방법: T1~T5의 **커버리지 표 222행 + 발견 상세 전부**를 설계문서 §10·§11의 결정·작업항목과
> 1:1 대조했다. §11이 이미 잡은 `skills/README.md` 외에 **아래 9건**이 남는다.

### E1 — §9.1 주입량 측정표가 실측과 다르다 【심각도: 높음 — §9 전체의 근거】

**위치**: §9.1, §9.2 서두, D-20 목표치, §11.2(e).

§9.1 주장 vs **실제 훅 로더(`session-start.py`)로 측정한 값**:

| 구성 | §9.1 주장 | **실측(HEAD)** | 차이 |
| --- | ---: | ---: | ---: |
| RULES | 20,191 B (84%) | **28,005 B** (82%) | **+38.7%** |
| WORKFLOW | 3,728 B (16%) | **6,057 B** (18%) | **+62.5%** |
| **합계** | **23,989 B** | **34,062 B** | **+42.0%** |

재현:

```
$ python3 - <<'EOF'
import importlib.util; from pathlib import Path
s=importlib.util.spec_from_file_location("ss","plugins/common/hooks/session-start.py")
m=importlib.util.module_from_spec(s); s.loader.exec_module(m); r=Path("plugins/common")
print(len(m.load_rules(r, False).encode()), len(m.load_workflow_skill(r).encode()))
EOF
28005 6057
```

**파생 주장이 전부 틀어진다**:
- §9.1 *"`AGENTS.md` 는 §15 로 24,576B 상한이 걸려 있는데, 세션 주입은 그 **98%**를 …"*
  → 실제는 **139%**. 논거는 **더 강해진다**(상한을 이미 넘겼다). 그런데 숫자가 틀린 채로
  남으면 다음 사람이 §9 전체를 의심한다.
- D-20 *"23,989B → 약 7.5KB (**69% 감축**)"* → 34,062B 기준이면 **78% 감축**.

**결정적 정황**: §11.2(e)의 core 6종 개별 합(13,282 B)은 **실측과 정확히 일치**한다
(definition-of-done 3,648 + loop-engineering 3,029 + planning-protocol 2,027 + code-quality 1,835
+ planning-check 1,437 + ssot 1,306 = 13,282 ✓). 즉 **같은 문서 안에서 같은 코퍼스의 두 측정이
서로 모순**된다 — §9.1이 낡았거나 토큰 단위로 잰 것으로 보인다.

**권고**: §9.1 표를 재측정값으로 교체하고, 측정 명령을 표 아래에 남긴다(다음 사람이 재현
가능해야 이 사고가 반복되지 않는다). 진단(§9.2)과 결정(D-17~D-21)의 방향은 **바뀌지 않는다** —
근거가 더 세질 뿐이다.

---

### E2 — WORKFLOW 예산 2,048 B는 처방된 작업으로 도달하지 못한다 【심각도: 높음】

**위치**: D-20, §11.2(e), D-18 3번째 불릿, 수용 테스트 18.

§11.2(e): *"WORKFLOW 2,048B 는 현재 3,728B 의 55% — **네이티브 중복 표 2개를 걷어내면
도달하는 수치**다."*

**실측**:

```
본문(frontmatter 제거)                         6,019 B
  ├ Skill Trigger Map (L28-43)  ┐
  └ Agent Selection  (L45-55)   ┘  두 표 합계   1,203 B
두 표 제거 후 남는 본문                          4,816 B   ← 예산 2,048 B 의 2.35배
```

2,048 B에 도달하려면 **추가로 2,768 B(남은 본문의 57%)를 더 잘라야** 한다. 남은 본문의
대부분은 `## 비신뢰 텍스트 취급 (untrusted text) — 호스트 무관 공통 규율`(L62~111)이고,
이것은 **네이티브 중복이 아니라 킷 고유의 보안 규율**이다(D-18의 삭제 근거가 적용되지 않는다).

**즉 예산과 처방 중 하나는 틀렸다.** 선택지:
- (a) WORKFLOW 예산을 **4,096 B**로 올린다 — 두 표 제거 후 4,816B에서 추가 720B만 깎으면 된다
  (`Workflow Chain` 서술 압축 수준). 처방과 예산이 일치한다.
- (b) 예산 2,048 B를 유지하고, 비신뢰 텍스트 절을 **`rules/` 로 이관**한다 — 그러면 그것은
  core 티어 예산(6,144 B)을 먹는다. core 6종이 13,282 → 6,144로 가야 하는 상황에서 여기에
  ~2.5KB를 더 넣는 것은 비현실적이다.
- (c) 비신뢰 텍스트 절을 **reference 티어 파일**로 빼고 WORKFLOW에는 색인 한 줄만 남긴다 —
  D-17의 티어 모델을 WORKFLOW에도 적용하는 것이라 구조적으로 가장 일관된다.

**내 권고는 (c)**. 근거: 이 절 자신이 *"이 절은 툴 중립이다"*라고 선언하므로 규범(`rules/`)의
성격이고, D-17이 만든 세 티어 체계는 정확히 "항상 현저할 필요는 없지만 없어지면 안 되는 것"을
담기 위한 것이다. 다만 **비신뢰 텍스트 규율을 reference로 내리는 것은 보안 규율의 현저성을
낮추는 결정**이므로, 컨트롤이 명시적으로 판단해야 한다 → 질문 Q2.

---

### E3 — dangling `references:`는 3종이 아니라 8종이다. 5종은 고칠 작업 항목이 없다 【심각도: 높음】

**위치**: D-22 증거표 1행, 25-16(§17 게이트), 26-8, T3 §4.6.

D-22 증거표는 이렇게만 적는다:

> `references:` frontmatter 가 없는 파일을 가리킴 | `implement-code`·`plan-implementation`·`review-code`

**실측 전수 스캔 — 8종 10개 경로 전부 MISSING**:

```
MISSING plugins/common/agents/meta/facilitator.md        -> ../../../skills/common/multi-perspective-review/references/perspectives-guide.md
MISSING plugins/common/agents/meta/synthesizer.md        -> ../../../skills/common/…/conflict-resolution.md
MISSING plugins/common/agents/meta/consensus-builder.md  -> ../../../skills/common/…/conflict-resolution.md
MISSING plugins/common/agents/meta/devils-advocate.md    -> ../../../skills/common/…/perspectives-guide.md
MISSING plugins/common/agents/meta/facilitator-teams.md  -> (3개 경로 전부)
MISSING plugins/common/agents/dev/implement-code.md      -> path: references/patterns.md (+2)
MISSING plugins/common/agents/dev/plan-implementation.md -> path: references/templates.md (+1)
MISSING plugins/common/agents/dev/review-code.md         -> path: references/checklist.md (+1)
```

`skills/common/` 이라는 **최상위 디렉토리는 이 레포에 존재한 적이 없다**(`find . -path "*/skills/common/*"` → 0건).
T3이 §4.6에 명시적으로 보고했으나 §10 통합에서 빠졌다 — §11이 잡은 `skills/README.md`와
**같은 유형의 누락 2번째 사례**다.

**세 가지 파급**:
1. **25-16이 만드는 §17은 첫 실행에서 red다.** 게이트가 검사할 5개 파일을 고치는 항목이 없다.
   (26-8은 메타 에이전트의 *듀얼 모드 절*만 다룬다 — `references:` frontmatter는 다른 곳이다.)
2. **D-24와 순서 결합.** 이 경로들이 *의도*한 대상은 `skills/references/{perspectives-guide,
   conflict-resolution,deliberation-pattern}.md` 인데, D-24가 그 셋을 **삭제**한다. 따라서
   고칠 때 가리켜야 할 곳은 `plugins/common/skills/multi-perspective-review/*.md`다.
   순서를 틀리면 "고쳤는데 다시 깨진다".
3. **`references:` 문법이 두 종류다** — 메타 5종은 문자열 리스트, dev 3종은 `path:` 매핑
   리스트. §17의 검사 ①은 두 형태를 모두 파싱해야 한다(구현 지시서에 명시 필요).

**권고**: 25-21(미완 실행 잔재)에 *"에이전트 8종의 `references:` frontmatter 정리 — dev 3종은
필드 제거(내용이 본문에 인라인), 메타 5종은 `multi-perspective-review/` 실경로로 정정하거나
제거"*를 추가하고, **25-16보다 앞선다**고 못박는다.

---

### E4 — `references/work-system.md` 재작성이 어느 작업 항목에도 없다 【심각도: 중】

**위치**: T3 F5, D-24 3번째 불릿, 25-18.

D-24는 *"`references/work-system.md`·`phase-guides.md` 는 활성 참조인데 구식 → **재작성**"*
이라고 결정했다. 그러나 작업 항목 25-18은:

> 25-18 | `references/` **8종 정리** + `docs/superpowers/` 고아 처리 (D-24) | 워커

8종 = 미참조 8종(DUP 4 + 순수 고아 4)이다. **`work-system.md`는 그 8종에 들어 있지 않다**
(활성 참조이므로). 즉 D-24가 결정한 재작성이 작업 목록에서 증발했다.

T3의 평가로는 이것이 **가장 사용자 영향이 큰 항목 중 하나**다 — `plan-task/SKILL.md:200`과
`auto-dev/SKILL.md:386`이 "상세/전체"로 실제로 링크하는 문서이고, 509행 전체가 현재
`plan-task`(Step 0-4)와 다른 세대의 Phase 0-6 모델을 서술한다. *"상세를 보러 갔다가 더
헷갈리는"* 상태다.

**권고**: 25-18을 "8종 정리"가 아니라 **"10종 처리 — 8종 삭제 + `work-system.md` 재작성"**으로
고치고, 재작성 범위(509행 전면 vs 상단 경고 배너)를 결정한다 → 질문 Q3.

---

### E5 — `analyze-tech-debt`의 하드코딩 프로젝트명이 반영 안 됐다 【심각도: 낮음】

**위치**: T2 커버리지표 #6, T2 §2.1.

`plugins/common/agents/dev/analyze-tech-debt.md:95` 예시 리포트에 `대상: claude_setting` —
이 레포와 무관한 외부 프로젝트명이 배포물에 박혀 있다. T2가 CLAUDE.md의 Consumer-first
원칙 위반으로 분류했으나 §10 어디에도 없다.

§17(D-22)의 4개 검사 중 어느 것도 이것을 잡지 못한다(경로도 에이전트명도 도구명도 아니다).

**권고**: 25-21(미완 실행 잔재)에 1줄 추가. 저비용·저위험.

---

### E6 — `manage-api-versions`의 존재하지 않는 계약이 반영 안 됐다 【심각도: 중】

**위치**: T2 커버리지표 #13, T2 §2.1.

`plugins/common/agents/dev/manage-api-versions.md:54-61, :159-176` 이 **`agents/**/index.json`
레지스트리**와 에이전트 frontmatter **`version:` 필드**를 관리 대상으로 서술한다. 실측:

```
$ grep -rln '^version:' plugins/common/agents/   → 0건
$ find . -name index.json -path "*agents*"       → 0건
```

CLAUDE.md는 정반대를 못박는다: *"plugin.json has no agent/skill registry — both are
auto-discovered"*.

이것은 D-22 증거표의 *"존재하지 않는 계약을 가르침"* 행과 **정확히 같은 클래스**인데, 그 행은
`agent-creator`·`skill-creator`만 나열한다. 그리고 D-32가 그 두 스킬에 배정한 기전(템플릿
픽스처 테스트)은 에이전트 산문에는 적용되지 않는다.

**권고**: 25-21에 추가. §17로는 못 잡으므로(산문이 서술하는 *스키마*의 부재라 경로·이름 검사에
안 걸린다) 1회 정리 항목으로 명시한다.

---

### E7 — site `_index` 3개 수치 오기재가 명시적으로 배정되지 않았다 【심각도: 중】

**위치**: T5 F-14/F-15, D-23, 수용 테스트 23.

D-23은 *탐지 기전*을 만들지만, **현재 틀린 값 자체를 고치라는 작업 항목·수용 테스트가 없다.**
25-17은 "카운트 주장 탐지식 검사로 전환"이고 수용 테스트 23은 *"새 문서에 추가하면 자동
포함된다"*(기전 검증)이다.

실측 오차:

| 위치 | 주장 | 실측 |
| --- | --- | ---: |
| `site/content/_index.md:19` | Agent Behavior Evals **11개 시나리오** | **38** |
| `site/content/_index.md:18` · `_index.en.md:19` | 유닛 테스트 **220개 이상** / **220+** | 455 (거짓은 아니나 2배 이상 과소) |
| `site/content/_index.md:20` · `_index.en.md:21` | 기계 게이트 **8개 이상** / **8+** | 15개 명명 섹션 |
| `site/content/about.md:38` · `about.en.md:40` | **16 스킬** / **16 Skills** | **19** ← D-23이 명시적으로 언급한 유일한 건 |

**권고**: 25-17에 *"탐지 전환과 동시에 탐지된 기존 오기재를 전부 정정한다(현재 최소 4곳)"*를
붙이고, 수용 테스트에 *"§17/§16 게이트 신설 커밋 시점에 탐지 결과 미검사 주장 0건"*을 추가한다.

---

### E8 — D-23의 탐지식 검사는 "역사 기록 보존" 원칙과 정면 충돌한다 【심각도: 높음 — 설계 결함】

**위치**: D-23, 25-17, 수용 테스트 23. (증거 대조가 아니라 **설계 반대 의견**이지만 근거가
감사 데이터에서 나오므로 여기 둔다.)

D-23: *"카운트 주장을 **패턴으로 탐지**한다(`N개`·`N종`·`N skills`·`N agents` 류를 **배포·사이트
문서 전역**에서 스캔). 탐지됐는데 검사되지 않는 주장이 있으면 **fail**."*

**실측 반증**: `site/` 에는 **날짜가 박힌 블로그 포스트**가 있고, 그 안의 수치는 그 시점의
사실을 기록한 **동결 스냅샷**이다.

```
site/content/posts/2026-07-03-auditing-your-own-gates.md:20
   "…verify-done.sh는 초록불이었고, 169개 유닛 테스트가 녹색이었고…"     ← 현재 455
site/content/posts/2026-07-03-auditing-your-own-gates.md:26
   "3. 에이전트 거버넌스 (33개 정의의 일관성)"
site/content/posts/2026-07-03-auditing-your-own-gates.md:68
   "25개의 새 테스트가 전부 빨강이어도 CI는 통과했을 것이다"
site/content/posts/2026-07-02-harness-loop-engineering-landscape.md:78
   "Pi(4개 코어 툴 …)"
```

이 문장들을 "검사되지 않는 카운트 주장"으로 fail시키면 **영구 red**다. 고치면 T5 F-19가
지적한 대로 *"블로그는 발행 시점 스냅샷"*이라는 이 레포 자신의 보존 원칙(감사 수용 기준 5,
D-29의 *"역사 기록은 고치지 않는다"*)을 깨뜨린다.

그런데 **제외 목록을 만들면 D-23이 금지한 열거로 되돌아간다.**

**해법 — 열거가 아니라 규칙으로 제외한다.** 이것이 D-23의 정신을 지키면서 실행 가능한 유일한
형태다:

| 스캔 대상 | 근거 |
| --- | --- |
| `plugins/**/*.md` | 배포물. 현재를 서술한다 |
| `site/content/*.md` (최상위 파일만) | 랜딩·about — 현재를 서술한다 |
| `README.md` · `plugins/common/README.md` · `CLAUDE.md` | 현재 서술 |
| **제외**: `site/content/posts/**` · `docs/specs/**` · `docs/works/**` · `CHANGELOG.md` | **경로 규칙**으로 제외 — "날짜가 박힌 기록 디렉토리는 동결" 한 문장이 SSOT. 파일 목록이 아니다 |

이러면 `about.md`/`about.en.md`가 자동으로 들어오고(F-16/F-17 해소), 새 랜딩 페이지도
등록 없이 포함되며, 블로그·스펙·CHANGELOG는 **규칙 한 줄**로 빠진다. D-23의 목표
("목록을 손으로 유지하지 않는다")가 그대로 유지된다.

**D-23 본문에 이 스코프 규칙을 적어야 한다.** 지금 그대로 구현하면 워커는 영구 red를 만들거나,
말없이 제외 목록을 손으로 만든다 — 둘 다 나쁘다.

---

### E9 — `13 → 12`의 연쇄 영향 목록에 3건이 빠졌다 【심각도: 중】

**위치**: §9.4 "연쇄 영향 — 이 배치가 건드리는 게이트", D-18, 25-12.

§9.4가 나열한 것: `check_doc_counts.py` 대상 문서, `rules/CHECKSUMS.sha256`,
`docs/architecture/rules/MIRROR.sha256`, `AGENTS.md`(§11 드리프트), `packaging/targets.json`.

**빠진 것 3건**(실측):

1. **`docs/architecture/rules/tool-usage-priority.md` 자체를 지워야 한다.** 이 규범에는 해설본
   미러가 **있다**.
   ```
   $ ls docs/architecture/rules/ | grep tool-usage
   tool-usage-priority.md
   ```
   정본만 지우면 `sync-rule-mirror.sh`가 "짝 없는 미러"를 만나 §7이 red다.

2. **`docs/conventions/rules-mirror.md` 1~3행이 숫자를 하드코딩한다.**
   ```
   docs/conventions/rules-mirror.md:1  `plugins/common/rules/` (13) is what gets injected …
   docs/conventions/rules-mirror.md:2  `docs/architecture/rules/` (9) is the long-form …
   docs/conventions/rules-mirror.md:3  … The remaining four …
   ```
   13→12, 9→8이 되면 이 세 숫자가 전부 틀린다. `check_doc_counts.py`는 이 파일을 보지 않는다
   (`scripts/check_doc_counts.py:123-124`는 CLAUDE.md·README.md만).

3. **`AGENTS.md`의 `cck2:` conventions 블록도 재생성 대상이다.** §9.4는 "AGENTS.md(§11 드리프트)"
   라고만 적었는데, AGENTS.md에는 **독립된 두 마커 블록**이 있다:
   ```
   AGENTS.md:7    <!-- cck:begin  rules-v1.4.0        sha256:0a03ad2f… -->
   AGENTS.md:424  <!-- cck2:begin conventions-v1.0.0  sha256:fdd35efc… -->
   ```
   2번(rules-mirror.md 수정)이 발생하면 **conventions 블록도** 재생성해야 한다.
   그리고 CLAUDE.md 자신은 `check_doc_counts.py:123`가 `rules \((\d+)\)` 패턴으로 잡으므로 OK.

**권고**: §9.4의 연쇄 목록에 위 3건을 추가한다. 그리고 D-26(CLAUDE.md → conventions import)과
합쳐지면 CLAUDE.md의 `rules (13)` 문장이 어디로 가는지도 정해야 한다 → 아래 O5·질문 Q4.

---

## 3. 실행 불가능한 서술 — 완료 판정이 불가능한 동사

> 판정 기준: *"구현 LLM이 '했다'고 말했을 때, 컨트롤이 보고를 믿지 않고 직접 확인할 수 있는가."*
> 상세 대체안은 `03-gate-spec.md`에 각 항목 번호로 있다.

| # | 서술 | 위치 | 왜 판정 불가 | 대체 |
| --- | --- | --- | --- | --- |
| X1 | **"축약한다"** (6종 규범) | D-21 표, 25-15 | 얼마나? 무엇을 지우고 무엇을 남기나? 예산 게이트는 **core 총합**만 보므로 한 파일을 과도하게 깎아 통과 가능 | 파일별 상한을 policy 데이터로: `01-policy.json` `injection.perRuleMaxBytes` |
| X2 | **"중립화"** (`ssot`·`mcp-usage`) | D-19, 25-13 | 무엇이 "중립"인가에 대한 판정선 없음 | 언어 종속 토큰 blocklist 검사 (G13) |
| X3 | 수용 4 — *"bypass 를 끈 상태에서 축소된 allowlist 로 **일상 작업이 성립함**"* | §7 | "일상 작업" 미정의, 관측 기간 미정, 실패 시 판정 주체 없음. **이 배치에서 통과 선언이 불가능하다** | 수용 테스트에서 제거하고, A 트랙 산출물을 "제거한 42→N개 목록 + bypass off 1세션 실행 로그"로 바꾼다 (G4) |
| X4 | 수용 7 — *"`agent-teams` 를 호출하면 `control-loop` 로 안내됨"* | §7 | LLM 행동. "안내"의 판정 불가 | 결정적 부분만: `grep -c control-loop agent-teams/SKILL.md ≥ 1` ∧ 폐기 예고 문구 존재 (G7) |
| X5 | 수용 12 — *"README 의 파리티 문장과 매니페스트 `description` 이 **같은 약속을 말함**"* | §7 | 자연어 동치. **원리적으로 게이트 불가** — D-32 3행이 인정한 바로 그 범주인데 수용 테스트에는 그대로 남아 있다 | 게이트 불가임을 명시 + 마커 문자열 동일성으로 대체 (G12) |
| X6 | 수용 20 — *"규범 파일을 열면 frontmatter 만 보고 언제 주입되는지 **알 수 있다**"* | §9.5 | 사람의 이해도 | `tier` 선언 존재 ∧ (`tier==conditional` → `activates` 비어있지 않음) (G20) |
| X7 | 수용 31 — *"`enforce-structure` 가 … **crash 없이 스킵을 보고한다**"* | §11.4 | 에이전트 **행동**. 비결정 출력 | 결정적/비결정 2분할: 산문에 폴백 문장 존재(결정적) + eval 시나리오 1건(비결정, 임계값) (G31) |
| X8 | D-32 3행 — *"해설본 사실성 **1회 스윕**"* | §11.1, 25-26 | 범위·완료 조건 없음. 9종 × 자연어 사실성은 무한 | 스윕 대상을 **기계로 확인 가능한 주장만**으로 한정: 카운트·경로·존재하는 구조명. 나머지는 대상 밖임을 명시 (G26) |

**X3에 대한 반대 의견을 분명히 한다.** 수용 테스트 4는 W-025의 완료를 **영원히 열어 둔다** —
"일상 작업이 성립함"을 언제 판정할지 아무도 정할 수 없기 때문이다. 이 레포는
`definition-of-done`으로 "완료 선언 전 게이트 통과"를 규범화해 놓았는데, 이 항목은
그 게이트에 들어갈 수 없는 형태다. **수용 테스트에서 빼고 A 트랙의 산출물 기록으로 강등**해야
W-025가 닫힌다.

---

## 4. 숨은 의존 — 순서가 결과를 바꾸는 지점

> 특히 **게이트 신설 항목과 그 게이트가 검사할 대상을 바꾸는 항목이 같은 배치**에 있을 때.
> 아래는 전부 W-025 안에서 발생한다.

### O1 — §17(25-16, B 트랙) 이전에 8종의 `references:`가 고쳐져야 한다 【치명】

E3 참조. 25-16이 만드는 §17 검사 ①은 **첫 실행에서 10개 경로에 red**를 낸다. 그리고 그중
5개(메타 에이전트)를 고칠 작업 항목이 **아예 없다.**

추가로 **트랙이 갈린다**: 25-16은 B 트랙(`scripts/`, 버전 무변경), 고쳐야 할 대상은
`plugins/**`(C 트랙, v2.18.0). B가 먼저 머지되면 **버전 무변경 트랙이 레포를 red로 만든다.**

**필수 순서**: `25-21(+E3 추가분) → 25-16`.

---

### O2 — §16(25-14, B 트랙) 이전에 축약(25-15, C 트랙)이 끝나야 한다 【치명】

D-20의 core 예산 6,144 B는 **축약 후** 도달하는 값이다. 현재 core 6종 합은 **13,282 B**로
예산의 **216%**다. 25-14가 먼저 머지되면 `verify-done.sh`가 모든 개발자에게 red다.

여기에도 트랙 교차가 있다: **25-14 = B(버전 무변경), 25-15 = C(v2.18.0)**.

**세 가지 해법 중 택1** → 질문 Q1:
- (a) 25-14를 C 트랙으로 옮겨 25-15와 같은 커밋에 넣는다 (가장 단순)
- (b) §16을 policy 플래그로 warn→fail 승격시킨다 — `evals/policy.json`의
  `classificationCompleteEnforceFail` 관례가 이미 선례다(`01-policy.json`의
  `gates.injectionBudget.enforceFail`)
- (c) 예산을 현재값에서 시작해 배치마다 낮추는 래칫

**(b)를 권고한다.** 이 레포에 이미 있는 관례이고, "게이트를 먼저 세우되 즉시 red로 막지
않는다"는 문제를 코드 변경 없이 데이터로 푼다.

---

### O3 — 25-11(tier frontmatter)은 CHECKSUMS·MIRROR와 **같은 커밋**이어야 한다 【높음】

규범 13개 파일에 frontmatter를 추가하면 **13개 sha256이 전부 바뀐다.** §7은 집합 동등성까지
강제한다:

```
scripts/verify-done.sh:~272  (cd plugins/common/rules && $_SHA *.md | grep -v CHECKSUMS | diff -q - CHECKSUMS.sha256)
scripts/verify-done.sh:~283  ./scripts/sync-rule-mirror.sh    # MIRROR.sha256 대조
```

**§9.4가 이 둘을 나열은 했으나 "같은 커밋"이라고는 안 적혀 있다.** 워커가 frontmatter만 넣고
커밋하면 그 커밋이 red다.

**추가로 §9.4에 없는 구현 함정**: `load_rules()`는 파일을 **통째로 읽어** 주입한다
(`session-start.py:230` `content = rule_path.read_text().strip()`). frontmatter를 넣으면
`---\ntier: core\nactivates: always\n---` 가 **그대로 세션에 주입된다** — 12종 × 약 40 B ≈
**480 B의 순증**이 예산이 걸린 페이로드에 얹힌다. `load_workflow_skill()`은 frontmatter를
제거하는데(`session-start.py:277-289`) `load_rules()`는 안 한다.
**25-11의 지시서에 "frontmatter 파싱·제거를 `load_rules`에 추가"를 명시해야 한다.**

---

### O4 — 25-17(카운트 탐지, B) vs 25-12·13·23(카운트를 바꾸는 항목, C) 【중】

규범 13→12, 스킬 디렉토리 정리는 **문서의 카운트 주장을 무효화**한다. 탐지 게이트가 먼저
들어오면 아직 안 고친 주장들에 red. E9의 `docs/conventions/rules-mirror.md` 3개 숫자가
대표 사례다.

**필수 순서**: 카운트를 바꾸는 항목(C)과 탐지 전환(B)이 **한 릴리스에 함께**, 그리고 탐지
전환 커밋 안에서 기존 오기재를 전부 정정(E7).

---

### O5 — 25-26의 기록 대상이 25-19가 삭제하는 절이다 【중】

- **25-19** (D-26): CLAUDE.md의 인라인 6절을 `@docs/conventions/<file>.md` import로 치환.
  그 6절에 **"Rules have a long-form mirror — and it is checksum-guarded"** 가 포함된다
  (T1 F7이 `docs/conventions/rules-mirror.md`와의 손-복제로 확인).
- **25-26** (D-32 3행): *"`sync-rule-mirror.sh` 의 체크섬은 형식 동기화이지 사실 정확성이
  아님을 **CLAUDE.md 에** 적는다."*

25-19가 먼저면 25-26이 쓸 절이 없고, 25-26이 먼저면 25-19가 그 문장을 지운다.

**권고**: 25-26의 대상을 **`docs/conventions/rules-mirror.md`** 로 바꾼다. 그러면 import를 통해
CLAUDE.md에도 반영되고, AGENTS.md `cck2:` 블록 재생성으로 전 하네스에 전파된다 — D-26의
설계가 의도한 그대로 동작한다. (동시에 E9-2의 숫자 갱신도 같은 파일에서 처리된다.)

---

### O6 — D-24의 삭제와 메타 에이전트 `references:` 정정의 대상 충돌 【중】

E3-2 참조. 정정 대상은 삭제될 `skills/references/*` 가 아니라
`skills/multi-perspective-review/*` 다. 지시서에 **정확한 목표 경로**를 적지 않으면 워커가
삭제 예정 파일을 가리키게 고친다.

---

### O7 — 27-2(생성기) → 27-5(개명) 【중, W-027】

D-3이 *"이것이 없으면 v3.0.0 개명은 59파일 수작업"*이라고 근거는 댔으나, §5의 W-027 표에
**순서 제약으로 적히지 않았다**. 27-5는 되돌리기 비용이 가장 큰 항목이므로(외부 리스팅),
"27-2가 되돌려-FAIL까지 통과하기 전에는 27-5 착수 금지"를 명시해야 한다.

---

### O8 — 25-2(회귀 가드)와 수용 16(claude 리터럴)의 충돌 【낮음 — L2에 흡수】

25-2는 `evals/run.py`에 `~/.claude.json` 을 읽는 코드를 추가한다. 수용 테스트 16은
`run.py`의 `claude` 리터럴을 `ClaudeCodeHarness` 안으로 제한한다. 문자열 스캔으로 구현하면
충돌한다 → G16의 재작성으로 해소.

---

### 순서 요약 (W-025 내부, 위반 시 red)

```
[A 트랙: 커밋 없음 — 독립]  25-1 · 25-3 · 25-4 · 25-5 · 25-6

[C 트랙 v2.18.0]
   25-21(+E3 references 정정) ──┐
   25-11(+CHECKSUMS/MIRROR 동일 커밋) ─┤
   25-12 · 25-13 · 25-15 · 25-18(+E4) · 25-20 · 25-23(+L5 이관) · 25-25 · 25-27 ─┤
                                                                                 │
[B 트랙 버전 무변경 — 위 C 이후]                                                 ▼
   25-16(§17) · 25-14(§16, 또는 warn-first) · 25-17(+E7 정정) · 25-19 → 25-26(대상 변경)
   25-2 · 25-7 · 25-8 · 25-9 · 25-10 · 25-22 · 25-24 · 25-28  (순서 자유)
```

---

## 5. 위험 평가 — 배치별 되돌리기 비용 최대 항목과 완화책

### W-025 A 트랙 (환경) — **되돌리기 수단이 아예 없다** 【최고 위험】

**항목**: 25-1(유령 프로젝트 정리) · 25-4(유령 플러그인 기록 8건) · 25-5(설정 백업 4개 삭제) ·
25-6(permissions 축소, D-11).

**왜 최고인가**: A 트랙은 §11.2(f)가 *"레포 무관 — **커밋도 없음**"*이라고 정의한다. 즉
**버전 관리 밖에서 사용자 환경을 변형**하고, 실수를 되돌릴 산출물이 존재하지 않는다.
D-11이 *"되돌리기는 한 커밋이다"*라고 쓴 것은 **사실이 아니다** — `~/.claude/settings.json`은
레포가 아니다. 게다가 25-5는 **백업 파일 4개를 지우는 항목**이라 복원 경로를 더 좁힌다.
`settings.json`의 79%가 orca 훅 shim이라는 §1.5 관측도 위험 요인이다(다른 소유자의 생성물과
같은 파일을 편집한다).

**완화책**(전부 저비용):
1. A 트랙 착수 전 `~/.claude/settings.json`의 `permissions.allow` 42개 **원문 스냅샷**과
   `~/.claude.json` projects 키 목록을 **날짜 붙여 스크래치가 아닌 곳**(예: 배치 보고서
   본문)에 남긴다. 커밋이 없으므로 보고서가 유일한 되돌림 자산이다.
2. 25-5(백업 삭제)를 **A 트랙의 마지막**으로 옮긴다. 다른 A 항목이 끝나고 1세션 이상 정상
   동작을 확인한 뒤 지운다.
3. 25-6은 **한 번에 다 빼지 않는다.** D-11의 두 범주(프로젝트 전용 `Bash(<project>:*)` /
   광범위 쓰기 `curl`·`ssh`·`scp`·`source`·`chmod`) 중 **프로젝트 전용부터** 제거한다 —
   그쪽이 오작동 시 영향이 국소적이다.

### W-025 C 트랙 (배포물 v2.18.0) — **25-15 축약** 【높음】

**왜**: 규범 6종을 절반 이하로 깎는 것은 **판단 작업**이라 "되돌리기"가 파일 복원이 아니라
**판단의 재수행**이다. 그리고 소비자 관점에서는 이미 배포된 뒤에는 새 릴리스 없이 되돌아가지
않는다. 축약이 과했다는 것은 몇 주 뒤 행동 회귀로 나타나므로 발견도 늦다.

**완화책**:
1. **25-11(기계적·가역)과 25-15(판단·비가역)를 다른 커밋으로 분리**한다. 문제가 생겼을 때
   티어 체계는 남기고 축약만 되돌릴 수 있어야 한다.
2. 축약 전 원문은 **해설본 미러(`docs/architecture/rules/`)에 보존**한다 — 미러는 축약 대상이
   아니므로 "정본은 짧고 해설본이 길다"는 기존 구조가 그대로 안전망이 된다. **단 D-18로
   삭제되는 `tool-usage-priority`는 미러도 함께 삭제되므로 예외**(E9-1).
3. 축약 후 **eval 전량 1회 재실행 + 기준선 비교**. `evals/policy.json`의 `regenerationCadence`
   관례가 이미 "시나리오를 추가한 Stage는 그 Stage 안에서 재생성"을 규정한다 — 규범 축약은
   시나리오 추가보다 행동 영향이 크므로 같은 규율을 적용한다. **이것이 25-15의 유일한
   실증 안전망이다** (예산 게이트는 크기만 보고 행동은 안 본다).

### W-026 — **26-6 하네스 심 추출** 【높음】

**왜**: `evals/run.py`는 **모든 행동 회귀 판정의 기반**이다. 심 추출이 명령 조립을 미세하게
바꾸면 eval 결과가 조용히 달라지고, 기준선이 신뢰 불가가 된다. 되돌리기 비용은 코드가 아니라
**"그 사이 판정한 모든 결과의 신뢰"** 다.

**완화책**:
1. 추출 전후로 `--dry-run`(`evals/run.py:1383`이 이미 지원)을 전 시나리오에 돌려
   **조립된 명령 문자열의 diff가 공집합**임을 증명한다. 이것이 이 항목의 되돌려-FAIL이다.
2. L2에 따라 **세 결합점을 모두** 옮긴다. 하나만 옮기면 "중립화했다"는 잘못된 확신이 남고,
   그 확신 위에서 27-4가 README에 파리티 문장을 쓴다.
3. 기준선 재생성을 같은 배치 안에서. (`regenerationCadence` 관례)

### W-027 — **27-5 개명** 【최고 — 외부 되돌림 불가】

**왜**: 마켓플레이스 리스팅·커뮤니티 카탈로그 **새 리스팅**(D-4: 이름 변경 = 재제출)·소비자의
`enabledPlugins` 키. 이 중 어느 것도 이 레포의 커밋으로 되돌아가지 않는다. 카탈로그는
**익일 동기화**라 잘못 나간 이름이 최소 하루는 살아 있다.

**완화책**(대부분 이미 설계에 있다 — 순서만 명시하면 된다):
1. **27-1 프로브가 3개 질문 전부에 `runtime-verified` 답을 낼 때까지 27-5 착수 금지.**
   D-4가 결정했으나 §5 표에 순서로 안 적혀 있다.
2. **27-2 생성기가 되돌려-FAIL을 통과할 때까지 27-5 착수 금지**(O7).
3. D-33의 별칭 기한을 **프로브 결과 확인 후 확정**한다. D-33 자신이 *"프로브 결과에 종속"*
   이라고 적었으므로, 27-1 완료 전에는 README·공지에 기한 숫자를 **쓰지 않는다**.
4. 개명 커밋과 태그를 분리하지 않는다 — CLAUDE.md의 "Tag the commit you push as the release"
   규약대로. (과거 20개 릴리스가 태그 없이 나간 사고가 §Release Checklist에 기록돼 있다.)

### 배치 전반 — **게이트 신설 3종(§16·§17·탐지식 카운트)이 한 배치에 몰려 있다** 【중】

W-025 하나에 새 기계 게이트가 셋 들어온다. 셋 다 첫 실행에서 red를 낼 수 있고(O1·O2·O4),
red가 겹치면 **어느 게이트가 진짜 결함을 잡았는지 분간이 안 된다** — 이 레포가 CLAUDE.md에
적어둔 *"아무도 이해하지 못하는 게이트는 red가 떴을 때 무시된다"* 가 정확히 그 상황이다.

**완화책**: 셋을 **warn-first로 도입**하고(정책 플래그, O2-(b)), 같은 배치 안에서 대상을 전부
정리한 뒤 **마지막 커밋에서 fail로 승격**한다. 승격 커밋이 곧 되돌려-FAIL 증명이 된다.

---

## 6. 동의하지 않는 지점 — 명시적 반대

아래는 "보완"이 아니라 **결정 자체에 대한 반대**다. 근거를 붙였다.

### R1 — D-22 ④(도구명 허용 집합)에 반대한다

L6 참조. 외부 표면의 허용 집합을 손으로 유지하는 것은 D-23·D-32가 금지한 형태다.
잡으려는 대상은 실측 1건(`LSP`)이고, **금지 패턴 + 사용 분포**로 같은 효과를 열거 없이 얻는다.

### R2 — 수용 테스트 4(bypass off 일상 작업)에 반대한다

X3 참조. 판정 주체·기간·기준이 없어 **W-025의 완료 선언을 무기한 막는다.**
`definition-of-done` 규범과 형태가 맞지 않는다.

### R3 — 수용 테스트 27("위반 0건")에 반대한다

L10 참조. 기계적 정의로는 4건이고, 그중 2건(`facilitator`·`synthesizer`)은 고치면
multi-perspective-review가 깨질 가능성이 높다. **예외를 근거와 함께 기록**하는 형태로
바꿔야 한다.

### R4 — D-6의 "운송 부록"이 어디에 사는지 정해지지 않은 것에 반대한다

**위치**: D-6, 26-2, 수용 테스트 5.

D-6은 *"`orca` 는 배포물(`plugins/`) 안에 **0건**이다. 우연이 아니라 소비자 우선 원칙의
결과다"*라며 그 사실을 근거로 부록 분리를 정당화한다. 실측으로 그 사실은 맞다:

```
$ grep -rn "orca" plugins/ | wc -l
0
```

그런데 **26-2가 만드는 "운송 부록"에는 orca 감지 명령과 레시피가 들어간다.** 그것이
`plugins/common/skills/control-loop/` 아래에 놓이면 **D-6이 근거로 삼은 그 0건이 깨진다.**
수용 테스트 5는 `SKILL.md` **한 파일**만 검사하므로 이 위반을 잡지 못한다.

**권고**: 부록의 위치를 명시적으로 결정한다 → 질문 Q5. 내 권고는 **`docs/` 에 두고 스킬은
"운송 레시피는 레포 문서 참조"로 한 줄만** 두는 것이다. 근거: (a) D-6이 근거로 든 불변식이
유지된다 (b) 소비자에게 orca 레시피는 무의미하다 (c) 부록이 낡아도 배포물이 안 낡는다는
D-6 자신의 논지와 일치한다. 반대 논거도 인정한다 — 배포물 밖에 두면 소비자가 부록을 못 본다.
그렇다면 **수용 테스트 5의 스코프를 `control-loop/` 디렉토리 전체로 넓히지 못한다**는 사실을
문서에 적어야 한다.

### R5 — D-31의 "삭제" 결론에는 동의하나 근거 하나는 성립하지 않는다

D-31의 삭제 결정 자체는 옳다(T3 F1이 "삭제보다 대체"를 권고했으나, D-31의 반론 —
"손으로 유지하는 색인은 드리프트 원천" — 이 더 강하고 D-23과 정합적이다).

그러나 D-31이 *"부수 효과가 **결정적이다**"*라고 강조한 21→19 해소는 **L5로 성립하지 않는다**
(`references/`가 남아 20이 된다). 결정은 유지하되 **근거에서 이 문장을 빼거나, L5의 이관
작업을 추가**해야 한다. 성립하지 않는 근거를 남기면 다음 사람이 결정 전체를 의심한다.

---

## 7. 컨트롤에 묻는 질문 (5개)

> 답을 기다리는 동안 나머지 산출물(01~04)을 진행할 수 있다 —
> Q1·Q2·Q3은 `01-policy.json`·`02-stages.md`의 값에 영향이 있으므로,
> 답이 오기 전까지 해당 값은 `[unresolved]`로 두고 대안 두 개를 병기한다.

**Q1 — §16·§17 게이트를 warn-first로 도입하는가?**
O1·O2 때문에 게이트 신설과 대상 정리가 같은 배치에 있다. 선택지:
(a) 게이트 항목을 C 트랙으로 옮겨 정리와 같은 커밋 / (b) policy 플래그로 warn→fail 승격
(`classificationCompleteEnforceFail` 선례) / (c) 트랙 간 머지 순서만 못박고 게이트는 처음부터 fail.
**권고 (b).**

**Q2 — WORKFLOW 예산 2,048 B를 유지하는가, 4,096 B로 올리는가?**
E2. 실측상 두 표 제거로는 4,816 B가 남는다. (a) 예산 4,096 B로 상향 /
(b) `비신뢰 텍스트 취급` 절을 reference 티어 규범으로 이관하고 WORKFLOW엔 색인 한 줄
(보안 규율의 현저성이 내려간다 — 컨트롤 판단 필요) / (c) 다른 절을 더 깎는다.
**권고 (b), 단 보안 현저성 하락은 명시적 수용이 필요하다.**

**Q3 — `references/work-system.md`(509행)를 전면 재작성하는가, 경고 배너만 다는가?**
E4. 활성 링크 2곳이 있고 현재 `plan-task`의 Step 0-4 모델과 다른 세대다. 전면 재작성은
W-025에 큰 덩어리를 하나 더 넣는다. 대안: (a) 전면 재작성 / (b) 상단 경고 배너 + 링크
제거(스킬 본문에서 "상세" 링크를 떼면 고아가 되므로 그때 삭제 대상) / (c) 삭제하고 필요한
내용만 `plan-task/SKILL.md`에 흡수.

**Q4 — 25-26의 기록 대상을 `docs/conventions/rules-mirror.md`로 바꾸는가?**
O5. CLAUDE.md에 쓰면 25-19가 지운다.

**Q5 — `control-loop` 운송 부록은 `plugins/` 안인가 `docs/` 인가?**
R4. D-6이 근거로 삼은 "배포물 안 orca 0건" 불변식의 유지 여부가 걸린다.

---

## 부록 A — 실측 재현 로그 (전부 읽기 전용, 기준 커밋 `3f85f47`)

```bash
$ git rev-parse HEAD
3f85f47be4997e54d275218bf64ac2c81324c2bd            # 브리프 §0 확인 통과

# 컴포넌트 실측
$ find plugins/common/agents -name '*.md' | wc -l              → 33
$ find plugins/common/skills -maxdepth 2 -iname SKILL.md | wc -l → 19
$ ls plugins/common/skills | wc -l                              → 21   (19 + README.md + references/)
$ ls plugins/common/rules/*.md | wc -l                          → 13
$ ls plugins/common/skills/references/ | wc -l                  → 10
$ ls docs/architecture/rules/*.md | wc -l                       → 9    (tool-usage-priority.md 포함)
$ find evals/scenarios -mindepth 2 -maxdepth 2 -type d | wc -l  → 38
$ python3 -m pytest --collect-only 2>&1 | tail -1               → 455 (T5 §4.7 재확인)

# E1: 주입량 실측
$ python3 -c '<load_rules / load_workflow_skill 호출>'
RULES 28005 B · WORKFLOW 6057 B · 합계 34062 B

# E2: WORKFLOW 표 2개 크기
본문 6019 B / 두 표 1203 B / 제거 후 4816 B

# L1: 분류 완전성 검사의 발견원
$ sed -n '302,309p' scripts/check_eval_coverage.py     → agents 디렉토리만 rglob
$ python3 -c "import json;print(json.load(open('evals/policy.json'))['gate']['classificationCompleteEnforceFail'])" → False

# L2: run.py 하네스 결합점
$ grep -n '"claude"\|shutil.which("claude")' evals/run.py  → 1049, 1077, 1304
$ grep -c claude evals/run.py                              → 14

# E3: dangling references 전수
$ python3 -c '<frontmatter references 파싱 + 경로 존재 확인>'  → MISSING 10건 / 8파일
$ find . -path "*/skills/common/*" | wc -l                     → 0

# L10: isolation 규약 위반 전수
$ python3 -c '<tools에 Write/Edit ∧ isolation 없음>'
   facilitator · synthesizer · define-business-logic · design-user-journey  (4건)

# E9: 미러·conventions 카운트
$ sed -n '1,3p' docs/conventions/rules-mirror.md   → "(13)" "(9)" "remaining four"
$ grep -n 'cck:begin\|cck2:begin' AGENTS.md        → 7 (rules-v1.4.0) · 424 (conventions-v1.0.0)
$ wc -c AGENTS.md                                   → 23457   (상한 24576, 여유 1119 B)

# E8: 동결 기록 안의 카운트 주장
$ grep -rnE '[0-9]+ ?개' site/content/posts/*.md | head
   …:20 "169개 유닛 테스트"   …:26 "33개 정의"   …:68 "25개의 새 테스트"

# E7: 현행 site 오기재
$ grep -n '11개 시나리오\|220개 이상\|8개 이상' site/content/_index.md      → 18,19,20
$ grep -n '16 스킬\|16 Skills' site/content/about.md site/content/about.en.md → 38 / 40

# 게이트 섹션 번호 (§12 공백, 다음 빈 번호 = 16·17 확인)
$ grep -n '^hdr ' scripts/verify-done.sh
   1 2 3 3b 4 5 6 7 8 9 10 13 11 14 15        ← §12 없음 ✓, §16·§17 미사용 ✓

# D-6 불변식
$ grep -rn "orca" plugins/ | wc -l   → 0
```

## 부록 B — 감사 5종 전 발견의 처리 상태 (설계 반영 여부 전수)

| 리포트 | 발견 | 설계 반영 | 비고 |
| --- | --- | --- | --- |
| T1 F1 tool-usage-priority 충돌 | D-18 ✅ | | E9-1: 미러 파일 삭제 누락 |
| T1 F2 `AskUserQuestion` 하드코딩 | D-25 ✅ | 25-15에 편입 | |
| T1 F3 mcp-usage NotebookLM | D-19 ✅ | | |
| T1 F4 ssot TypeScript | D-19 ✅ | | X2: 완료 판정 없음 |
| T1 F5 agent-system 키워드 표 | D-18 ✅ | | 미러 §3도 대상임이 D-18에 미기재 |
| T1 F6 미러 3-Tier 허구 구조 | D-32 3행 ✅ | | X8: "1회 스윕" 범위 없음 |
| T1 F7 CLAUDE.md import 미사용 | D-26 ✅ | | O5 충돌 |
| T1 F8 Release Checklist 구식 | D-26/25-19 ✅ | | |
| T1 F9 Key Skills 표 누락 | D-26/25-19 ✅ | | |
| T2 references dangling (3종) | D-22 ✅ **부분** | | **E3: 실제 8종, 5종 미배정** |
| T2 design-database 등 phantom 위임 | D-22 ✅ | | |
| T2 generate-boilerplate DELEGATE_TO | D-28 ✅ | | |
| T2 enforce-structure 전제 파일 | D-32 4행 ✅ | | X7: 수용 31 게이트 불가 |
| T2 LSP 도구 | D-22 ④ ✅ | | **L6/R1: 기전에 반대** |
| T2 메타 5종 듀얼 모드 | D-28/26-8 ✅ | | |
| T2 isolation 누락 (2종) | D-28 ✅ **부분** | | **L10: 실제 4종** |
| T2 worktree 4줄 중복 8종 | D-27 ✅ | | |
| T2 `analyze-tech-debt` claude_setting | ❌ **미반영** | | **E5** |
| T2 `manage-api-versions` 허구 계약 | ❌ **미반영** | | **E6** |
| T3 F1 skills/README.md | D-31 ✅ | | **L5: 산술 오류** |
| T3 F2/F6 agent-creator·skill-creator | D-32 1행 ✅ | | **L7: 기전 실행 불가** |
| T3 F3 mcp-builder CLI | D-32 2행 / 25-25 ✅ | | |
| T3 F4 multi-perspective-review design-database | D-22 ✅ | | |
| T3 F5 work-system.md 구식 | D-24 ✅ **결정만** | | **E4: 작업 항목 없음** |
| T3 F7 using-claude-code-kit 두 표 | D-18 ✅ | | **E2: 예산 미달** |
| T3 F8 references/ 8종 | D-24/11.2(b) ✅ | | **L4: phase-guides 이중 처방** |
| T4 F-1 evals/README.md 서두 | D-28 5행 ✅ | | |
| T4 F-2/3/4 consensus-builder | — | 워크트리 아티팩트, §10.2가 정확히 판별 ✅ | |
| T4 §0 워크트리 낡음 | D-30 ✅ | | 이 브리프 §0이 그 규범의 첫 적용 사례 |
| T5 F-03/04 docs/superpowers | 11.2(c)/25-28 ✅ | | |
| T5 F-05~F-13 Work 문서 상태 줄 | D-29 ✅ | | 과거 4건 보존 결정 타당 |
| T5 F-14/15 site index 수치 | D-23 ✅ **기전만** | | **E7: 정정 항목 없음** |
| T5 F-16/17 about "16 스킬" | D-23 ✅ | | **E7** |
| T5 F-18 plugins README 훅 서술 | D-28 4행 ✅ | | |
| T5 F-19 블로그 DUP | 보존 ✅ | | **E8: D-23 탐지가 이것을 red로 만든다** |

**미반영 신규 2건(E5·E6) + 부분 반영 4건(E3·E4·E7 + L10) + 산술/처방 오류 3건(L4·L5·E2).**
