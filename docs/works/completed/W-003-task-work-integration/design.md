# W-003 설계 문서 v2: Task-Work 통합 고도화

> Work ID: W-003
> 작성일: 2026-04-05 / 개정: 2026-04-06
> 상태: 설계 확정 대기
> 참고: Claude Code 공식 문서 기반 (hooks, task system, plugin rules)

---

## 0. 적대적 리뷰에서 발견된 이슈 및 해결 방향

| #   | 심각도 | 이슈                                 | 해결                                                    |
| --- | ------ | ------------------------------------ | ------------------------------------------------------- |
| 1   | 🔴     | Task ID 불일치 (T-N vs 실제 숫자 ID) | 재생성 알고리즘 설계 + description 저장                 |
| 2   | 🔴     | session-start.py 경로 오류           | utils.get_project_root() 사용                           |
| 3   | 🔴     | task-resume.md 로드 메커니즘 불명    | session-check.py RULE_FILES에 추가                      |
| 4   | 🟡     | Step 0에서 Work ID 불확실            | Work ID 확보 → ToolSearch → TaskCreate 순서 명시        |
| 5   | 🟡     | 강제성 없음                          | TaskList 선행 체크 + CLAUDE_CODE_TASK_LIST_ID 고급 옵션 |
| 6   | 🟠     | 자동 재생성 UX 문제                  | 상태 표시만 → 사용자 "재개" 의사 확인 후 실행           |
| 7   | 🟠     | Markdown 테이블 파싱 취약            | 방어적 파싱 + description 컬럼 추가                     |

---

## 1. 배경 및 목표

### 문제

Claude Code의 공식 Task 시스템(TaskCreate/TaskUpdate/blockedBy)과 Work 파일 시스템이
설계상으로는 통합되어 있지만 실제 세션에서 Task 생성이 일어나지 않는다.

**근본 원인 (공식 문서 확인):**

- TaskCreate는 deferred tool — ToolSearch로 스키마 fetch 전까지 호출 불가
- 스킬에 "항상 생성합니다"라고 써도 Claude가 스킵 가능 (강제 메커니즘 없음)
- progress.md가 Phase 단위 체크리스트라 Task 재생성에 필요한 정보 부족
- **Task는 세션 스코프** — 재시작 시 소멸, 복원 메커니즘 없음
- session-check.py의 rules 주입 방식을 몰라 task-resume 규칙 추가를 잘못 설계했음

### 목표 (A + B + C)

| 목표 | 내용                                          |
| ---- | --------------------------------------------- |
| A    | Claude가 매 세션 Task를 실제로 생성·추적      |
| B    | 독립 Task 병렬 실행 (blockedBy 의존성 그래프) |
| C    | 세션 재시작/resume 시 active Work 자동 복원   |

---

## 2. 아키텍처

### 공식 문서 기반 핵심 사실 (Claude Code Docs)

```
SessionStart hook output 형식 (공식):
  {"hookSpecificOutput": {"additionalContext": "<text>"}}
  → additionalContext 값이 Claude 컨텍스트에 자동 주입됨
  → 여러 hook의 값은 concatenate됨

rules 로드 방식 (이 kit):
  session-check.py → RULE_FILES 목록 읽기 → additionalContext로 주입
  task-resume.md를 이 목록에 추가하면 자동 로드됨

Task 시스템 (공식):
  - Task는 세션 스코프 (기본값)
  - CLAUDE_CODE_TASK_LIST_ID 환경변수로 named task list 사용 가능
    → 동일 ID로 시작한 세션들이 같은 task list 공유
    → BUT: Claude Code 프로세스 시작 전 env에 있어야 함 (hook에서 설정 불가)
  - TaskCreate subject/description/activeForm/metadata 필드 지원
```

### 두 레이어의 역할 분리

```
Work 파일 (docs/works/)              Task 시스템 (세션 런타임)
────────────────────────             ──────────────────────────
영구 저장 · Git 추적                  세션 스코프 · 재시작 시 소멸
"무엇을 / 왜 / 어디까지"               "지금 무엇을 / 어떤 순서로"
progress.md Task Map = 재생성 소스    TaskCreate = 실행 엔진
```

### 세션 생명주기

```
Claude Code 시작 (어떤 방식이든)
    │
    ├─▶ session-check.py (기존)
    │       → rules additionalContext 주입 (task-resume.md 포함)
    │
    ├─▶ session-start.py (신규)
    │       → docs/works/active/ 스캔 (get_project_root() 기반)
    │       → active Work 있으면 상태 요약 additionalContext 출력
    │       → 없으면 조용히 종료
    │
    └─▶ Claude 응답
            ├─ source=resume이거나 사용자가 작업 재개 의사 표현
            │       → progress.md Task Map 읽기
            │       → Task 재생성 알고리즘 실행
            │       → TaskCreate + TaskUpdate(addBlockedBy)
            └─ 단순 질문/조회
                    → 상태 안내 후 일반 대화 진행
```

---

## 3. 컴포넌트 설계

### 3-1. progress.md Task Map 구조 (핵심 변경)

#### 변경 이유

기존 Phase 체크리스트(- [ ] 코드 구현)로는 Task를 재생성할 수 없다.
재생성에 필요한 최소 정보: **제목, 설명, 상태, blockedBy**.

#### 신규 포맷

```markdown
## Task Map

### Planning

| Task ID | 제목            | 설명                          | 상태 | blockedBy |
| ------- | --------------- | ----------------------------- | ---- | --------- |
| T-1     | 요구사항 명확화 | clarify-requirements 에이전트 | ✅   | -         |
| T-2     | 구현 계획 수립  | plan-implementation 에이전트  | ✅   | T-1       |

### Development

| Task ID | 제목        | 설명                    | 상태 | blockedBy |
| ------- | ----------- | ----------------------- | ---- | --------- |
| T-3     | 데이터 모델 | User/Auth 스키마 정의   | ✅   | T-2       |
| T-4     | API 구현    | JWT 인증 엔드포인트 4개 | ⏳   | T-3       |
| T-5     | 프론트엔드  | 로그인 컴포넌트         | ⬜   | T-3       |
| T-6     | 테스트 작성 | unit + integration      | ⬜   | T-4, T-5  |

### Validation

| Task ID | 제목      | 설명                   | 상태 | blockedBy |
| ------- | --------- | ---------------------- | ---- | --------- |
| T-7     | 코드 리뷰 | review-code 에이전트   | ⬜   | T-6       |
| T-8     | 보안 스캔 | security-scan 에이전트 | ⬜   | T-6       |
| T-9     | 결과 통합 | 리뷰+보안 결과 통합    | ⬜   | T-7, T-8  |

## Task 업데이트 로그

- 2026-04-06T10:00Z: T-1 완료
- 2026-04-06T10:30Z: T-2 완료
- 2026-04-06T11:00Z: T-3 완료
- 2026-04-06T11:30Z: T-4 시작 (in_progress)
```

#### Task 상태 기호

| 기호 | 의미    | TaskCreate 상태 |
| ---- | ------- | --------------- |
| ✅   | 완료    | completed       |
| ⏳   | 진행 중 | in_progress     |
| ⬜   | 대기    | pending         |

---

### 3-2. Task 재생성 알고리즘 (이슈 #1 해결)

#### 문제

TaskCreate가 반환하는 실제 ID(숫자)와 progress.md의 T-N 레이블이 다르다.
새 세션에서 재생성하면 새 숫자 ID가 부여된다.

#### 해결: 완료 Task 제외 + 순서 생성 + 매핑 추적

```
입력: progress.md Task Map
  T-1 ✅, T-2 ✅, T-3 ✅ (완료)
  T-4 ⏳ blockedBy T-3
  T-5 ⬜ blockedBy T-3
  T-6 ⬜ blockedBy T-4, T-5

알고리즘:
  complete = {T-1, T-2, T-3}
  incomplete = [T-4, T-5, T-6]  ← 이것만 재생성
  id_map = {}  ← T-N → 실제 Task ID 매핑

  for task in incomplete (순서대로):
    실제 blockedBy = [
      id_map[dep] for dep in task.blockedBy
      if dep not in complete      ← 완료 Task는 제외
    ]
    new_id = TaskCreate(subject, description, metadata)
    id_map[task.id] = new_id
    if 실제 blockedBy:
      TaskUpdate(new_id, addBlockedBy=실제 blockedBy)

결과:
  T-4 → TaskCreate → id=42, blockedBy=[]    (T-3 완료라 제외)
  T-5 → TaskCreate → id=43, blockedBy=[]    (T-3 완료라 제외)
  T-6 → TaskCreate → id=44, blockedBy=[42, 43]
```

**핵심**: 완료된 Task의 blockedBy 의존성은 제거한다.
이미 완료된 것은 다시 할 필요 없으므로 블로커도 없다.

task-resume.md 규칙에 이 알고리즘을 명시한다.

---

### 3-3. plan-task 스킬 수정

**수정된 Step 순서 (이슈 #4 해결):**

```markdown
## Step 0: Work ID 확보 [건너뛰기 금지]

신규 요청이면:
./scripts/work.sh new "<제목>" → Work ID 출력 (예: W-004)
기존 Work이면:
frontmatter의 work_id 읽기

→ Work ID 확보 완료 후에만 다음 진행

## Step 1: Task 시스템 초기화 [건너뛰기 금지]

1. ToolSearch("select:TaskCreate,TaskUpdate,TaskList") — 스키마 fetch
2. TaskList 실행 → 이미 생성된 Task 있으면 Step 1 스킵 (중복 방지)
3. Task 없으면:
   TaskCreate({
   subject: "[W-XXX][Planning] 요구사항 명확화",
   description: "clarify-requirements 에이전트 실행",
   metadata: {work_id: "W-XXX", phase: "planning"}
   }) → T-1
   TaskCreate({
   subject: "[W-XXX][Planning] 구현 계획 수립",
   description: "plan-implementation 에이전트 실행",
   metadata: {work_id: "W-XXX", phase: "planning"}
   }) → T-2
   TaskUpdate(T-2, addBlockedBy=[T-1])
4. progress.md Task Map 섹션 초기화 (description 포함)

## Step 2-N: 기존 단계 (요구사항 명확화, 구현 계획)

각 Step 완료 시 의무:

- TaskUpdate(task_id, status: "completed")
- progress.md Task Map 해당 행 ✅로 갱신
- Task 업데이트 로그에 완료 시각 기록
- Work frontmatter updated_at 갱신
```

---

### 3-4. auto-dev 스킬 수정

```markdown
## Step 0: Work 컨텍스트 + Task 시스템 초기화 [건너뛰기 금지]

1. Work ID 확보 (plan-task와 동일)
2. ToolSearch("select:TaskCreate,TaskUpdate,TaskList")
3. TaskList → 기존 Task 있으면 상태 확인 후 재개 (재생성 스킵)
4. Task 없으면:
   a. planning-results.md 구현 계획 항목 분석
   b. explore-codebase 직접 탐색 (에이전트 위임 아님)
   → 이미 구현된 파일/함수 확인 → 해당 항목 ✅ 마킹
   c. 미완료 항목만 TaskCreate (의존성 분석 후)
   d. blockedBy 없는 Task 2개 이상 → Agent 동시 dispatch
5. progress.md Task Map 생성/갱신

## 병렬 실행 원칙

blockedBy 없는 Task가 2개 이상이면:
Agent(task_A) ─┐
Agent(task_B) ─┼─ 동일 응답에서 동시 dispatch
Agent(task_C) ─┘

Validation Phase: T-review + T-security 항상 병렬

## Task 완료 시 (매번 반드시)

1. TaskUpdate(id, status: "completed")
2. progress.md Task Map: 해당 행 상태 ✅로 수정
3. Task 업데이트 로그 기록
4. TaskList로 unblocked Task 확인 → 즉시 실행
```

---

### 3-5. session-start.py (신규 hook) — 이슈 #2, #6, #7 해결

`plugins/common/hooks/session-start.py`:

```python
#!/usr/bin/env python3
"""
SessionStart hook: active Work 상태를 additionalContext로 출력.
active Work가 없거나 docs/works/가 없으면 아무것도 출력하지 않음.

공식 output 형식:
  {"hookSpecificOutput": {"additionalContext": "<text>"}}
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# 이슈 #2 해결: utils.py의 get_project_root() 사용 (플러그인 설치 위치 무관)
HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
try:
    from utils import get_project_root
except ImportError:
    def get_project_root():
        """Fallback: git toplevel."""
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True
        )
        return result.stdout.strip() if result.returncode == 0 else os.getcwd()


def parse_frontmatter(filepath: Path) -> dict:
    """Work 파일 YAML frontmatter 파싱 (외부 의존성 없음)."""
    fm = {}
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except Exception:
        return fm
    if not lines or lines[0].strip() != "---":
        return fm
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def parse_task_map(progress_path: Path) -> list[dict]:
    """
    progress.md Task Map 파싱.
    이슈 #7 해결: 방어적 파싱 — 공백 변화, 컬럼 너비 변화에 강건함.
    """
    tasks = []
    if not progress_path.exists():
        return tasks

    try:
        lines = progress_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return tasks

    in_task_map = False
    header_found = False

    for line in lines:
        stripped = line.strip()

        # Task Map 섹션 진입
        if stripped == "## Task Map":
            in_task_map = True
            continue

        # 다른 ## 섹션 진입 시 종료
        if in_task_map and stripped.startswith("## ") and stripped != "## Task Map":
            break

        if not in_task_map or not stripped.startswith("|"):
            continue

        # 헤더 행 감지 (Task ID 컬럼 포함)
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not header_found:
            if any("Task ID" in c for c in cells):
                header_found = True
            continue  # 헤더 또는 구분선 스킵

        # 구분선 스킵 (---|---|...)
        if all(set(c.replace("-", "").replace(":", "").strip()) <= {""} for c in cells):
            continue

        if len(cells) < 4:
            continue

        tasks.append({
            "id": cells[0],
            "title": cells[1],
            "desc": cells[2] if len(cells) > 4 else "",
            "status": cells[-2].strip() if len(cells) > 4 else cells[2].strip(),
            "blocked_by": cells[-1].strip(),
        })

    return tasks


def summarize_work(work_dir: Path) -> "str | None":  # Python 3.9 compat: use Optional[str] in actual impl
    """Work 하나의 요약 문자열 생성."""
    md_files = sorted(work_dir.glob("W-*.md"))
    if not md_files:
        return None

    fm = parse_frontmatter(md_files[0])
    work_id = fm.get("work_id", work_dir.name)
    title = fm.get("title", work_dir.name)
    phase = fm.get("current_phase", "?")

    tasks = parse_task_map(work_dir / "progress.md")
    done = sum(1 for t in tasks if "✅" in t["status"])
    total = len(tasks)

    incomplete = [t for t in tasks if "⬜" in t["status"] or "⏳" in t["status"]]
    in_progress = [t for t in incomplete if "⏳" in t["status"]]
    pending_unblocked = [
        t for t in incomplete
        if "⬜" in t["status"]
        and all(
            any("✅" in ot["status"] for ot in tasks if ot["id"] == dep.strip())
            for dep in t["blocked_by"].split(",")
            if dep.strip() and dep.strip() != "-"
        )
    ]

    lines = [f"[{work_id}] {title}"]
    lines.append(f"  Phase: {phase} | 완료: {done}/{total} Tasks")

    if in_progress:
        lines.append("  진행 중:")
        for t in in_progress[:2]:
            lines.append(f"    ⏳ {t['id']}: {t['title']}")

    if pending_unblocked:
        lines.append("  실행 가능 (블록 없음):")
        for t in pending_unblocked[:3]:
            lines.append(f"    ⬜ {t['id']}: {t['title']}")

    return "\n".join(lines)


def main():
    project_root = Path(get_project_root())
    works_active = project_root / "docs" / "works" / "active"

    if not works_active.exists():
        return

    active_dirs = sorted(d for d in works_active.iterdir() if d.is_dir())
    if not active_dirs:
        return

    summaries = []
    for work_dir in active_dirs:
        summary = summarize_work(work_dir)
        if summary:
            summaries.append(summary)

    if not summaries:
        return

    # 이슈 #6 해결: 상태 표시만 — 사용자가 재개 의사를 표현할 때까지 Task 재생성 안 함
    context = (
        "=== ACTIVE WORK ===\n"
        + "\n\n".join(summaries)
        + "\n\n"
        + "작업 재개 시 progress.md Task Map을 읽고 Task 재생성 알고리즘을 실행하세요.\n"
        + "=== END ACTIVE WORK ==="
    )

    # 공식 output 형식 (이슈 #2 해결)
    print(json.dumps({
        "hookSpecificOutput": {
            "additionalContext": context
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # SessionStart는 fail-open — 오류가 세션을 막으면 안 됨
        print(f"[claude-code-kit] session-start warning: {e}", file=sys.stderr)
    sys.exit(0)
```

---

### 3-6. hooks.json 수정

기존 SessionStart 항목에 session-start.py 추가:

```json
"SessionStart": [
  {
    "matcher": "startup|clear|compact",
    "hooks": [
      {
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/setup/session-check.py\"",
        "async": false
      },
      {
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/session-start.py\"",
        "async": false
      }
    ]
  }
]
```

> `additionalContext` 값은 여러 hook에서 concatenate됨 (공식 문서 확인).
> session-check.py의 rules + session-start.py의 work 상태가 합쳐져 Claude에게 전달된다.

---

### 3-7. session-check.py 수정 — 이슈 #3 해결

`task-resume.md`를 `RULE_FILES` 목록에 추가:

```python
RULE_FILES = [
    "agent-system.md",
    "tool-usage-priority.md",
    "ssot.md",
    "mcp-usage.md",
    "code-quality.md",
    "task-resume.md",   # ← 신규 추가
]
```

이렇게 하면 `plugins/common/rules/task-resume.md`가 매 세션 시작 시
`<claude-code-kit-rules>` 블록에 포함되어 Claude에게 주입된다.

---

### 3-8. task-resume.md 규칙 파일 (신규) — 이슈 #6 개선

`plugins/common/rules/task-resume.md` 파일 내용:

---

**# Task 재생성 규칙**

**트리거 조건**

세션 컨텍스트에 `=== ACTIVE WORK ===`가 있을 때:

1. 사용자가 작업 재개를 명시하면 (예: "계속해줘", "재개", "W-XXX 작업해줘")
   → Task 재생성 알고리즘 즉시 실행
2. 단순 질문/조회이면
   → "W-XXX 작업이 진행 중입니다. 재개할까요?" 안내 후 대기

자동으로 Task를 생성하거나 코드를 수정하지 않는다.

**Task 재생성 알고리즘**

progress.md Task Map을 읽고:

1. `complete` = ✅ 상태인 Task ID 집합
2. `incomplete` = ⬜·⏳ 상태인 Task 목록 (순서 유지)
3. `id_map = {}` ← T-N → 실제 TaskCreate ID 매핑
4. incomplete를 순서대로 처리:
   - `실제_blockedBy` = incomplete 중 아직 미완료인 dep의 id_map 값
   - `new_id` = TaskCreate(subject=`[W-XXX][Phase] 제목`, description=task.desc, metadata={work_id, phase})
   - `id_map[task.id]` = new_id
   - 실제\_blockedBy 있으면: TaskUpdate(new_id, addBlockedBy=실제\_blockedBy)
5. ⏳이었던 Task → TaskUpdate(new_id, status="in_progress")
6. blockedBy 없는 Task부터 실행 시작

**Task 생성 규칙**

- subject: `[W-XXX][Phase] 제목` 형식
- metadata: `{"work_id": "W-XXX", "phase": "planning|development|validation"}`
- 완료된 Task는 절대 재생성하지 않음

---

---

### 3-9. work.sh 버그 수정 — 이슈 (추가)

`to_slug` 함수의 sed 한글 범위 오류 수정:

```bash
# 현재 (버그: POSIX sed에서 가-힣 collation 오류)
to_slug() {
  echo "$1" | tr '[:upper:]' '[:lower:]' \
    | sed 's/[^a-z0-9가-힣]/-/g' \   # ← 오류
    | sed 's/-\{2,\}/-/g' \
    | sed 's/^-//;s/-$//'
}

# 수정: Python으로 위임 (utils.py 패턴과 일관성 유지)
to_slug() {
  local title="$1"
  python3 - "$title" <<'PYEOF'
import re, sys
t = sys.argv[1].lower()
# \w는 Unicode word chars (한글 포함), 나머지는 하이픈으로
t = re.sub(r'[^\w]', '-', t)
t = re.sub(r'-+', '-', t).strip('-')
print(t)
PYEOF
}
```

> `python3 -c "..." "$1"` 대신 heredoc 사용 → 제목에 따옴표가 있어도 shell escape 문제 없음.

---

### 3-10. 고급 옵션: CLAUDE_CODE_TASK_LIST_ID

이슈 #5(강제성)의 근본 해결책. Task를 세션 간 실제로 유지하려면:

```bash
# Claude Code 시작 시 env var 설정
CLAUDE_CODE_TASK_LIST_ID=W-003 claude

# 또는 alias로 등록
alias work-resume='CLAUDE_CODE_TASK_LIST_ID=$(basename $(ls -d docs/works/active/W-* 2>/dev/null | head -1)) claude'
```

이 방법을 쓰면:

- 이전 세션의 Task가 `~/.claude/tasks/W-003/`에 그대로 남아있음
- 재생성 알고리즘 불필요
- TaskList로 즉시 이전 상태 확인 가능

**한계**: Claude Code 시작 전에 env var를 설정해야 함. hook에서는 설정 불가.
work.sh에 `resume` 명령을 추가해 wrapper를 제공하는 것이 UX상 최선.

```bash
# work.sh resume W-003
cmd_resume() {
  local id="$1"
  local work_dir
  work_dir=$(find "$WORKS_DIR/active" -maxdepth 1 -type d -name "${id}-*" | head -1)
  if [ -z "$work_dir" ]; then
    echo "❌ Active work $id not found" >&2; exit 1
  fi
  echo "✅ Resuming $id with persistent task list"
  exec env CLAUDE_CODE_TASK_LIST_ID="$id" claude "$@"
}
```

---

## 4. 데이터 흐름

### 최초 Work 시작 (plan-task)

```
/plan-task 새 기능
  → Step 0: work.sh new → W-004 생성
  → Step 1: ToolSearch(TaskCreate) → TaskList(비어있음 확인)
  → TaskCreate T-1 (요구사항 명확화)
  → TaskCreate T-2 (구현 계획), TaskUpdate T-2 addBlockedBy=[T-1]
  → progress.md Task Map 초기화 (description 포함)
  → T-1 실행: clarify-requirements → 완료
  → TaskUpdate(T-1, completed), progress.md ✅, 로그 기록
  → T-2 unblocked → 실행
  → TaskUpdate(T-2, completed), progress.md ✅
  → "Planning 완료. 다음: /auto-dev W-004"
```

### 세션 재시작 후 재개

```
새 세션 시작
  → session-check.py: rules 주입 (task-resume.md 포함)
  → session-start.py: docs/works/active/W-004/ 발견
       additionalContext:
         "=== ACTIVE WORK ===
          [W-004] 새 기능
            Phase: development | 완료: 3/8 Tasks
            진행 중: ⏳ T-4: API 구현
            실행 가능: ⬜ T-5: 프론트엔드
          작업 재개 시 progress.md Task Map 읽고 Task 재생성 알고리즘 실행
          === END ACTIVE WORK ==="

사용자: "계속해줘"
  → task-resume.md 규칙 발동
  → progress.md Task Map 읽기
  → Task 재생성 알고리즘 실행:
      complete = {T-1, T-2, T-3}
      T-4(⏳, blockedBy T-3✅) → TaskCreate(T-4), blockedBy=[], id=51
      T-5(⬜, blockedBy T-3✅) → TaskCreate(T-5), blockedBy=[], id=52
      T-6(⬜, blockedBy T-4,T-5) → TaskCreate(T-6), addBlockedBy=[51,52], id=53
      ...
  → T-4 in_progress → 재개
```

### Task 완료 시 (매번)

```
Task 완료
  → TaskUpdate(id, "completed")
  → progress.md Task Map: 해당 행 ✅
  → 로그: "2026-04-06T11:00Z: T-4 완료"
  → Work frontmatter updated_at 갱신
  → TaskList → unblocked Task 확인
  → blockedBy 없는 Task 2개 이상 → Agent 동시 dispatch
```

---

## 5. 변경 파일 목록

| 파일                                              | 변경 종류 | 주요 내용                                            |
| ------------------------------------------------- | --------- | ---------------------------------------------------- |
| `plugins/common/skills/plan-task/skill.md`        | 수정      | Step 순서 재정립 (Work ID 먼저), TaskList 선행 체크  |
| `plugins/common/skills/auto-dev/skill.md`         | 수정      | Step 0 하드게이트, 병렬 dispatch, 소스코드 직접 탐색 |
| `plugins/common/skills/references/work-system.md` | 수정      | progress.md Task Map 포맷 (description 컬럼 추가)    |
| `plugins/common/hooks/session-start.py`           | 신규      | active Work 상태 additionalContext 출력              |
| `plugins/common/hooks/hooks.json`                 | 수정      | session-start.py SessionStart 등록                   |
| `plugins/common/setup/session-check.py`           | 수정      | RULE_FILES에 task-resume.md 추가                     |
| `plugins/common/rules/task-resume.md`             | 신규      | Task 재생성 알고리즘 규칙                            |
| `scripts/work.sh`                                 | 수정      | to_slug 한글 버그 수정, resume 명령 추가             |

---

## 6. 구현 순서 (Task 의존성)

```
T-1: work.sh 버그 수정 + resume 명령        ← 독립
T-2: progress.md Task Map 포맷 확정          ← 독립
T-3: work-system.md 업데이트                 ← blockedBy T-2
T-4: plan-task 스킬 수정                     ← blockedBy T-2
T-5: auto-dev 스킬 수정                      ← blockedBy T-2
T-6: task-resume.md 규칙 파일 작성           ← blockedBy T-2
T-7: session-start.py 작성                   ← blockedBy T-2
T-8: session-check.py 수정 (RULE_FILES)      ← blockedBy T-6
T-9: hooks.json 수정                         ← blockedBy T-7
T-10: 통합 테스트 (전체 흐름 검증)           ← blockedBy T-1,T-3,T-4,T-5,T-8,T-9
```

**병렬 가능:**

- T-1, T-2 동시 실행
- T-2 완료 후 T-3, T-4, T-5, T-6, T-7 동시 실행
- T-6 완료 후 T-8 / T-7 완료 후 T-9
- 전체 완료 후 T-10

---

## 7. 성공 기준

- [ ] `work.sh new "한글 제목"` 정상 동작
- [ ] `work.sh resume W-XXX` 실행 시 CLAUDE_CODE_TASK_LIST_ID 설정하여 claude 실행
- [ ] `/plan-task` 실행 시 항상 TaskCreate 2개 + blockedBy 생성됨
- [ ] progress.md Task Map에 description 컬럼 포함
- [ ] `/auto-dev` 실행 시 Task 그래프 + 병렬 dispatch 동작
- [ ] Task 완료 시마다 progress.md Task Map + 로그 자동 업데이트
- [ ] Claude Code 재시작 시 active Work 상태 자동 출력 (additionalContext)
- [ ] "계속해줘" 발화 시 Task 재생성 알고리즘 정확히 동작
- [ ] 재생성 시 완료 Task blockedBy 의존성 올바르게 제거됨
