#!/usr/bin/env bash
#
# export-harness.sh — 하네스 중립 AGENTS.md 내보내기 진입점 (W-017).
#
# feedback.sh·checklist.sh와 동일한 래퍼 관례: **구현은 플러그인 안에** 두고
# (`plugins/common/hooks/export_harness.py`), 이 레포에서는 repo-상대 경로로 호출한다.
# 구현을 scripts/ 에 두면 플러그인 설치자에게는 배포되지 않아 스킬이 동작하지 않는다
# — scripts/ 는 이 레포 전용이고 배포 대상은 plugins/ 뿐이다 (consumer-first).
#
# 사용:
#   ./scripts/export-harness.sh [--check|--stdout] [--target PATH] [--plugin-root PATH]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMPL="$HERE/../plugins/common/hooks/export_harness.py"
if [ ! -f "$IMPL" ]; then
  echo "[export-harness.sh] export_harness.py를 찾을 수 없음: $IMPL" >&2
  exit 2  # SKIPPED — false-green 금지
fi
exec python3 "$IMPL" "$@"
