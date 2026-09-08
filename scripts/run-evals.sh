#!/usr/bin/env bash
#
# run-evals.sh — Agent Evals 진입점 (Spec 2 / W-B, toolkit-improvement-batch).
# evals/run.py를 repo-상대로 호출하는 얇은 래퍼(scripts/checklist.sh, feedback.sh와
# 동일한 관례).
#
# 사용:
#   ./scripts/run-evals.sh --validate                 # 오프라인 스키마 검증 (API 불필요)
#   ./scripts/run-evals.sh --dry-run                    # claude 미호출, 실행 계획만 출력
#   ./scripts/run-evals.sh [--agent X] [--scenario Y]   # 필터 실행 (API 비용 발생)
#   ./scripts/run-evals.sh --baseline                   # 결과를 evals/baseline/<date>.json 저장
#   ./scripts/run-evals.sh --compare evals/baseline/<date>.json
#
# exit code: 0=전체 pass 1=fail/후퇴/스키마오류 2=SKIPPED(claude CLI 부재)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_PY="$HERE/../evals/run.py"
if [ ! -f "$RUN_PY" ]; then
  echo "[run-evals.sh] evals/run.py를 찾을 수 없음: $RUN_PY" >&2
  exit 3
fi
exec python3 "$RUN_PY" "$@"
