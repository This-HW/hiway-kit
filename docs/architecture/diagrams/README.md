---
status: current
as_of: 2026-11-27
---

# Archify 도식 관리

도식 디렉토리마다 `candidate.json`, `<slug>.svg`, `ARTIFACTS.sha256`을 추적한다.
문서에는 `auto` 테마 SVG와 내용을 요약한 텍스트를 싣는다. 로컬 인터랙티브 HTML은 같은
뷰어 런타임을 도식마다 포함하고 GitHub 파일 화면에서는 실행되지 않으므로 Git에서 제외한다.

## 재생성

Archify 3.3.1(tt-a1i/archify, 커밋 `62f3a995eb26`)이 필요하다.

`candidate.json`을 수정하고 레포 루트에서 실행한다. 예시는 `phase-gates`다.
다른 도식은 `slug`와 `kind`를 해당 후보의 디렉토리 이름과 `diagram_type`에 맞춘다.

```sh
slug=phase-gates
kind=workflow
d="docs/architecture/diagrams/$slug"
archify="${ARCHIFY_DIR:?set to the Archify skill directory}"
receipts="$(mktemp -d "${TMPDIR:-/tmp}/hiway-archify.XXXXXX")"
ARCHIFY_UPDATE_CHECK_DISABLED=1 node "$archify/bin/archify.mjs" \
  finalize "$kind" "$d/candidate.json" "$d/$slug.html" \
  --quality showcase --repo-root "$PWD" --out-dir "$receipts" --json &&
mv "$d/$slug.delivery.json" "$receipts/" &&
ARCHIFY_UPDATE_CHECK_DISABLED=1 node "$archify/bin/export-svg.mjs" \
  "$d/$slug.html" "$receipts/$slug.svg" auto &&
mv "$receipts/$slug.svg" "$d/$slug.svg" &&
(
  cd "$d" &&
  shasum -a 256 candidate.json "$slug.svg" > ARTIFACTS.sha256
) &&
python3 scripts/check_archify_diagrams.py
```

갱신한 정본과 SVG, 매니페스트를 함께 커밋한다. Python 게이트는 Git 추적 파일을 보므로
새 도식은 세 파일을 스테이징한 뒤 실행한다.

## 인터랙티브판 열기

위 절차로 만든 `docs/architecture/diagrams/<slug>/<slug>.html`을 로컬 브라우저에서
파일로 연다. macOS에서는 `open "$d/$slug.html"`로 열 수 있다. 인터랙티브판은
미리보기 서버 없이 테마 전환과 노드 상세 보기를 제공한다.
