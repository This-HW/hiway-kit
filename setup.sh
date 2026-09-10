#!/bin/bash
# setup.sh: 새 환경 초기 셋업 (전역 설정 + Plugin 설치)
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

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)   OPT_FORCE=true; shift;;
        --status)  OPT_STATUS=true; shift;;
        --migrate) OPT_MIGRATE=true; shift;;
        *) echo "Unknown option: $1"; exit 1;;
    esac
done

if $OPT_STATUS; then
    python3 - "$STATE_FILE" <<'PYEOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
print(p.read_text() if p.exists() else 'No setup state found')
PYEOF
    exit 0
fi

if $OPT_MIGRATE; then # D-015: dual-load 해소
    [ -d .claude/agents ] && mv .claude/agents .claude/agents.bak && echo "✓ .claude/agents → .claude/agents.bak"
    [ -d .claude/skills ] && mv .claude/skills .claude/skills.bak && echo "✓ .claude/skills → .claude/skills.bak"
    exit 0
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
echo "[1/5] Plugin 설치..."
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
    echo "[1b/5] Codex 감지됨 — 플러그인 설치 (선택)"
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

# 2. ruff.toml 전역 설치
echo "[2/5] ruff.toml 설치..."
RUFF_DST="$HOME/.config/ruff/ruff.toml"
if [ ! -f "$RUFF_DST" ]; then
    mkdir -p "$(dirname "$RUFF_DST")"
    cp "$SCRIPT_DIR/plugins/common/setup/ruff.toml" "$RUFF_DST"
    echo "  ✓ $RUFF_DST 설치됨"
    echo "    ℹ 전역 '폴백'입니다 — 프로젝트에 ruff.toml/pyproject.toml이 있으면 그쪽이 이깁니다."
    echo "      (전역 설정에만 의존하면 머신마다 린트 판정이 갈립니다 — 프로젝트에 설정을 두세요)"
else
    echo "  - 이미 존재, 스킵"
fi

# 3. init.templateDir 설정
echo "[3/5] git init.templateDir 설정..."
CURRENT_TPL="$(git config --global init.templateDir 2>/dev/null || true)"
if [ -z "$CURRENT_TPL" ]; then
    TPL_DIR="$HOME/.claude/git-templates/hooks"
    mkdir -p "$TPL_DIR"
    cp "$SCRIPT_DIR/plugins/common/setup/pre-commit" "$TPL_DIR/pre-commit"
    chmod 755 "$TPL_DIR/pre-commit"
    git config --global init.templateDir "$HOME/.claude/git-templates"
    echo "  ✓ init.templateDir 설정됨"
elif [ "$CURRENT_TPL" != "$HOME/.claude/git-templates" ]; then
    echo "  ⚠ 이미 다른 templateDir 설정됨: $CURRENT_TPL"
    echo "    수동으로 pre-commit을 해당 디렉토리에 복사하세요."
fi

# 4. 현재 repo pre-commit 설치
echo "[4/5] 현재 repo pre-commit 설치..."
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || true)"
if [ -n "$GIT_DIR" ]; then
    HOOK_DST="$GIT_DIR/hooks/pre-commit"
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

# 5. ~/.claude/settings.json 설정 주입
echo "[5/5] Claude Code 설정 주입..."
if ! _step_done "settings-inject"; then
SETTINGS_FILE="$HOME/.claude/settings.json"
python3 - "$SETTINGS_FILE" <<'PYEOF'
import json, pathlib, sys

settings_file = pathlib.Path(sys.argv[1])
try:
    settings = json.loads(settings_file.read_text()) if settings_file.exists() else {}
except Exception as e:
    print(f"  ⚠ settings.json 파싱 실패, 스킵: {e}", file=sys.stderr)
    sys.exit(0)

# autoMemoryDirectory (이미 설정된 경우 유지)
if "autoMemoryDirectory" not in settings:
    settings["autoMemoryDirectory"] = str(pathlib.Path.home() / ".claude/memory")

settings_file.parent.mkdir(parents=True, exist_ok=True)
settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
print("  ✓ settings.json 업데이트됨")
PYEOF
    _mark_done "settings-inject"
else
    echo "  - 이미 완료, 스킵"
fi

echo ""
echo "=== 셋업 완료 ==="
echo "상태 확인: ./setup.sh --status"
