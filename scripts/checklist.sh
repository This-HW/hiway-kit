#!/usr/bin/env bash
#
# checklist.sh — Durable Executor Checklist 진입점 (W-013).
# feedback.sh와 동일한 ./scripts 래퍼 관례. 플러그인 checklist.py를 repo-상대로 호출.
#
# 사용:
#   ./scripts/checklist.sh init   <work_dir> '<json-array>'   # 또는 stdin
#   ./scripts/checklist.sh show   <work_dir>
#   ./scripts/checklist.sh status <work_dir>                   # 원장 조회: 0=완료 1=미완 3=없음
#   ./scripts/checklist.sh verify <work_dir>                   # 전 항목 verify 재실행(재증명)
#   ./scripts/checklist.sh pass   <work_dir> <id>              # verify 실행 후 통과 시 flip
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CL="$HERE/../plugins/common/hooks/checklist.py"
if [ ! -f "$CL" ]; then
  echo "[checklist.sh] checklist.py를 찾을 수 없음: $CL" >&2
  exit 3
fi
exec python3 "$CL" "$@"
