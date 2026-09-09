# 파이프라인 보강 계획 v2

> 작성일: 2026-05-03
> v1 대비 변경: Track 1 구현 명세 6개 결함 수정 + 이중 검증 문제 해소. Track 2 보류.

---

## 범위 결정

**Track 1 (Stop hook 확장)**: 진행. 방향은 유효하고 결함은 수정 가능.
**Track 2 (Delegation Signal JSON화)**: **폐기 [판정: 2026-08-27, W-018 S4]**. 근거는 아래 "Track 2 판정" 참고.

---

## 핵심 설계 결정: Stop hook의 역할

v1 계획의 가장 큰 누락이었던 이중 검증 문제를 먼저 정의한다.

auto-dev 파이프라인은 이미 Phase 5 (통합 검증)에서 lint/test를 실행한다. Stop hook이 동일한 검증을 다시 하면:
- 성공 케이스: 불필요한 중복 실행 (비용, 시간)
- 충돌 케이스: Phase 5는 통과, Stop hook은 실패 → 어느 쪽이 권위자인가?

**역할 분리 원칙:**

| 레이어 | 담당 | 실행 시점 |
|--------|------|-----------|
| auto-dev Phase 5 | 파이프라인 내 검증 (primary) | 구현 완료 후, Claude가 응답 쓰는 도중 |
| Stop hook validator | 마지막 안전망 (safety net) | Claude 응답 완료 후 |

Stop hook은 **auto-dev 없이 직접 코딩한 경우**에만 검증을 수행한다. auto-dev가 이미 검증을 마쳤으면 Skip한다.

이 구분은 마커 파일로 구현한다: auto-dev Phase 5 완료 시 `.claude_validated` 파일을 생성하고, Stop hook은 이 파일이 있으면 검증을 건너뛴다.

---

## 구현 명세

### 파일 1: `plugins/common/hooks/stop-validator.py` (신규)

```python
#!/usr/bin/env python3
"""
Stop hook: last-resort safety net for ad-hoc coding sessions.
Skips if auto-dev pipeline already ran validation (Phase 5 marker present).

Failure taxonomy:
  lint_error    → auto-fix with ruff, re-validate. If fixed: inform Claude.
  test_failure  → structured error output, block (NOT auto-fixable)
  no_py_changes → skip entirely (no Python files modified)
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


# ── 마커 파일 경로 ───────────────────────────────────────────────
PROJECT_ROOT = Path(".").resolve()
_hash = hashlib.md5(str(PROJECT_ROOT).encode()).hexdigest()[:8]
VALIDATED_MARKER = Path(f"/tmp/.claude_validated_{_hash}")
RETRY_COUNTER    = Path(f"/tmp/.claude_stop_retries_{_hash}")
MAX_RETRIES = 2

# 검색 제외 디렉토리
EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules",
                ".mypy_cache", ".pytest_cache", "dist", "build"}


# ── 유틸 ────────────────────────────────────────────────────────
def get_retry_count() -> int:
    try:
        return int(RETRY_COUNTER.read_text().strip())
    except Exception:
        return 0


def increment_retry() -> int:
    count = get_retry_count() + 1
    RETRY_COUNTER.write_text(str(count))
    return count


def reset_retry():
    RETRY_COUNTER.unlink(missing_ok=True)


def allow(message: str = ""):
    """정상 종료: Claude Code가 stop을 허용."""
    if message:
        print(message)
    reset_retry()
    sys.exit(0)


def block(failure_type: str, reason: str, details: dict = None):
    """
    Stop을 차단: Claude Code가 Claude에게 재응답을 요청.
    stdout에 출력된 내용이 Claude의 컨텍스트에 주입된다.
    """
    payload = {
        "failure_type": failure_type,
        "reason": reason,
        "details": details or {},
        "retry_count": get_retry_count(),
        "action_required": _get_action_hint(failure_type),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(2)


def _get_action_hint(failure_type: str) -> str:
    hints = {
        "lint_error":          "남은 린트 오류를 수동으로 수정하세요.",
        "test_failure":        "실패한 테스트를 확인하고 코드를 수정하세요.",
        "max_retries_exceeded": "자동 수정 한계 초과. 수동 확인이 필요합니다.",
    }
    return hints.get(failure_type, "확인이 필요합니다.")


# ── 변경 파일 감지 ───────────────────────────────────────────────
def get_modified_py_files() -> list[str]:
    """
    수정/추가된 Python 파일 목록을 반환.
    1) git diff HEAD      — tracked 파일 중 수정된 것
    2) git diff --cached  — staged 파일
    3) git ls-files --others --exclude-standard — untracked 새 파일
    git 없는 환경이면 빈 리스트 (검증 스킵).
    """
    try:
        files: set[str] = set()

        # tracked 수정 파일
        r1 = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        files.update(f for f in r1.stdout.splitlines() if f.endswith(".py"))

        # staged 파일
        r2 = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5
        )
        files.update(f for f in r2.stdout.splitlines() if f.endswith(".py"))

        # untracked 새 파일 (git add 전 신규 생성 파일 포함)
        r3 = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=5
        )
        files.update(f for f in r3.stdout.splitlines() if f.endswith(".py"))

        return list(files)
    except Exception:
        return []


# ── 린트 ────────────────────────────────────────────────────────
def check_lint(target_files: list[str]) -> tuple[bool, str]:
    existing = [f for f in target_files if Path(f).exists()]
    if not existing:
        return True, ""
    try:
        result = subprocess.run(
            ["ruff", "check"] + existing,
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        # ruff 미설치: 검증 스킵
        return True, ""
    except subprocess.TimeoutExpired:
        return True, ""  # timeout은 통과로 처리 (블로킹 방지)


def auto_fix_lint(target_files: list[str]) -> tuple[bool, list[str], str]:
    """
    Returns: (now_passing, fixed_files, remaining_errors)
    """
    try:
        # --fix 실행 후 어떤 파일이 바뀌었는지 확인
        existing = [f for f in target_files if Path(f).exists()]
        before = {f: Path(f).read_text() for f in existing}
        subprocess.run(
            ["ruff", "check", "--fix"] + existing,
            capture_output=True, text=True, timeout=30
        )
        after = {f: Path(f).read_text() for f in existing}
        fixed_files = [f for f in existing if before.get(f) != after.get(f)]

        passed, errors = check_lint(target_files)
        return passed, fixed_files, errors
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True, [], ""


# ── 테스트 ───────────────────────────────────────────────────────
def find_test_files() -> list[str]:
    """EXCLUDE_DIRS를 제외하고 테스트 파일 탐색.
    p.parts는 절대 경로 전체를 포함하므로 relative_to(PROJECT_ROOT)로
    프로젝트 루트 기준 상대 경로에서만 필터링한다.
    """
    test_files = []
    for pattern in ("test_*.py", "*_test.py"):
        for p in PROJECT_ROOT.rglob(pattern):
            try:
                relative_parts = p.relative_to(PROJECT_ROOT).parts
            except ValueError:
                continue
            if not any(part in EXCLUDE_DIRS for part in relative_parts):
                test_files.append(str(p))
    return test_files


def check_tests() -> tuple[bool, str]:
    test_files = find_test_files()
    if not test_files:
        return True, ""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "-q", "--no-header"],
            capture_output=True, text=True, timeout=60
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        return True, ""  # pytest 미설치: 스킵
    except subprocess.TimeoutExpired:
        return False, "테스트 실행 시간 초과 (60초)"


# ── 메인 ────────────────────────────────────────────────────────
def main():
    # 1. auto-dev Phase 5 마커 확인 → 이중 검증 방지
    if VALIDATED_MARKER.exists():
        VALIDATED_MARKER.unlink(missing_ok=True)  # 소비 후 삭제
        allow("auto-dev validation marker found. Skipping stop-validator.")

    # 2. Python 파일 변경 없음 → 스킵
    modified_files = get_modified_py_files()
    if not modified_files:
        allow()

    # 3. max retries guard
    retry_count = get_retry_count()
    if retry_count >= MAX_RETRIES:
        reset_retry()
        block(
            "max_retries_exceeded",
            f"자동 수정 {MAX_RETRIES}회 시도 후에도 문제가 남아있습니다.",
            {"modified_files": modified_files},
        )

    # 4. 린트 검사
    lint_passed, lint_errors = check_lint(modified_files)
    if not lint_passed:
        fixed, fixed_files, remaining = auto_fix_lint(modified_files)
        if fixed:
            # 수정된 파일을 Claude에게 명시적으로 알림
            print(json.dumps({
                "action": "auto_fixed",
                "fixed_files": fixed_files,
                "message": f"ruff가 {len(fixed_files)}개 파일을 자동 수정했습니다. "
                           f"수정된 파일: {', '.join(fixed_files)}",
            }, ensure_ascii=False))
            # 수정 후 계속 진행 (lint 통과)
        else:
            increment_retry()
            block(
                "lint_error",
                "자동 수정 후에도 린트 오류가 남아있습니다.",
                {"errors": remaining[:2000], "files": modified_files},
            )

    # 5. 테스트 검사
    # test_failure는 자동 수정 불가 → 바로 block (재시도 카운트 증가)
    tests_passed, test_output = check_tests()
    if not tests_passed:
        increment_retry()
        block(
            "test_failure",
            "테스트가 실패했습니다. 코드를 수정하세요.",
            {"output": test_output[:3000]},
        )

    # 모든 검사 통과
    allow()


if __name__ == "__main__":
    main()
```

---

### 파일 3: `plugins/common/hooks/hooks.json` (수정)

Stop 섹션만 교체한다. 나머지 hook은 그대로 유지.

```json
"Stop": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/stop-validator.py\"",
        "timeout": 120
      }
    ]
  }
]
```

pytest 최대 실행 시간(60s) + ruff + git 명령 여유 포함해 120s로 설정한다.

---

### 파일 4: auto-dev 스킬 Phase 5 연동

**마커 생성 방식 결정:**

`auto-dev-validator.py` 별도 파일은 제거한다. 마커 생성/삭제만 하는 30줄짜리 파일을 유지할 이유가 없다.

대신 bash 한 줄로 대체한다. 단, `${CLAUDE_PLUGIN_ROOT}`는 Claude Code가 hook 실행 시 주입하는 변수라 Claude가 Bash 도구로 실행하는 스킬 컨텍스트에서는 **설정되어 있지 않을 수 있다.** 경로 의존 없이 stop-validator.py와 동일한 해시를 생성하는 python3 인라인으로 작성한다.

`plugins/common/skills/auto-dev/SKILL.md` Phase 5 완료 직후 삽입:

```markdown
### Phase 5 완료 후 필수 실행

검증이 통과되면 아래 명령을 실행한다.
이 마커가 있으면 Stop hook이 이중 검증을 건너뛴다.

\`\`\`bash
# stop-validator.py와 동일한 해시 방식으로 마커 생성
touch "/tmp/.claude_validated_$(python3 -c 'import hashlib,os; print(hashlib.md5(os.getcwd().encode()).hexdigest()[:8])')"
\`\`\`

> 이 블록을 건너뛰면 Stop hook에서 동일한 lint/test가 다시 실행된다.
```

**왜 python3 인라인인가:**
- `${CLAUDE_PLUGIN_ROOT}` 미설정 시에도 동작한다
- `md5sum` (Linux) / `md5` (macOS) 플랫폼 차이 없이 stop-validator.py와 동일한 해시를 보장한다
- 별도 파일 의존성 없음

**구현 전 확인 사항:**
실제 auto-dev 실행 맥락에서 아래 명령으로 환경변수 설정 여부를 먼저 검증한다.
```bash
echo "CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT}"
```
만약 설정되어 있다면 `python3 -c` 방식 대신 `${CLAUDE_PLUGIN_ROOT}` 경로를 써도 무방하다.

---


## 구현 순서

```
Day 1
  stop-validator.py 작성 (위 명세 기준)
  [사전 확인] 실제 auto-dev 실행 맥락에서 echo ${CLAUDE_PLUGIN_ROOT} 확인
             → 설정됨: 스킬 bash 블록에서 직접 경로 사용 가능
             → 미설정: python3 -c 인라인 방식 유지 (현재 명세)

Day 2
  단위 테스트 4케이스:
    - Python 파일 변경 없음 → 스킵 확인
    - ruff 오류 있음 → 자동 수정 후 fixed_files 출력 확인
    - pytest 실패 → block JSON 구조 확인
    - 마커 파일 존재 → Stop hook 스킵 확인 (이중 검증 방지)

Day 3
  hooks.json Stop 섹션 교체
  auto-dev 스킬 Phase 5에 마커 생성 bash 블록 추가
  통합 테스트 (auto-dev 실행 후 Stop hook 스킵 확인)

Day 4
  엣지케이스:
    - Python 파일 없는 프로젝트 (JS only)
    - ruff 미설치 환경
    - pytest 미설치 환경
    - max_retries 초과 시나리오
    - 마커 해시 충돌 (다른 프로젝트 경로가 같은 8자 해시를 가질 확률 — 무시 가능)

Day 5
  plugins/common/.claude-plugin/plugin.json 버전 bump: 2.1.0 → 2.1.1
  CLAUDE.md 업데이트
```

---

## 명시적으로 하지 않는 것

- **TypeScript/JS 린트 연동**: eslint 경로는 별도 작업으로 분리. 이번 명세는 Python(ruff)만.
- **SubagentStop에 validator 적용**: 에이전트 중간 결과 검증은 노이즈. 미적용.
- **Track 2 (Delegation Signal JSON화)**: 폐기 (아래 "Track 2 판정" 참고).

---

## Track 2 판정 (2026-05 보류 → 2026-08-27 폐기, W-018 S4)

**판정: 폐기.** 15개월이 아니라 정확히는 2026-05-03(보류 결정) → 2026-08-27(이 판정)까지
약 3.7개월 방치됐던 건이며, 근거는 세 갈래다.

1. **보류 해제 조건("실제 파싱 실패 사례")이 3개월 넘게 한 번도 성립하지 않았다.**
   `git log --all --grep="delegation.*pars"` / CHANGELOG 검색 결과, **마커가 잘못된
   형식으로 존재해서 파싱이 실패한 사례는 전무하다.** 대신 발견된 것은 전부
   **마커 자체가 통째로 누락되는 사례**다:
   - `ef858ee`(2026-07-07, W-014 T-B follow-up): implement-code에서 헤드리스 실행 시
     간헐 누락(11/11→10/11 flake) 관측. **JSON화가 아니라 시스템 프롬프트에 "모든
     응답의 마지막 블록은 예외 없이 signal"이라는 명시적 무조건 규칙을 추가**해서
     해결했다 — 이후 implement-code는 이번 배치(W-018)에서도 6/6로 안정적이다.
   - W-018 S2/S3(2026-08-26~27): 8종 관측 중 6종(write-tests·sync-docs·optimize-logic·
     explore-codebase·verify-code·implement-api)에서 같은 유형(마커 완전 누락)의
     간헐적 미준수 실측(W-022 R1 — 이후 계약 자체가 폐기됨).
   **두 사례 다 "파싱이 어려운 형식이라 실패"가 아니라 "형식과 무관하게 아예 안 씀"이다.**
   JSON으로 바꿔도 에이전트가 블록 자체를 생략하는 문제는 해결되지 않는다 — Track 2가
   고치려는 문제와 실제로 반복되는 문제가 애초에 다른 종류다.
2. **더 싸고 이미 검증된 대안이 있다.** `ef858ee`의 프롬프트 레벨 수정("예외 없이")이
   실제로 효과가 있었다(2회 연속 통과 확인, 이후 지속 안정). 50+ 파일을 JSON 스키마로
   바꾸는 대신, 같은 문구를 나머지 불안정 에이전트 정의에 추가하는 쪽이 훨씬 저비용
   해법이다 — 이건 W-021(delegation-signal-contract-review)의 몫으로 넘겼다.
3. **비용 전제도 그대로이거나 더 나쁘다.** `grep -rl "DELEGATION_SIGNAL" **/*.md`
   기준 현재 **54개 파일**이 이 마커를 참조한다(2026-05 추정 "50+"보다 늘었다 — 에이전트
   수가 그새 늘었기 때문). 게다가 CLAUDE.md의 오케스트레이션 모델이 이미 "스킬 주도
   플랫 위임"으로 바뀌어(Spec 2 / W-006), 이 신호가 실제 오케스트레이션 판단에
   쓰이는 정도가 2026-05 시점보다 줄었을 가능성이 있다(W-021이 이 부분도 다룬다) —
   비용 대비 실익이 개선되지 않았다.

**재검토 조건(폐기가 뒤집힐 경우를 대비해 명시)**: 만약 향후 마커가 **존재하되
형식이 손상되어 파싱이 실패하는** 사례가 실제로 발생하면(예: 마커 철자 변형, 중첩,
잘린 블록), 그건 이 폐기 판정의 근거를 정면으로 반박하는 사건이므로 Track 2를
다시 연다. 지금까지는 "존재 vs 부재"만 문제였지 "존재하는데 못 읽음"은 한 번도
없었다.
