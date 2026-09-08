#!/usr/bin/env bash
#
# feedback.sh — feedback ledger 진입점 (Spec 3 / W-007).
#
# kit의 ./scripts 관례(work.sh와 동일)에 맞춘 래퍼. 플러그인의
# feedback_ledger.py를 repo-상대 경로로 호출하여 ${CLAUDE_PLUGIN_ROOT}
# (스킬 Bash 컨텍스트에서 set 보장 없음) 의존을 제거한다.
#
# 사용:
#   ./scripts/feedback.sh upsert <category> <severity> "<pattern...>"
#   ./scripts/feedback.sh digest [K]
#
# 읽기(digest 주입)는 session-start.py가 feedback_ledger.py를 직접 import하므로
# 플러그인/풀 모드 양쪽에서 동작한다. 쓰기(capture)는 이 래퍼로 일원화한다.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEDGER="$HERE/../plugins/common/hooks/feedback_ledger.py"
if [ ! -f "$LEDGER" ]; then
  echo "[feedback.sh] feedback_ledger.py를 찾을 수 없음: $LEDGER" >&2
  exit 0  # best-effort: 학습 루프 오류가 본 작업을 막지 않음
fi
exec python3 "$LEDGER" "$@"
