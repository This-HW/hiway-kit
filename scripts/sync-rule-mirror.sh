#!/usr/bin/env bash
#
# sync-rule-mirror.sh — 룰 해설본 미러의 동기화 검사/재생성 **단일 소스**
#
# `docs/architecture/rules/`(9개)는 `plugins/common/rules/`(주입 룰)의 **장문 해설본**이다
# (W-004에서 신설). 주입 룰은 세션마다 주입되므로 압축돼 있고, 해설본은 표·예시로 푼다.
#
# 문제: 둘을 잇는 장치가 없어서 조용히 어긋난다. 실제로 2026-08-17 감사에서 3건이
# 드리프트해 있었고, 그중 planning-check 해설본은 "Notion/Figma MCP를 순서대로 검색"이라
# 적어 **MCP 설치를 전제**했다 — 이 레포의 consumer-first north-star와 정면으로 모순.
# 아무도 몰랐다는 게 핵심이라, rules CHECKSUMS와 같은 방식으로 기계화한다.
#
# 매니페스트는 해설본이 "마지막으로 반영한 주입 룰의 sha256"을 기록한다. 주입 룰을
# 고치면 해시가 달라져 FAIL → 해설본을 확인(필요시 수정)한 뒤 --regenerate 로 갱신한다.
# 재생성은 **의식적인 행위**여야 한다 — 자동 갱신하면 검사가 무의미해진다.
#
# 사용: scripts/sync-rule-mirror.sh              # 검사 (0=동기, 1=드리프트)
#       scripts/sync-rule-mirror.sh --regenerate # 매니페스트 갱신
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 1

MIRROR_DIR="docs/architecture/rules"
SRC_DIR="plugins/common/rules"
MANIFEST="$MIRROR_DIR/MIRROR.sha256"

if command -v shasum >/dev/null 2>&1; then SHA="shasum -a 256"
elif command -v sha256sum >/dev/null 2>&1; then SHA="sha256sum"
else echo "해시 도구 부재(shasum/sha256sum) — 검증 불가" >&2; exit 2; fi

[ -d "$MIRROR_DIR" ] || { echo "미러 디렉토리 없음: $MIRROR_DIR" >&2; exit 2; }

_header() {
  echo "# 미러 동기화 매니페스트 — docs/architecture/rules/ 는 주입 룰의 장문 해설본이다."
  echo "# 각 줄 = 그 해설본이 마지막으로 반영한 **주입 룰**(plugins/common/rules/)의 sha256."
  echo "# 주입 룰을 고쳤는데 이 값이 그대로면 verify-done §7이 FAIL — 해설본 확인 후 재생성:"
  echo "#   scripts/sync-rule-mirror.sh --regenerate"
}

if [ "${1:-}" = "--regenerate" ]; then
  {
    _header
    for m in "$MIRROR_DIR"/*.md; do
      b="$(basename "$m")"
      [ -f "$SRC_DIR/$b" ] || { echo "대응 주입 룰 없음: $b" >&2; exit 1; }
      $SHA "$SRC_DIR/$b" | awk -v f="$b" '{print $1"  "f}'
    done
  } > "$MANIFEST" || exit 1
  echo "재생성 완료: $MANIFEST"
  exit 0
fi

[ -f "$MANIFEST" ] || { echo "$MANIFEST 없음 — 미러 동기화를 검증할 수 없다" >&2; exit 1; }

rc=0
for m in "$MIRROR_DIR"/*.md; do
  b="$(basename "$m")"
  if [ ! -f "$SRC_DIR/$b" ]; then
    echo "미러에 대응하는 주입 룰이 없다: $b (룰 삭제/개명 시 미러도 함께 정리)" >&2
    rc=1; continue
  fi
  want="$(awk -v f="$b" '$2==f {print $1}' "$MANIFEST")"
  have="$($SHA "$SRC_DIR/$b" | awk '{print $1}')"
  if [ -z "$want" ]; then
    echo "매니페스트에 항목 없음: $b" >&2; rc=1
  elif [ "$want" != "$have" ]; then
    echo "주입 룰이 해설본보다 최신: $b — $MIRROR_DIR/$b 반영 후 --regenerate" >&2; rc=1
  fi
done
exit "$rc"
