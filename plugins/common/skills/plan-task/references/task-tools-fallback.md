# Task 도구 부재 시 대체 경로 (fail-open) — 단일 소스

> 이 문서는 `brainstorming` · `plan-task` · `auto-dev`가 **공통으로 참조**한다.
> 같은 내용을 각 스킬에 복제하지 않는다 — 복제된 계약은 반드시 드리프트한다(F-023).

## 문제 (F-038)

세 스킬 모두 진입 직후 `ToolSearch("select:TaskCreate,TaskUpdate,TaskList")`로 네이티브
Task 도구를 로드하고, 그 단계는 `[건너뛰기 금지]`로 표시돼 있다. 그런데 **Task 계열
도구는 모든 호스트/세션에 있는 것이 아니다.** 실측(2026-08-22 세션)에서
`ToolSearch`가 `No matching deferred tools found`를 반환했다.

`[건너뛰기 금지]`를 문자 그대로 지키면 파이프라인이 **거기서 멈춘다.** 특정 네이티브
도구의 존재를 전제하는 필수 단계는 consumer-first 위반이다 — 이 kit는 설치되는
플러그인이지 이 레포 전용 도구가 아니다.

## 규율

**Task 도구 로드는 시도하되, 부재를 실패로 취급하지 않는다.**

```
ToolSearch("select:TaskCreate,TaskUpdate,TaskList")
  ├─ 도구 반환됨   → 원래 절차대로 TaskCreate/TaskUpdate 사용
  └─ 부재/실패     → 아래 대체 경로. 사용자에게 한 줄 고지 후 **계속 진행**
```

### 대체 경로: durable checklist

> **경로 주의 (consumer-first)**: `./scripts/checklist.sh`는 **이 kit 레포에만** 있는
> 래퍼다. 플러그인으로 설치한 프로젝트에는 `scripts/`가 없다. 구현은 플러그인 안에
> 있으므로 그쪽을 직접 부른다:
>
> ```bash
> CL="${CLAUDE_PLUGIN_ROOT:-}/hooks/checklist.py"
> [ -f "$CL" ] || CL=$(ls -1 ~/.claude/plugins/cache/*/*/*/hooks/checklist.py 2>/dev/null | sort -V | tail -1)
> [ -f "$CL" ] && python3 "$CL" show <work_dir>
> ```
>
> 둘 다 못 찾으면 아래 "Work 시스템도 없는 경우"의 대화창 추적으로 내려간다.


kit에는 이미 같은 목적의 **기계 검증형** 추적 장치가 있다. Task 도구가 없을 때는
이쪽을 쓴다 (오히려 verify 명령으로 증명되므로 더 강하다):

```bash
# 항목 정의 — id/description/acceptance/verify 필수
./scripts/checklist.sh init <work_dir> '[{"id":"C1","description":"...","acceptance":"...","verify":"<셸 명령>"}]'

./scripts/checklist.sh show   <work_dir>   # 현황
./scripts/checklist.sh pass   <work_dir> C1  # verify 실행 → exit 0일 때만 완료 전환
./scripts/checklist.sh status <work_dir>   # 0=전부완료 1=미완 3=원장없음
./scripts/checklist.sh verify <work_dir>   # 전 항목 재증명
```

`verify`는 **셸 명령**이어야 한다. "확인했다"는 완료 전환의 근거가 아니다
(definition-of-done: 완료는 판단이 아니라 명령의 출력).

### Work 시스템도 없는 경우 (fallback 모드)

`docs/works/` 자체가 없으면 checklist도 걸 곳이 없다. 그때는 **대화창에 진행 표를
유지**하고, 각 항목의 완료 근거로 실행한 명령과 그 출력을 남긴다. 추적 수단이 없다는
이유로 게이트를 면제하지 않는다.

## 금지

- Task 도구 부재를 이유로 파이프라인을 중단하는 것
- 부재를 조용히 무시하고 **아무 추적 없이** 진행하는 것 (둘 다 결함이다)
- checklist 항목의 `verify`에 `true` 같은 무조건 통과 명령을 넣는 것 — 게이트 착시(F-018)
- **완료 게이트 자체를 항목으로 넣는 것** — `verify-done.sh §8`이 "active Work의 checklist
  전항목 완료"를 요구하므로, `verify: scripts/verify-done.sh` 항목은 자기참조 데드락이 된다
  (게이트가 그 항목을 기다리고, 그 항목이 게이트를 기다린다). 게이트는 checklist **밖**의
  마지막 단계다.
