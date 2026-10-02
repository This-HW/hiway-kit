#!/usr/bin/env python3
"""build-site-redirects.py — 옛 사이트 리다이렉트 스텁 생성기 (v5.2.2).

왜 필요한가
-----------
제품 사이트가 `https://hiway.thishw.com/`(별도 레포)로 옮겨 갔다. 옛 주소
`this-hw.github.io/hiway-kit/` 는 이 레포의 `site/` 가 서빙하던 Hugo 사이트였고, 이미
검색엔진·외부 글·README 에 박혀 있다. GitHub Pages 는 301 을 줄 수 없으므로 **경로마다
meta refresh + canonical 을 가진 정적 HTML 스텁**을 서빙해 새 주소로 보낸다.

설계 원칙
---------
1. **표 하나가 SSOT 다.** `site/redirects.json` 이 옛 경로 → 새 경로 매핑의 전부이고,
   산출 HTML·XML 은 이 스크립트가 그 표에서만 만든다. 손으로 쓴 산출물이 없으므로
   매핑과 산출물이 갈라질 자리가 없다. 산출물은 커밋하지 않는다(`site/public/`, 배포 때 만든다).
2. **결정론적.** 같은 표는 항상 같은 바이트를 만든다(타임스탬프 없음).
3. **표 안의 경로는 산출 디렉토리 밖으로 못 나간다 — `--check`·`--write` 둘 다.**
   `from` 은 설정 파일에서 온 문자열이다. `out / from` 은 `from` 이 절대경로면 `out` 을
   통째로 버리는 pathlib 의 함정이 있다(docs/conventions/path-containment.md). 그래서
   `_resolve_in_repo()` 가 **한 번만** resolve 해서 그 결과를 검사·기록에 그대로 쓴다.
4. **빠뜨린 경로는 red.** 같은 산출 경로를 둘이 주장하거나(pages/feeds/static/retired/404),
   파일과 디렉토리가 같은 경로를 쓰면 조용히 한쪽을 덮지 않고 exit 1.
5. stdlib only, Python 3.9 floor.

사용:
  python3 scripts/build-site-redirects.py --check
  python3 scripts/build-site-redirects.py --write                # → site/public
  python3 scripts/build-site-redirects.py --write --out site/public

exit code: 0 = 성공 / 1 = 표 검증 실패·경로 탈출·충돌
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

DEFAULT_TABLE = "site/redirects.json"
DEFAULT_OUT = "site/public"
LANGS = ("ko", "en")
NEW_SITE_RE = re.compile(r"^https://[A-Za-z0-9.-]+$")
# `to` 에 들어가면 HTML·XML 속성이나 공백 구분 문맥을 깰 수 있는 글자
BAD_TARGET_CHARS = re.compile(r"[\s\"'<>\\`]")

TEXT = {
    "ko": {
        "title": "hiway-kit — 새 주소로 이동했습니다",
        "body": "이 페이지는 새 주소로 이동했습니다. 자동으로 이동하지 않으면 아래 링크를 눌러 주세요.",
        "feed_title": "hiway-kit — 피드가 이사했습니다",
        "feed_desc": "이 피드 주소는 더 이상 갱신되지 않습니다. 새 피드를 구독해 주세요:",
    },
    "en": {
        "title": "hiway-kit — moved to a new address",
        "body": "This page has moved. If you are not redirected automatically, follow the link below.",
        "feed_title": "hiway-kit — this feed has moved",
        "feed_desc": "This feed address is no longer updated. Please subscribe to the new feed:",
    },
}

STYLE = (
    ":root{color-scheme:light dark}"
    "body{font:16px/1.6 system-ui,sans-serif;margin:0;padding:3rem 1rem}"
    "main{max-width:36rem;margin:0 auto}"
    "a{word-break:break-all}"
)


class TableError(Exception):
    """표(site/redirects.json) 검증 실패 — exit 1 로 번역되는 통제된 오류."""


def _resolve_in_repo(
    container_root: Path, rel_path: str
) -> tuple[Path | None, str | None]:
    """`rel_path`(표의 문자열)를 `container_root` 안으로만 한정해 해석한다.

    `container_root / rel_path` 는 `rel_path` 가 절대경로면 `container_root` 를 버리고
    `rel_path` 그대로가 된다. `..` 나 심링크로도 트리 밖으로 나갈 수 있다 — 셋 다
    `resolve()` 한 번으로 정규화한 뒤 `container_root` 하위인지 대조하면 같은 검사로
    잡힌다. **호출자는 이 결과(Path)를 그대로 재사용해야 한다**(검사·사용 각자 resolve
    하면 그 틈이 TOCTOU).

    시그니처는 `scripts/build-targets.py::_resolve_in_repo` 와 동일하다(D-15: 구현은 여러
    벌, 계약만 하나). 공유 적대적 케이스 표는 `scripts/tests/resolve_in_repo_contract.py`.
    """
    real = (container_root / rel_path).resolve()
    try:
        real.relative_to(container_root.resolve())
    except ValueError:
        return None, f"레포 루트 밖을 가리킨다 → {real}"
    return real, None


# ── 표 검증 ────────────────────────────────────────────────────────────────


def _require_str(value: object, where: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise TableError(f"{where}: 비어 있지 않은 문자열이 필요하다")
    return value


def _check_from(path: str, where: str, *, suffix: str) -> None:
    if not path.startswith("/") or path.startswith("//"):
        raise TableError(f"{where}: '/' 하나로 시작하는 경로여야 한다 → {path!r}")
    if not path.endswith(suffix):
        raise TableError(f"{where}: {suffix!r} 로 끝나야 한다 → {path!r}")
    if "\\" in path or any(ch in path for ch in "?#"):
        raise TableError(
            f"{where}: 역슬래시·쿼리·프래그먼트는 경로가 아니다 → {path!r}"
        )
    if any(seg in ("..", ".") for seg in path.split("/")):
        raise TableError(f"{where}: '.'·'..' 세그먼트 금지 → {path!r}")
    if "//" in path:
        raise TableError(f"{where}: 빈 세그먼트('//') 금지 → {path!r}")


def _check_to(path: str, where: str, *, suffix: str) -> None:
    if not path.startswith("/") or path.startswith("//"):
        raise TableError(
            f"{where}: newSite 기준 '/' 하나로 시작하는 경로여야 한다(다른 호스트 금지) → {path!r}"
        )
    if not path.endswith(suffix):
        raise TableError(f"{where}: {suffix!r} 로 끝나야 한다 → {path!r}")
    if BAD_TARGET_CHARS.search(path):
        raise TableError(f"{where}: 공백·따옴표·꺾쇠·역슬래시 금지 → {path!r}")


def load_table(path: Path) -> dict:
    try:
        table = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise TableError(f"표를 읽지 못했다: {path} — {err}") from err
    if not isinstance(table, dict):
        raise TableError("표 최상위는 객체여야 한다")

    new_site = _require_str(table.get("newSite"), "newSite")
    if not NEW_SITE_RE.match(new_site):
        raise TableError(f"newSite: 경로 없는 https 오리진이어야 한다 → {new_site!r}")

    for key in ("pages", "feeds"):
        if not isinstance(table.get(key), list) or not table[key]:
            raise TableError(f"{key}: 비어 있지 않은 배열이 필요하다")
    for i, entry in enumerate(table["pages"]):
        where = f"pages[{i}]"
        if not isinstance(entry, dict):
            raise TableError(f"{where}: 객체가 필요하다")
        _check_from(
            _require_str(entry.get("from"), f"{where}.from"),
            f"{where}.from",
            suffix="/",
        )
        _check_to(
            _require_str(entry.get("to"), f"{where}.to"), f"{where}.to", suffix="/"
        )
        if entry.get("lang") not in LANGS:
            raise TableError(f"{where}.lang: {LANGS} 중 하나여야 한다")
    for i, entry in enumerate(table["feeds"]):
        where = f"feeds[{i}]"
        if not isinstance(entry, dict):
            raise TableError(f"{where}: 객체가 필요하다")
        _check_from(
            _require_str(entry.get("from"), f"{where}.from"),
            f"{where}.from",
            suffix=".xml",
        )
        _check_to(
            _require_str(entry.get("to"), f"{where}.to"),
            f"{where}.to",
            suffix="/index.xml",
        )
        if entry.get("lang") not in LANGS:
            raise TableError(f"{where}.lang: {LANGS} 중 하나여야 한다")

    nf = table.get("notFound")
    if not isinstance(nf, dict):
        raise TableError("notFound: 객체가 필요하다")
    _check_to(_require_str(nf.get("to"), "notFound.to"), "notFound.to", suffix="/")

    static = table.get("static")
    if not isinstance(static, dict):
        raise TableError("static: 객체가 필요하다")
    for name, content in static.items():
        _require_str(name, "static 키")
        if name.startswith("/") or "\\" in name:
            raise TableError(f"static 키: 루트 기준 상대 경로여야 한다 → {name!r}")
        if not isinstance(content, str):
            raise TableError(f"static[{name!r}]: 문자열 내용이 필요하다")

    retired = table.get("retired")
    if not isinstance(retired, list):
        raise TableError("retired: 배열이 필요하다")
    for i, entry in enumerate(retired):
        where = f"retired[{i}]"
        if not isinstance(entry, dict):
            raise TableError(f"{where}: 객체가 필요하다")
        _check_from(
            _require_str(entry.get("from"), f"{where}.from"), f"{where}.from", suffix=""
        )
        _require_str(entry.get("reason"), f"{where}.reason")
    return table


# ── 렌더 ───────────────────────────────────────────────────────────────────


def _url(new_site: str, to: str) -> str:
    return new_site + quote(to, safe="/:@~-._%")


def render_stub(lang: str, url: str) -> str:
    text = TEXT[lang]
    u = html.escape(url, quote=True)
    return (
        "<!doctype html>\n"
        f'<html lang="{lang}">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(text['title'])}</title>\n"
        '<meta name="robots" content="noindex">\n'
        f'<link rel="canonical" href="{u}">\n'
        f'<meta http-equiv="refresh" content="0; url={u}">\n'
        f"<style>{STYLE}</style>\n"
        "</head>\n<body>\n<main>\n"
        f"<p>{html.escape(text['body'])}</p>\n"
        f'<p><a href="{u}">{u}</a></p>\n'
        "</main>\n</body>\n</html>\n"
    )


def render_not_found(url: str) -> str:
    """404.html — 언어를 알 수 없는 미매핑 경로용이라 두 언어를 함께 적는다."""
    u = html.escape(url, quote=True)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>hiway-kit</title>\n"
        '<meta name="robots" content="noindex">\n'
        f'<link rel="canonical" href="{u}">\n'
        f'<meta http-equiv="refresh" content="0; url={u}">\n'
        f"<style>{STYLE}</style>\n"
        "</head>\n<body>\n<main>\n"
        f"<p>{html.escape(TEXT['en']['body'])}</p>\n"
        f"<p>{html.escape(TEXT['ko']['body'])}</p>\n"
        f'<p><a href="{u}">{u}</a></p>\n'
        "</main>\n</body>\n</html>\n"
    )


def render_feed(lang: str, new_site: str, to: str) -> str:
    """'피드가 이사했다'는 항목 하나짜리 최소 RSS 2.0 — 날짜·생성 시각 없음(결정론)."""
    text = TEXT[lang]
    feed_url = _url(new_site, to)
    page_url = _url(new_site, to[: -len("index.xml")])
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<rss version="2.0">\n<channel>\n'
        f"<title>{xml_escape(text['feed_title'])}</title>\n"
        f"<link>{xml_escape(page_url)}</link>\n"
        f"<description>{xml_escape(text['feed_desc'] + ' ' + feed_url)}</description>\n"
        f"<language>{lang}</language>\n"
        "<item>\n"
        f"<title>{xml_escape(text['feed_title'])}</title>\n"
        f"<link>{xml_escape(page_url)}</link>\n"
        f'<guid isPermaLink="false">{xml_escape(feed_url)}</guid>\n'
        f"<description>{xml_escape(text['feed_desc'] + ' ' + feed_url)}</description>\n"
        "</item>\n</channel>\n</rss>\n"
    )


def render(table: dict) -> dict[str, str]:
    """표 → {산출 상대경로: 내용}. 충돌(같은 경로 둘·파일/디렉토리 겹침)은 TableError."""
    site = table["newSite"]
    files: dict[str, str] = {}
    owners: dict[str, str] = {}

    def put(rel: str, content: str, who: str) -> None:
        key = unicodedata.normalize("NFC", rel).lower()
        if key in owners:
            raise TableError(f"산출 경로 충돌: {rel!r} ← {who} 와 {owners[key]}")
        owners[key] = who
        files[rel] = content

    for i, e in enumerate(table["pages"]):
        rel = e["from"].lstrip("/") + "index.html"
        put(rel, render_stub(e["lang"], _url(site, e["to"])), f"pages[{i}]")
    for i, e in enumerate(table["feeds"]):
        put(e["from"].lstrip("/"), render_feed(e["lang"], site, e["to"]), f"feeds[{i}]")
    put("404.html", render_not_found(_url(site, table["notFound"]["to"])), "notFound")
    for name, content in table["static"].items():
        put(name, content, f"static[{name!r}]")

    # retired 는 만들지 않는다 — 그러나 만드는 경로와 겹치면 '만들지 않는다'는 선언이 거짓이다.
    for i, e in enumerate(table["retired"]):
        rel = e["from"].lstrip("/")
        key = unicodedata.normalize("NFC", rel).lower()
        if key in owners:
            raise TableError(
                f"retired[{i}] {e['from']!r} 는 이미 {owners[key]} 가 만든다"
            )

    # 파일 경로가 다른 파일의 디렉토리 접두이면 같은 이름이 파일이자 디렉토리가 된다.
    dirs = {
        unicodedata.normalize("NFC", "/".join(rel.split("/")[:n])).lower()
        for rel in files
        for n in range(1, len(rel.split("/")))
    }
    for rel in files:
        if unicodedata.normalize("NFC", rel).lower() in dirs:
            raise TableError(f"{rel!r} 는 파일인데 다른 산출물의 디렉토리이기도 하다")
    return files


def plan(out_root: Path, files: dict[str, str]) -> dict[Path, str]:
    """산출 상대경로를 `out_root` 안의 실경로로 **한 번만** 해석한다(검사·쓰기가 공유)."""
    resolved: dict[Path, str] = {}
    for rel, content in files.items():
        try:
            target, error = _resolve_in_repo(out_root, rel)
        except (OSError, RuntimeError) as err:
            raise TableError(f"{rel!r}: 경로를 해석하지 못했다 — {err}") from err
        if target is None:
            raise TableError(f"{rel!r}: {error}")
        resolved[target] = content
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="표 검증 + 산출 계획(쓰지 않음)"
    )
    mode.add_argument("--write", action="store_true", help="산출물을 --out 에 기록")
    parser.add_argument(
        "--repo-root", default=str(Path(__file__).resolve().parent.parent)
    )
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    root = Path(args.repo_root).resolve()
    try:
        table_path, error = _resolve_in_repo(root, args.table)
        if table_path is None:
            raise TableError(f"--table: {error}")
        out_root, error = _resolve_in_repo(root, args.out)
        if out_root is None:
            raise TableError(f"--out: {error}")
        table = load_table(table_path)
        files = render(table)
        planned = plan(out_root, files)
    except TableError as err:
        print(f"[build-site-redirects] ✗ {err}", file=sys.stderr)
        return 1

    summary = (
        f"pages {len(table['pages'])} · feeds {len(table['feeds'])} · "
        f"static {len(table['static'])} · 404 1 → 파일 {len(planned)}개"
    )
    if args.check:
        print(f"[build-site-redirects] ✓ 표 유효, 경로 봉쇄 통과 — {summary}")
        return 0
    for target, content in planned.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"[build-site-redirects] ✓ {out_root} 에 기록 — {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
