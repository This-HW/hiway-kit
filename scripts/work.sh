#!/usr/bin/env bash
# scripts/work.sh — Work 상태 관리 CLI
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKS_DIR="${REPO_ROOT}/docs/works"

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [args]

Commands:
  new <title>       새 Work 아이템 생성
  list              전체 Work 목록 출력
  show <id>         Work 상세 조회 (예: W-001)
  start <id>        idea → active 전환
  next-phase <id>   현재 phase를 다음 단계로 전환
  complete <id>     active → completed 전환
  resume <id>       CLAUDE_CODE_TASK_LIST_ID 설정 후 claude 실행 (Task 영속성)

Examples:
  $(basename "$0") new "새 기능 구현"
  $(basename "$0") list
  $(basename "$0") show W-001
  $(basename "$0") start W-001
  $(basename "$0") next-phase W-001
  $(basename "$0") complete W-001
  $(basename "$0") resume W-001
EOF
  exit 1
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

iso8601() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Convert title to kebab-case slug
# Python heredoc 사용 — POSIX sed의 한글 문자 범위(가-힣) collation 오류 회피,
# 제목에 따옴표·특수문자가 있어도 shell escape 문제 없음
to_slug() {
  local title="$1"
  python3 - "$title" <<'PYEOF'
import re, sys
t = sys.argv[1].lower()
t = re.sub(r'[^\w]', '-', t)   # \w = Unicode word chars (한글 포함)
t = re.sub(r'-+', '-', t).strip('-')
print(t)
PYEOF
}

# Shared per-repo state directory — resolved once, used everywhere (경로 봉쇄 관례,
# CLAUDE.md). `git rev-parse --git-common-dir` returns a path **relative to REPO_ROOT
# in the primary checkout** (".git") but an **absolute path in a worktree**
# (실측 확인, D-40/D-41) — so it must be normalised before use, not string-compared.
# This directory is shared by every worktree of this repo and is structurally
# untracked, which is exactly what fixes the cross-worktree W-XXX collision below.
KIT_STATE_DIR=""
kit_state_dir() {
  if [[ -n "$KIT_STATE_DIR" ]]; then
    printf "%s" "$KIT_STATE_DIR"
    return 0
  fi
  local raw
  raw="$(git -C "$REPO_ROOT" rev-parse --git-common-dir 2>/dev/null)" || {
    echo "Error: ${REPO_ROOT} is not inside a git repository (--git-common-dir failed)" >&2
    exit 1
  }
  case "$raw" in
    /*) : ;;
    *) raw="${REPO_ROOT}/${raw}" ;;
  esac
  # 디렉토리 이름은 "kit" 이다 — **제품명을 넣지 않는다.** 이것은 내부 경로가 아니라
  # 프로토콜 경로이고(rules/child-marker.md·skills/child-session·child-git-guard.py·
  # feedback_ledger.py 가 같은 이름을 규범으로 참조한다), 제품명을 박으면 개명할 때마다
  # 살아있는 마커가 고아가 된다. v3.9.0 에서 구 이름을 이 중립 이름으로 옮겼다.
  KIT_STATE_DIR="$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "${raw}/kit")"
  printf "%s" "$KIT_STATE_DIR"
}

# Find the next W-XXX number by scanning all three stage dirs *and* the shared
# claim registry (kit_state_dir/claimed — see claim_work_id). The claim registry
# must be included here too: it is what lets a concurrent process in another
# worktree see a number that has been reserved but has no docs/works directory yet.
next_work_number() {
  local max="0"
  local claimed_dir
  claimed_dir="$(kit_state_dir)/claimed"
  while IFS= read -r -d '' dir; do
    local base
    base="$(basename "$dir")"
    if [[ "$base" =~ ^W-([0-9]+) ]]; then
      local n="${BASH_REMATCH[1]}"
      n=$((10#$n))  # strip leading zeros
      if (( n > max )); then max=$n; fi
    fi
  done < <(
    {
      find "$WORKS_DIR" -mindepth 2 -maxdepth 2 -type d -print0 2>/dev/null
      find "$claimed_dir" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null
    }
  )
  printf "%03d" $(( max + 1 ))
}

# Atomically claim a unique Work ID (TOCTOU 방지 — W-011, cross-worktree 방지 — D-41/25-31).
# next_work_number 계산과 디렉토리 생성 사이에 다른 프로세스가 같은 번호를
# 받을 수 있다(동시 `work.sh new`). mkdir의 원자성으로 claimed/W-XXX를
# 선점해 번호를 확정한다 — 선점 실패 시 재채번 후 재시도.
#
# 레지스트리는 `kit_state_dir`(레포의 모든 워크트리·clone이 공유하는 git-common-dir
# 하위)에 있다 — 이전에는 docs/works/.claimed 였고, 이는 워크트리별로 별도 체크아웃이라
# 동시 세션이 같은 W-XXX를 받을 수 있었다(D-41). 크로스-레포(별도 clone)는 여전히
# 이 메커니즘으로 탐지할 수 없다 — git-common-dir 자체가 레포 경계이기 때문이다.
claim_work_id() {
  local claimed_dir
  claimed_dir="$(kit_state_dir)/claimed"
  mkdir -p "$claimed_dir"
  local num
  for _ in $(seq 1 20); do
    num="$(next_work_number)"
    if mkdir "${claimed_dir}/W-${num}" 2>/dev/null; then
      printf "%s" "$num"
      return 0
    fi
    # 경합 시 재채번 전 짧은 지터 — 동시 프로세스들이 같은 번호로 몰리는 것 완화
    sleep "0.0$((RANDOM % 5 + 1))"
  done
  echo "Error: could not allocate a unique Work ID after 20 attempts (already claimed)" >&2
  exit 1
}

# Locate the directory for a given Work ID across all stage dirs
find_work_dir() {
  local id="$1"  # e.g. W-001
  local matches
  matches="$(find "$WORKS_DIR" -mindepth 2 -maxdepth 2 -type d -name "${id}-*" 2>/dev/null | sort || true)"
  if [[ -z "$matches" ]]; then
    echo "Error: Work '$id' not found under $WORKS_DIR" >&2
    exit 1
  fi
  # 동일 ID가 여러 디렉토리와 매치되면(cross-clone 중복 병합 등) 사용자에게
  # 경고하되 CLI를 브릭하지 않는다 — exit 1로 모든 하위명령을 막으면 정작 중복을
  # 정리할 complete/show조차 못 쓴다. 결정론적으로 첫 항목(정렬순)을 선택하고
  # 사용자가 수동 정리하도록 stderr로 알린다.
  if [[ "$(printf '%s\n' "$matches" | wc -l | tr -d ' ')" -gt 1 ]]; then
    echo "Warning: Work '$id'가 여러 디렉토리와 매치됩니다(중복 ID). 첫 항목을 사용합니다 — 수동 정리 권장:" >&2
    printf '  %s\n' $matches >&2
    matches="$(printf '%s\n' "$matches" | head -1)"
  fi
  echo "$matches"
}

# Locate the primary .md file inside a work directory
find_work_md() {
  local dir="$1"
  local id
  id="$(basename "$dir" | grep -oE '^W-[0-9]+')"
  find "$dir" -maxdepth 1 -name "${id}-*.md" | head -1 || true
}

# Read a frontmatter field value from a work .md file
get_field() {
  local file="$1"
  local field="$2"
  python3 - "$file" "$field" <<'PYEOF'
import sys, re
file, field = sys.argv[1], sys.argv[2]
with open(file) as f:
    content = f.read()
m = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
if not m:
    sys.exit(0)
fm = m.group(1)
pat = re.compile(r'^' + re.escape(field) + r':\s*(.+)$', re.MULTILINE)
hit = pat.search(fm)
if hit:
    val = hit.group(1).strip().strip('"').strip("'")
    print(val)
PYEOF
}

# Update (or insert) a frontmatter scalar field in a work .md file
set_field() {
  local file="$1"
  local field="$2"
  local value="$3"
  python3 - "$file" "$field" "$value" <<'PYEOF'
import sys, re

file, field, value = sys.argv[1], sys.argv[2], sys.argv[3]
with open(file) as f:
    content = f.read()

m = re.match(r'^(---\n)(.*?)(\n---)(.*)', content, re.DOTALL)
if not m:
    print(f"Error: no frontmatter found in {file}", file=sys.stderr)
    sys.exit(1)

open_fence, fm, close_fence, body = m.group(1), m.group(2), m.group(3), m.group(4)

pat = re.compile(r'^(' + re.escape(field) + r'):[ \t]*.*$', re.MULTILINE)
replacement = f'{field}: "{value}"' if ' ' in value or ':' in value else f'{field}: {value}'

if pat.search(fm):
    fm = pat.sub(replacement, fm)
else:
    fm = fm + f'\n{replacement}'

with open(file, 'w') as f:
    f.write(open_fence + fm + close_fence + body)
PYEOF
}

# Append a value to a frontmatter list field (phases_completed: [...])
append_to_list_field() {
  local file="$1"
  local field="$2"
  local item="$3"
  python3 - "$file" "$field" "$item" <<'PYEOF'
import sys, re

file, field, item = sys.argv[1], sys.argv[2], sys.argv[3]
with open(file) as f:
    content = f.read()

m = re.match(r'^(---\n)(.*?)(\n---)(.*)', content, re.DOTALL)
if not m:
    print(f"Error: no frontmatter in {file}", file=sys.stderr)
    sys.exit(1)

open_fence, fm, close_fence, body = m.group(1), m.group(2), m.group(3), m.group(4)

pat = re.compile(r'^(' + re.escape(field) + r'):[ \t]*\[(.*?)\][ \t]*$', re.MULTILINE)
hit = pat.search(fm)
if hit:
    existing = hit.group(2).strip()
    if existing:
        new_list = f'[{existing}, {item}]'
    else:
        new_list = f'[{item}]'
    fm = pat.sub(f'{field}: {new_list}', fm)
else:
    fm = fm + f'\n{field}: [{item}]'

with open(file, 'w') as f:
    f.write(open_fence + fm + close_fence + body)
PYEOF
}

# Sync the body's `> Status: ...` inline line with the frontmatter status (D-29).
# W-001~W-004 갔던 문제 — completed 후에도 본문 인라인 줄이 안 바뀌어 진행 중처럼
# 읽혔다. 과거 파일은 역사 기록이라 고치지 않는다(감사 수용 기준 5) — 이 함수는
# `cmd_complete`가 새로 만드는 전환에만 적용되고, 패턴이 없는 파일은 그대로 둔다.
sync_status_line() {
  local file="$1"
  local status="$2"
  python3 - "$file" "$status" <<'PYEOF'
import sys, re

file, status = sys.argv[1], sys.argv[2]
with open(file) as f:
    content = f.read()

new_content, n = re.subn(
    r'^(> Status:).*$', r'\1 ' + status, content, count=1, flags=re.MULTILINE
)
if n:
    with open(file, 'w') as f:
        f.write(new_content)
PYEOF
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_new() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'new' requires a title argument" >&2
    echo "Usage: $(basename "$0") new <title>" >&2
    exit 1
  fi
  local title="$*"
  local slug
  slug="$(to_slug "$title")"
  slug="${slug:-untitled}"  # 특수문자만 있는 제목이 빈 슬러그가 되는 것 방지
  local num
  num="$(claim_work_id)"  # 원자적 ID 선점 (동시 실행 시 중복 W-XXX 방지, 워크트리 간 공유 — D-41)
  local id="W-${num}"
  local claimed_dir
  claimed_dir="$(kit_state_dir)/claimed"
  # claim 이후 실패(set -e) 시 고아 claimed 항목 잔존으로 번호가 영구 소각되는 것 방지 —
  # Work 디렉토리 생성 성공 후에만 trap 해제.
  trap 'rmdir "'"${claimed_dir}/W-${num}"'" 2>/dev/null || true' EXIT
  local dir="${WORKS_DIR}/idea/${id}-${slug}"
  local now
  now="$(iso8601)"

  if [[ -d "$dir" ]]; then
    echo "Error: Directory already exists: $dir" >&2
    exit 1
  fi

  mkdir -p "$dir"
  trap - EXIT  # Work 디렉토리 확보 — claim은 이제 실제 Work가 대표하므로 trap 해제

  # Escape special characters in title to prevent heredoc injection
  local title_esc
  title_esc="${title//\\/\\\\}"
  title_esc="${title_esc//\`/\\\`}"
  title_esc="${title_esc//\$/\\\$}"

  # --- W-XXX-{slug}.md ---
  cat > "${dir}/${id}-${slug}.md" <<MDEOF
---
work_id: "${id}"
title: "${title_esc}"
status: idea
current_phase: idea
phases_completed: []
size: ""
priority: P2
tags: []
created_at: "${now}"
updated_at: "${now}"
---

# ${title_esc}

> Work ID: ${id}
> Status: idea

## 요약

## 요구사항

## 다음 단계
MDEOF

  # --- progress.md ---
  cat > "${dir}/progress.md" <<MDEOF
# Progress: ${title_esc}

> Work ID: ${id}
> Last Updated: ${now}

## Phase 진행 상황

### Planning Phase
- [ ] 규모 판단
- [ ] 요구사항 명확화
- [ ] 구현 계획 수립

### Development Phase
- [ ] 대기 중 (Planning 완료 후)

### Validation Phase
- [ ] 대기 중 (Development 완료 후)

## 체크포인트

| 날짜 | Phase | 체크포인트 | 상태 |
|------|-------|-----------|------|
MDEOF

  # --- decisions.md ---
  cat > "${dir}/decisions.md" <<MDEOF
# Decisions: ${title_esc}

> Work ID: ${id}
> Last Updated: ${now}

## 의사결정 기록
MDEOF

  # --- planning-results.md ---
  cat > "${dir}/planning-results.md" <<MDEOF
# Planning 결과: ${title_esc}

> Work ID: ${id}
> Last Updated: ${now}

## 규모 판단
## 요구사항 명확화
## 구현 계획
MDEOF

  echo "Created: ${id}"
  echo "Title  : ${title}"
  echo "Path   : ${dir}"
}

cmd_list() {
  local found=0
  for stage in idea active completed; do
    local stage_dir="${WORKS_DIR}/${stage}"
    [[ -d "$stage_dir" ]] || continue
    while IFS= read -r -d '' work_dir; do
      local base
      base="$(basename "$work_dir")"
      local id
      id="$(echo "$base" | grep -oE '^W-[0-9]+')"
      [[ -z "$id" ]] && continue
      local md
      md="$(find_work_md "$work_dir" 2>/dev/null)"
      if [[ -z "$md" ]]; then
        printf "  %-8s  %-40s  %-10s  %-4s\n" "$id" "(no md file)" "$stage" "-"
        found=1
        continue
      fi
      local title status priority
      title="$(get_field "$md" title)"
      status="$(get_field "$md" status)"
      priority="$(get_field "$md" priority)"
      printf "  %-8s  %-40s  %-10s  %-4s\n" "$id" "$title" "${status:-$stage}" "${priority:--}"
      found=1
    done < <(find "$stage_dir" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null | sort -z)
  done

  if (( found == 0 )); then
    echo "No works found under $WORKS_DIR"
  fi
}

cmd_show() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'show' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"  # normalise to uppercase
  local dir
  dir="$(find_work_dir "$id")"
  local md
  md="$(find_work_md "$dir")"
  if [[ -z "$md" ]]; then
    echo "Error: No primary .md file found in $dir" >&2
    exit 1
  fi

  # Print frontmatter + content up to and including the second H2 section
  python3 - "$md" <<'PYEOF'
import sys, re
with open(sys.argv[1]) as f:
    content = f.read()

# Extract frontmatter
fm_m = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
if fm_m:
    print('---')
    print(fm_m.group(1))
    print('---')
    rest = content[fm_m.end():]
else:
    rest = content

# Print up to (and including) the second H2 block
lines = rest.splitlines()
h2_count = 0
out = []
for line in lines:
    if line.startswith('## '):
        h2_count += 1
        if h2_count > 2:
            break
    out.append(line)

print('\n'.join(out))
PYEOF
}

cmd_start() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'start' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"
  local dir
  dir="$(find_work_dir "$id")"
  local stage
  stage="$(basename "$(dirname "$dir")")"

  if [[ "$stage" != "idea" ]]; then
    echo "Error: Work '$id' is in '$stage', not 'idea'" >&2
    exit 1
  fi

  local dest
  dest="${WORKS_DIR}/active/$(basename "$dir")"
  mv "$dir" "$dest"

  local md
  md="$(find_work_md "$dest")"
  local now
  now="$(iso8601)"

  set_field "$md" status active
  set_field "$md" started_at "$now"
  set_field "$md" updated_at "$now"

  echo "Started: $id"
  echo "Moved  : $dest"
}

cmd_next_phase() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'next-phase' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"
  local dir
  dir="$(find_work_dir "$id")"
  local md
  md="$(find_work_md "$dir")"
  local now
  now="$(iso8601)"

  local current_phase
  current_phase="$(get_field "$md" current_phase)"

  local next_phase
  case "$current_phase" in
    idea)      next_phase="planning" ;;
    planning)  next_phase="development" ;;
    development) next_phase="validation" ;;
    validation)
      echo "Error: Work '$id' is already in 'validation' (final phase). Use 'complete' to finish." >&2
      exit 1
      ;;
    *)
      echo "Error: Unknown current_phase '${current_phase}' for '$id'" >&2
      exit 1
      ;;
  esac

  append_to_list_field "$md" phases_completed "$current_phase"
  set_field "$md" current_phase "$next_phase"
  set_field "$md" updated_at "$now"

  # Append checkpoint to progress.md
  local progress_md="${dir}/progress.md"
  if [[ -f "$progress_md" ]]; then
    printf "| %s | %s → %s | Phase 전환 | 완료 |\n" \
      "$(date -u +"%Y-%m-%d")" "$current_phase" "$next_phase" >> "$progress_md"
  fi

  echo "Phase  : ${current_phase} → ${next_phase}"
  echo "Work   : $id"
}

cmd_complete() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'complete' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"
  local dir
  dir="$(find_work_dir "$id")"
  local stage
  stage="$(basename "$(dirname "$dir")")"

  if [[ "$stage" != "active" ]]; then
    echo "Error: Work '$id' is in '$stage', not 'active'" >&2
    exit 1
  fi

  local dest
  dest="${WORKS_DIR}/completed/$(basename "$dir")"
  mv "$dir" "$dest"

  local md
  md="$(find_work_md "$dest")"
  local now
  now="$(iso8601)"

  set_field "$md" status completed
  set_field "$md" completed_at "$now"
  set_field "$md" updated_at "$now"
  sync_status_line "$md" completed

  # Only append validation if not already present (e.g. added by next-phase)
  local phases
  phases="$(get_field "$md" phases_completed)"
  if [[ "$phases" != *"validation"* ]]; then
    append_to_list_field "$md" phases_completed validation
  fi

  echo "Completed: $id"
  echo "Moved    : $dest"
}

cmd_resume() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'resume' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"
  local dir
  dir="$(find_work_dir "$id")"
  local stage
  stage="$(basename "$(dirname "$dir")")"

  if [[ "$stage" != "active" ]]; then
    echo "Error: Work '$id' is in '$stage', not 'active'" >&2
    echo "Tip   : Use 'start $id' to move it to active first" >&2
    exit 1
  fi

  echo "Resuming $id with persistent task list (CLAUDE_CODE_TASK_LIST_ID=$id)"
  echo "Tasks will be preserved across sessions."
  shift
  exec env CLAUDE_CODE_TASK_LIST_ID="$id" claude "$@"
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if [[ $# -lt 1 ]]; then
  usage
fi

command="$1"
shift

case "$command" in
  new)         cmd_new "$@" ;;
  list)        cmd_list ;;
  show)        cmd_show "$@" ;;
  start)       cmd_start "$@" ;;
  next-phase)  cmd_next_phase "$@" ;;
  complete)    cmd_complete "$@" ;;
  resume)      cmd_resume "$@" ;;
  *)
    echo "Error: Unknown command '$command'" >&2
    usage
    ;;
esac
