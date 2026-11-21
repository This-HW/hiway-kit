#!/bin/bash
# setup.sh: 새 환경 초기 셋업 (Plugin 설치 + 현재 레포 pre-commit, 전역 git 템플릿은 묻고 나서)
#
# 전역 설정은 묻지 않고 바꾸지 않는다(docs/conventions/consumer-footprint.md). 5.7.2 전에는 전역
# ruff.toml·init.templateDir·~/.claude/settings.json autoMemoryDirectory 를 묻지 않고 썼다 — 앞의 둘은
# 다른 모든 프로젝트에 닿고, 마지막은 킷과 무관한 Claude Code 동작(메모리 위치)을 바꿨다.
# D-016: 상태 추적 + 멱등성 + 외부 도구 버전 체크
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_FILE="$HOME/.claude/.setup-state.json"

# D-016: 상태 관리 함수 (ATK-002: sys.argv로 shell injection 방지)
_step_done() {
    python3 - "$1" "$STATE_FILE" <<'PYEOF'
import json, pathlib, sys
step, state_file = sys.argv[1], sys.argv[2]
p = pathlib.Path(state_file)
try:
    s = json.loads(p.read_text()) if p.exists() else {}
    sys.exit(0 if step in s.get('completed', []) else 1)
except Exception as e:
    print(f"[setup] _step_done error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}
_mark_done() {
    python3 - "$1" "$STATE_FILE" <<'PYEOF'
import json, pathlib, sys
step, state_file = sys.argv[1], sys.argv[2]
p = pathlib.Path(state_file)
try:
    p.parent.mkdir(parents=True, exist_ok=True)
    s = json.loads(p.read_text()) if p.exists() else {'completed': []}
    if step not in s['completed']:
        s['completed'].append(step)
    p.write_text(json.dumps(s, indent=2))
except Exception as e:
    print(f"[setup] _mark_done error: {e}", file=sys.stderr)
PYEOF
}

# D-016: 옵션 파서 (ATK-004: while-loop, 복합 옵션 조합 지원)
OPT_FORCE=false
OPT_STATUS=false
OPT_MIGRATE=false
OPT_UNINSTALL=false
OPT_DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)     OPT_FORCE=true; shift;;
        --status)    OPT_STATUS=true; shift;;
        --migrate)   OPT_MIGRATE=true; shift;;
        --uninstall) OPT_UNINSTALL=true; shift;;
        --dry-run)   OPT_DRY_RUN=true; shift;;
        *) echo "Unknown option: $1"; exit 1;;
    esac
done

if $OPT_DRY_RUN && ! $OPT_UNINSTALL; then
    echo "--dry-run 은 --uninstall 과 함께만 씁니다" >&2
    exit 1
fi
if $OPT_UNINSTALL && { $OPT_FORCE || $OPT_STATUS || $OPT_MIGRATE; }; then
    echo "--uninstall 은 --dry-run 외의 옵션과 함께 쓰지 않습니다" >&2
    exit 1
fi

# --uninstall: setup.sh 가 쓴 것만, 쓴 그대로일 때만 되돌린다(docs/conventions/consumer-footprint.md 쓰기 등록부).
#
# - 실행한 레포의 pre-commit — 이 체크아웃의 배포본과 **바이트가 같을 때만** 지운다. 다르면 사용자가
#   고쳤거나 다른 판이 깐 것이다 — 남기고 알린다(지우면 남의 수정을 잃는다).
# - init.templateDir — 값이 정확히 setup.sh 가 넣는 경로이고, 그 디렉토리에 setup.sh 가 넣은 것
#   (배포본과 같은 hooks/pre-commit) **밖의 파일이 없을 때만** 해제하고 사본을 지운다. 사용자 파일이
#   있거나 사본을 고쳤으면 설정도 파일도 남기고 알린다 — 설정만 풀면 남긴 파일이 아무 데도 연결되지
#   않은 채 "보존"으로 보고된다. 해제는 그 값 하나만(`--fixed-value --unset-all`) 하고, 실패해도
#   (XDG 위치·git 2.30 미만) 멈추지 않고 직접 할 명령을 알린다.
# - templateDir 로 **다른 레포에 이미 심긴** .git/hooks/pre-commit 사본은 이 스크립트가 찾을 수 없다
#   (어느 레포가 그 뒤에 만들어졌는지 기록이 없다) — 찾을 수 없다고 적고 각 레포에서 할 일을 안내한다.
# - ~/.claude/.setup-state.json — setup.sh 전용 상태라 지운다.
# - 플러그인은 지우지 않고 **명령만 안내**한다. setup.sh 가 깐 직접 마켓 설치와 사용자가 따로 깐
#   디렉토리판을 이 스크립트가 구별할 근거가 없다 — 자동으로 지우면 남의 설치까지 지울 수 있다.
if $OPT_UNINSTALL; then
    SHIPPED_HOOK="$SCRIPT_DIR/plugins/common/setup/pre-commit"
    TPL_ROOT="$HOME/.claude/git-templates"
    KEPT=0
    if $OPT_DRY_RUN; then
        DO="  (dry-run) 할 일:"
        echo "=== hiway-kit 제거 (dry-run — 아무것도 바꾸지 않습니다) ==="
    else
        DO="  ✓"
        echo "=== hiway-kit 제거 ==="
    fi

    # _remove_if_shipped <파일> <표시 이름> — 배포본과 같을 때만 지운다.
    _remove_if_shipped() {
        local target="$1" label="$2"
        if [ -L "$target" ]; then
            echo "  ⚠ $label 은 심링크라 건드리지 않습니다 — 직접 확인하세요"
            KEPT=$((KEPT + 1))
        elif [ ! -e "$target" ]; then
            echo "  - $label 없음"
        elif cmp -s "$SHIPPED_HOOK" "$target"; then
            $OPT_DRY_RUN || rm -f "$target"
            echo "$DO $label 삭제"
        else
            echo "  ⚠ $label 이 이 판의 배포본과 달라 남겨 둡니다(수정했거나 다른 판이 깐 사본)."
            printf '    필요 없으면 직접 지우세요: rm -- %q\n' "$target"
            KEPT=$((KEPT + 1))
        fi
    }

    echo "[1/4] 현재 repo pre-commit..."
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        echo "  - git 레포가 아니라 건너뜁니다"
    elif [ -n "$(git config --get core.hooksPath 2>/dev/null || true)" ]; then
        # core.hooksPath 가 있으면 git 은 .git/hooks 를 쓰지 않는다 — 그래서 setup.sh 는 설치하지 않지만,
        # hooksPath 를 켜기 **전에** 깐 사본이 남아 있을 수는 있다. 쓰이지 않는 파일이라 지우지 않고 알린다.
        echo "  - core.hooksPath 를 쓰는 레포 — git 이 .git/hooks 를 쓰지 않아 setup.sh 는 여기에 설치하지 않습니다"
        LEFT_HOOK="$(git rev-parse --git-common-dir)/hooks/pre-commit"
        if [ -e "$LEFT_HOOK" ] || [ -L "$LEFT_HOOK" ]; then
            echo "  ⚠ 쓰이지 않는 .git/hooks/pre-commit 이 남아 있습니다 — 예전에 깐 사본인지 직접 확인하세요:"
            printf '    %q\n' "$LEFT_HOOK"
            KEPT=$((KEPT + 1))
        fi
    else
        _remove_if_shipped "$(git rev-parse --git-path hooks)/pre-commit" ".git/hooks/pre-commit"
    fi

    echo "[2/4] git init.templateDir..."
    CURRENT_TPL="$(git config --global init.templateDir 2>/dev/null || true)"
    TPL_WAS_OURS=false
    if [ "$CURRENT_TPL" = "$TPL_ROOT" ]; then
        TPL_WAS_OURS=true
        TPL_HOOK="$TPL_ROOT/hooks/pre-commit"
        # setup.sh 가 넣는 것은 hooks/pre-commit 하나뿐이다. 그 밖의 항목은 사용자 것이다.
        TPL_EXTRA="$(find "$TPL_ROOT" -mindepth 1 ! -path "$TPL_ROOT/hooks" ! -path "$TPL_HOOK" 2>/dev/null | head -5 || true)"
        if [ -n "$TPL_EXTRA" ]; then
            echo "  ⚠ 템플릿 디렉토리에 setup.sh 가 넣지 않은 파일이 있어 init.templateDir 를 해제하지 않습니다"
            echo "    (해제하면 그 파일들이 새 레포에 더는 복사되지 않습니다). 예:"
            printf '%s\n' "$TPL_EXTRA" | while IFS= read -r extra; do printf '      %q\n' "$extra"; done
            echo "    정리한 뒤 다시 실행하거나, 그대로 두려면 이 안내를 무시하세요."
            KEPT=$((KEPT + 1))
        elif [ -L "$TPL_HOOK" ] || { [ -e "$TPL_HOOK" ] && ! cmp -s "$SHIPPED_HOOK" "$TPL_HOOK"; }; then
            echo "  ⚠ 템플릿 pre-commit 이 이 판의 배포본과 달라(수정했거나 다른 판·심링크) init.templateDir 도"
            echo "    해제하지 않고 둘 다 남겨 둡니다 — 설정만 풀면 남긴 사본이 아무 데도 연결되지 않습니다."
            printf '    직접 확인: %q\n' "$TPL_HOOK"
            KEPT=$((KEPT + 1))
        elif $OPT_DRY_RUN; then
            echo "$DO init.templateDir 해제 ($TPL_ROOT)"
            _remove_if_shipped "$TPL_HOOK" "템플릿 pre-commit"
        elif git config --global --fixed-value --unset-all init.templateDir "$TPL_ROOT"; then
            echo "$DO init.templateDir 해제 ($TPL_ROOT)"
            _remove_if_shipped "$TPL_HOOK" "템플릿 pre-commit"
            rmdir "$TPL_ROOT/hooks" "$TPL_ROOT" 2>/dev/null || true
        else
            # 값이 ~/.gitconfig 가 아닌 XDG 위치($XDG_CONFIG_HOME/git/config)에 있거나 git 이 2.30 미만이면
            # 여기로 온다. set -e 로 조용히 멈추지 않고, 사본도 그대로 둔다(설정이 아직 가리키고 있다).
            echo "  ⚠ init.templateDir 해제에 실패했습니다 — 템플릿 사본도 그대로 둡니다. 직접 실행하세요:"
            printf '    git config --global --fixed-value --unset-all init.templateDir %q\n' "$TPL_ROOT"
            echo "    (값이 \$XDG_CONFIG_HOME/git/config 에 있으면 그 파일에서 지우세요)"
            KEPT=$((KEPT + 1))
        fi
    elif [ -n "$CURRENT_TPL" ]; then
        echo "  - 다른 templateDir 이라 건드리지 않습니다: $CURRENT_TPL"
    else
        echo "  - 설정 없음"
    fi

    echo "[3/4] 셋업 상태 파일..."
    if [ -f "$STATE_FILE" ]; then
        $OPT_DRY_RUN || rm -f "$STATE_FILE"
        echo "$DO $STATE_FILE 삭제"
    else
        echo "  - 없음"
    fi

    echo "[4/4] 플러그인 — 자동으로 지우지 않습니다. 남길 설치를 골라 직접 실행하세요:"
    echo "    claude plugin uninstall hiway-kit@hiway-kit        # setup.sh 가 깐 설치(경로 B)"
    echo "    claude plugin marketplace remove hiway-kit         # 그 마켓에서 깐 플러그인도 함께 제거됩니다"
    echo "    claude plugin list                                 # 다른 설치(디렉토리판 등)가 남았는지 확인"
    if command -v codex >/dev/null 2>&1; then
        echo "    codex plugin remove hiway-kit@hiway-kit-marketplace  # Codex 에 설치했다면"
    fi
    if $TPL_WAS_OURS; then
        # 탐지할 수 없는 것은 탐지할 수 없다고 적는다(warning-signal.md) — templateDir 가 켜져 있던 동안
        # git init·clone 한 레포마다 사본이 들어갔지만, 그 목록은 어디에도 기록되지 않는다.
        echo ""
        echo "  ⚠ init.templateDir 가 켜져 있던 동안 만든(git init·clone) 다른 레포의 .git/hooks/pre-commit"
        echo "    사본은 이 스크립트가 찾을 수 없어 그대로 남습니다. 각 레포에서 실행하세요:"
        printf '    cd <그 레포> && %q --uninstall\n' "$SCRIPT_DIR/setup.sh"
    fi
    echo ""
    if [ "$KEPT" -gt 0 ]; then
        echo "=== 제거 끝 — 남긴 항목 ${KEPT}개(위 ⚠) ==="
    else
        echo "=== 제거 끝 ==="
    fi
    exit 0
fi

if $OPT_STATUS; then
    python3 - "$STATE_FILE" <<'PYEOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
print(p.read_text() if p.exists() else 'No setup state found')
PYEOF
    exit 0
fi

if $OPT_MIGRATE; then # D-015: dual-load 해소 — 플러그인과 **이름이 겹치는 항목만** 옮긴다
    # 프로젝트 로컬 에이전트·스킬은 킷이 권장하는 2-Tier 구조라 디렉토리째 옮기면 안 된다.
    # 판정은 session-check.py(경고와 같은 코드)가 한다 — 플러그인 이름 집합은 이 체크아웃의
    # plugins/common/ 에서 읽는다. 실행 위치(cwd)는 이주할 프로젝트다.
    CHECK_PY="$SCRIPT_DIR/plugins/common/setup/session-check.py"
    if [ ! -f "$CHECK_PY" ]; then
        echo "✗ $CHECK_PY 없음 — hiway-kit 체크아웃의 setup.sh 로 실행하세요" >&2
        exit 1
    fi
    CONFLICTS_JSON="$(python3 "$CHECK_PY" --conflicts "$PWD")"
    python3 - "$PWD/.claude" "$CONFLICTS_JSON" <<'PYEOF'
import json, os, pathlib, shutil, sys
claude = pathlib.Path(sys.argv[1])
conflicts = json.loads(sys.argv[2])
if not conflicts:
    print("✓ 플러그인과 이름이 겹치는 .claude/agents·.claude/skills 항목 없음 — 옮긴 것 없음")
    sys.exit(0)
failed = 0
for c in conflicts:
    kind_dir, _, rel = c["path"].partition("/")  # agents/x.md → agents, x.md
    src = claude / kind_dir / rel
    dst_root = claude / (kind_dir + ".bak")
    dst = dst_root / rel
    # 상대경로가 .bak 밖으로 새지 않는지 한 번 확인한다(path-containment).
    if os.path.commonpath([dst_root.resolve(), dst.resolve().parent]) != str(dst_root.resolve()):
        print(f"✗ {c['path']}: 경로가 .bak 밖을 가리켜 건너뜁니다", file=sys.stderr)
        failed += 1
        continue
    if dst.exists() or dst.is_symlink():
        print(f"✗ {c['path']}: {dst.relative_to(claude)} 가 이미 있어 건너뜁니다", file=sys.stderr)
        failed += 1
        continue
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    print(f"✓ .claude/{c['path']} → .claude/{kind_dir}.bak/{rel}  ({c['kind']} {c['name']})")
sys.exit(1 if failed else 0)
PYEOF
    exit $?
fi

if $OPT_FORCE; then rm -f "$STATE_FILE"; echo "State reset."; fi

echo "=== hiway-kit 초기 셋업 ==="

# D-016 (IM-09): 외부 도구 최소 버전 체크 (ATK-007: 실제 버전 비교 구현)
_check_version() {
    local cmd="$1" min_ver="$2"
    if ! command -v "$cmd" &>/dev/null; then
        echo "  ⚠ $cmd 미설치 — $min_ver 이상 설치 권장"
        return 1
    fi
    local cur_ver
    # `|| true`: grep 미매치/head SIGPIPE의 비정상 종료가 set -e로 스크립트를 죽이지 않도록.
    cur_ver=$("$cmd" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
    if [ -z "$cur_ver" ]; then
        echo "  ? $cmd 버전 확인 불가 (설치는 됨)"
        return 0
    fi
    # 버전 문자열을 '.' 기준으로 쪼갠다. `arr=($str)` 대신 `IFS=. read -ra`를 쓰는 이유:
    # 전자는 분할과 동시에 **글로빙**도 타서(`*` 포함 시) 예기치 않게 파일명으로 확장된다.
    local cur min
    IFS=. read -ra cur <<<"$cur_ver"
    IFS=. read -ra min <<<"$min_ver"
    for i in 0 1 2; do
        local c="${cur[$i]:-0}" m="${min[$i]:-0}"
        if (( c > m )); then echo "  ✓ $cmd $cur_ver"; return 0; fi
        if (( c < m )); then echo "  ⚠ $cmd $cur_ver < 권장 $min_ver — 업그레이드 권장"; return 1; fi
    done
    echo "  ✓ $cmd $cur_ver"
}
# `|| true`: 버전 체크는 자문(advisory)일 뿐 — 미설치/구버전이 return 1로 set -e를
# 발동시켜 설치 전체를 중단(fresh-env brick)시키지 않도록 결과를 무시한다.
_check_version "ruff" "0.4.0" || true
_check_version "gitleaks" "8.18.0" || true

# 1. Plugin 설치 (common 필수)
echo "[1/3] Plugin 설치..."
if ! _step_done "plugin-common"; then
    claude plugin marketplace add This-HW/hiway-kit 2>/dev/null || true
    claude plugin install hiway-kit@hiway-kit --scope user
    _mark_done "plugin-common"
fi
echo "  ℹ 훅(protect-sensitive, auto-format 등)은 플러그인이 자동으로 처리합니다"

# 1b. Codex 플러그인 설치 (선택 — `codex`가 PATH에 있을 때만)
#
# 침묵 조건(warning-signal.md §검토 절차 1·4): `codex`가 없으면 **아무것도 인쇄하지
# 않는다.** 대부분의 사용자에게 상시 참인 안내는 정보가 아니라 소음이고, 소음은 옆에
# 있는 진짜 경고까지 죽인다.
#
# 무단 실행 금지: `claude` 쪽과 대칭이되 **묻고 나서** 설치한다. 사용자의 전역
# `~/.codex/**`를 스크립트가 조용히 고치지 않는다. 비대화형(파이프·CI)에서는 물을 수
# 없으므로 설치하지 않고 수동 명령만 안내한다 — EOF에서 `read`가 1을 반환해 `set -e`로
# 셋업 전체가 중단되는 것도 이 분기가 막는다.
if command -v codex >/dev/null 2>&1 && ! _step_done "plugin-codex"; then
    echo "[1b/3] Codex 감지됨 — 플러그인 설치 (선택)"
    CODEX_ANSWER="n"
    if [ -t 0 ]; then
        printf "  Codex에도 hiway-kit을 설치할까요? [y/N] "
        read -r CODEX_ANSWER || CODEX_ANSWER="n"
    else
        echo "  - 비대화형 실행이라 묻지 않고 건너뜁니다"
    fi
    case "$CODEX_ANSWER" in
        [yY]*)
            codex plugin marketplace add "$SCRIPT_DIR" 2>/dev/null || true
            if codex plugin add hiway-kit@hiway-kit-marketplace; then
                _mark_done "plugin-codex"
                echo "  ✓ Codex 플러그인 설치됨"
            else
                echo "  ⚠ Codex 플러그인 설치 실패 — 수동으로 다시 시도하세요"
            fi
            ;;
        *)
            echo "  - 건너뜀. 나중에: codex plugin marketplace add $SCRIPT_DIR"
            echo "                    codex plugin add hiway-kit@hiway-kit-marketplace"
            ;;
    esac
    # 설치 여부와 무관하게 신뢰 단계를 안내한다 — 설치만으로는 훅이 돌지 않는다.
    echo "  ★ 설치 후 한 번: Codex는 훅 **신뢰**를 승인하기 전까지 훅을 조용히 건너뜁니다"
    echo "    (경고도 오류도 없습니다 — 규범이 주입된 줄 알기 쉽습니다)"
    echo "    · 대화형: 프로젝트에서 codex 세션을 한 번 열어 훅 신뢰 프롬프트를 승인"
    echo "    · codex exec: 프롬프트가 없으므로 --dangerously-bypass-hook-trust 필요"
    echo "    신뢰가 없어도 규범 자체는 AGENTS.md 진입점으로 도달합니다 — 훅은 더 나은"
    echo "    경로이지 유일한 경로가 아닙니다."
fi

# (2.7.0) 도메인 플러그인은 제거됨 — core 단일 플러그인 구성.

# 2. init.templateDir — 이후 git init·clone 하는 **모든** 레포에 pre-commit 을 심는다(선택)
#
# 다른 프로젝트까지 닿는 전역 변경이라 Codex 단계처럼 **묻고 나서** 한다. 비대화형이면 묻지 않고
# 건너뛰고 수동 명령만 안내한다. 이미 다른 templateDir 이 있으면 덮지 않는다.
echo "[2/3] git init.templateDir (선택)..."
CURRENT_TPL="$(git config --global init.templateDir 2>/dev/null || true)"
TPL_ROOT="$HOME/.claude/git-templates"
if [ "$CURRENT_TPL" = "$TPL_ROOT" ]; then
    # 예전 판이 심은 템플릿 사본은 낡았을 수 있다 — 이후 만드는 모든 레포가 그 사본을 받는다.
    TPL_HOOK="$TPL_ROOT/hooks/pre-commit"
    if [ -f "$TPL_HOOK" ] && ! cmp -s "$SCRIPT_DIR/plugins/common/setup/pre-commit" "$TPL_HOOK"; then
        if $OPT_FORCE; then
            cp "$SCRIPT_DIR/plugins/common/setup/pre-commit" "$TPL_HOOK"
            chmod 755 "$TPL_HOOK"
            echo "  ✓ 템플릿 pre-commit 갱신됨 — 이미 만든 레포의 .git/hooks 사본은 그대로입니다"
        else
            echo "  ⚠ 템플릿 pre-commit 이 이 판과 다릅니다(낡은 사본) — ./setup.sh --force 로 갱신하거나"
            echo "    끄세요: git config --global --unset init.templateDir"
        fi
    else
        echo "  - 이미 설정됨 ($TPL_ROOT). 끄려면: git config --global --unset init.templateDir"
    fi
elif [ -n "$CURRENT_TPL" ]; then
    echo "  - 다른 templateDir 이 이미 있어 건드리지 않습니다: $CURRENT_TPL"
else
    TPL_ANSWER="n"
    if [ -t 0 ]; then
        printf "  앞으로 만드는 모든 git 레포에 hiway-kit pre-commit 을 심을까요? [y/N] "
        read -r TPL_ANSWER || TPL_ANSWER="n"
    else
        echo "  - 비대화형 실행이라 묻지 않고 건너뜁니다"
    fi
    case "$TPL_ANSWER" in
        [yY]*)
            mkdir -p "$TPL_ROOT/hooks"
            cp "$SCRIPT_DIR/plugins/common/setup/pre-commit" "$TPL_ROOT/hooks/pre-commit"
            chmod 755 "$TPL_ROOT/hooks/pre-commit"
            git config --global init.templateDir "$TPL_ROOT"
            echo "  ✓ init.templateDir 설정됨. 끄려면: git config --global --unset init.templateDir"
            ;;
        *)
            echo "  - 건너뜀. 레포 하나에만 넣으려면 그 레포에서 이 스크립트를 다시 실행하세요(아래 3단계)."
            ;;
    esac
fi

# 3. 현재 repo pre-commit 설치 — 이 스크립트를 실행한 레포 하나에만
echo "[3/3] 현재 repo pre-commit 설치..."
HOOKS_PATH_CFG="$(git config --get core.hooksPath 2>/dev/null || true)"
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "  - git 레포가 아니라 건너뜁니다"
elif [ -n "$HOOKS_PATH_CFG" ]; then
    # husky 등이 core.hooksPath 를 쓰면 git 은 .git/hooks 를 보지 않는다 — 넣어도 돌지 않으면서 설치된 척한다.
    echo "  - core.hooksPath($HOOKS_PATH_CFG)를 쓰는 레포라 설치하지 않습니다(git 이 .git/hooks 를 보지 않음)."
    echo "    그 훅 관리자에서 $SCRIPT_DIR/plugins/common/setup/pre-commit 을 부르게 하세요."
else
    # --git-path: 연결된 워크트리에서도 공용 hooks 디렉토리를 가리킨다(--git-dir 은 worktrees/<이름>).
    HOOK_DIR="$(git rev-parse --git-path hooks)"
    mkdir -p "$HOOK_DIR"
    HOOK_DST="$HOOK_DIR/pre-commit"
    if [ ! -f "$HOOK_DST" ]; then
        cp "$SCRIPT_DIR/plugins/common/setup/pre-commit" "$HOOK_DST"
        chmod 755 "$HOOK_DST"
        echo "  ✓ pre-commit 설치됨"
    elif $OPT_FORCE; then
        cp "$SCRIPT_DIR/plugins/common/setup/pre-commit" "$HOOK_DST"
        chmod 755 "$HOOK_DST"
        echo "  ✓ pre-commit 강제 갱신됨"
    else
        echo "  ⚠ pre-commit 이미 존재, 스킵 (갱신하려면 --force)"
    fi
fi

echo ""
echo "=== 셋업 완료 ==="
echo "상태 확인: ./setup.sh --status"
