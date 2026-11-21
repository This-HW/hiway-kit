"""scripts/check_unicode_safety.py — 배포 텍스트 은닉 Unicode 게이트 (verify-done §31).

양성 대조(은닉 문자를 넣으면 exit 1)와 음성 대조(깨끗하면 exit 0)를 **임시 git 레포**에서
돌린다 — 실제 레포를 건드리지 않는다(`test_check_old_names.py` 관례).

**픽스처는 전부 이스케이프로 쓴다.** 이 파일도 게이트의 검사 대상이다 — 원문 문자를 넣으면
게이트가 자기 테스트를 트립해 CI 가 막힌다(LESSONS: 보안 픽스처가 스캐너를 트립하면 안 된다).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from module_loader import load_module_by_path
from resolve_in_repo_contract import assert_resolve_in_repo_contract

SCRIPT = SCRIPTS_DIR / "check_unicode_safety.py"
gate = load_module_by_path(SCRIPT, "check_unicode_safety_t")

ZWSP = "\u200b"
ZWJ = "\u200d"
RLO = "\u202e"
TAG_A = "\U000e0041"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("clean text\n한글도 정상\n", encoding="utf-8")
    return root


def _track(root: Path) -> None:
    _git(root, "add", "-A")


def _exceptions(root: Path, items: list[dict]) -> None:
    (root / "scripts" / "unicode-safety-exceptions.json").write_text(
        json.dumps({"exceptions": items}), encoding="utf-8"
    )


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


# ── 음성·양성 대조 ─────────────────────────────────────────────────────────────


def test_clean_repo_passes(repo):
    _track(repo)
    res = _run(repo)
    assert res.returncode == 0, res.stdout
    assert "0건" in res.stdout


@pytest.mark.parametrize(
    "ch, cp",
    [
        (ZWSP, "U+200B"),
        (RLO, "U+202E"),
        (TAG_A, "U+E0041"),
        ("\ufeff", "U+FEFF"),
        ("\u2066", "U+2066"),
        ("\U000e0100", "U+E0100"),
    ],
)
def test_hidden_char_fails_with_location(repo, ch, cp):
    (repo / "docs.md").write_text(f"line one\nab{ch}cd\n", encoding="utf-8")
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1
    assert f"docs.md:2:3 {cp}" in res.stdout


def test_output_never_contains_the_character(repo):
    """실패 메시지는 코드포인트만 — 문자 자체를 찍으면 로그가 페이로드를 다시 실어 나른다."""
    (repo / "a.md").write_text(f"x{TAG_A}{RLO}{ZWSP}y\n", encoding="utf-8")
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1
    for ch in (TAG_A, RLO, ZWSP):
        assert ch not in res.stdout and ch not in res.stderr


def test_untracked_file_is_not_scanned(repo):
    """대상은 git 이 추적하는 파일 — 작업 중인 미추적 파일은 아직 배포물이 아니다."""
    _track(repo)
    (repo / "scratch.md").write_text(f"a{ZWSP}b\n", encoding="utf-8")
    assert _run(repo).returncode == 0


def test_any_extension_is_scanned(repo):
    """제외 나열 방식 — 확장자 목록이 없다. 새 형식의 파일도 기본으로 검사된다."""
    (repo / "weird.unknownext").write_text(f"a{ZWJ}b", encoding="utf-8")
    _track(repo)
    assert _run(repo).returncode == 1


def test_binary_is_skipped_but_invalid_utf8_text_is_not(repo):
    (repo / "img.bin").write_bytes(b"\x89PNG\0\0" + ZWSP.encode("utf-8"))
    _track(repo)
    assert _run(repo).returncode == 0  # NUL 이 든 바이너리는 대상 밖
    (repo / "latin.txt").write_bytes(b"caf\xe9 " + TAG_A.encode("utf-8"))
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1  # 깨진 UTF-8 이 섞여 있어도 건너뛰지 않는다
    assert "latin.txt:1:" in res.stdout


# ── 바이너리 판정은 구조로 (보안 리뷰 M-1, 5.9.0) ─────────────────────────────


def test_nul_byte_does_not_exempt_a_text_file(repo):
    """재현: `.md` 에 NUL 하나 + tag 문자 → 수정 전에는 파일 전체가 '바이너리'로 빠져 rc=0 이었다."""
    (repo / "a.md").write_bytes(b"ok\x00\n" + f"x{TAG_A}y\n".encode())
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1, res.stdout
    assert "NUL 바이트가 든 파일 1건" in res.stdout and "    a.md" in res.stdout
    assert "a.md:2:2 U+E0041" in res.stdout  # 내용도 텍스트로 검사했다
    assert TAG_A not in res.stdout


def test_nul_alone_in_text_file_fails(repo):
    """은닉 문자가 없어도 인정되지 않은 NUL 파일은 fail — 다음 페이로드의 은신처가 된다."""
    (repo / "notes.txt").write_bytes(b"plain\x00text\n")
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1 and "notes.txt" in res.stdout


@pytest.mark.parametrize("name", ["icon.png", "fixture.idx", "IMG.PNG", "font.woff2"])
def test_known_binary_suffix_is_skipped_and_listed(repo, name):
    (repo / name).write_bytes(b"\x89PNG\x00\x00" + ZWSP.encode("utf-8"))
    _track(repo)
    res = _run(repo)
    assert res.returncode == 0, res.stdout
    assert "바이너리 1개 제외" in res.stdout
    assert f"    {name}" in res.stdout  # 개수가 아니라 목록으로


@pytest.mark.parametrize("attr", ["*.dat binary", "*.dat -text"])
def test_gitattributes_binary_is_honoured(repo, attr):
    (repo / ".gitattributes").write_text(attr + "\n", encoding="utf-8")
    (repo / "blob.dat").write_bytes(b"\x00\x01" + ZWSP.encode("utf-8"))
    _track(repo)
    res = _run(repo)
    assert res.returncode == 0, res.stdout
    assert "    blob.dat" in res.stdout


def test_unknown_suffix_with_nul_and_no_attribute_fails(repo):
    """음성 대조의 짝 — 같은 파일이 속성 선언 없이는 fail."""
    (repo / "blob.dat").write_bytes(b"\x00\x01" + ZWSP.encode("utf-8"))
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1
    assert "blob.dat" in res.stdout and "blob.dat:1:3 U+200B" in res.stdout


def test_binary_suffix_without_nul_is_still_scanned(repo):
    """확장자만 바꿔 다는 회피 — NUL 이 없으면 확장자와 무관하게 텍스트로 검사한다."""
    (repo / "fake.png").write_text(f"a{ZWSP}b\n", encoding="utf-8")
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1 and "fake.png:1:2 U+200B" in res.stdout


@pytest.mark.skipif(os.geteuid() == 0, reason="root 는 권한 비트를 무시한다")
def test_read_failure_message_escapes_hidden_chars(repo):
    """리뷰 L-010 — 읽기 실패 메시지(`str(err)`)에는 파일명이 그대로 들어 있다. 이스케이프해 찍는다."""
    name = f"r{ZWSP}x.md"
    target = repo / name
    target.write_text("clean\n", encoding="utf-8")
    _track(repo)
    target.chmod(0)
    try:
        res = _run(repo)
    finally:
        target.chmod(0o644)
    assert res.returncode == 1
    assert "읽기실패" in res.stdout
    assert ZWSP not in res.stdout and ZWSP not in res.stderr


def test_hidden_char_in_path_fails_and_is_escaped(repo):
    name = f"a{ZWSP}b.md"
    (repo / name).write_text("clean\n", encoding="utf-8")
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1
    assert "a\\u{200B}b.md:0:2 U+200B" in res.stdout
    assert ZWSP not in res.stdout


def test_line_numbers_follow_newlines_not_splitlines(repo):
    """U+2028 은 `splitlines()` 에서 줄을 쪼갠다 — 편집기와 같은 번호를 위해 `\\n` 으로만 센다."""
    (repo / "a.md").write_text(f"a\u2028b\nc{ZWSP}\n", encoding="utf-8")
    _track(repo)
    assert "a.md:2:2 U+200B" in _run(repo).stdout


# ── 예외 ─────────────────────────────────────────────────────────────────────


def test_exception_with_reason_covers_hit(repo):
    (repo / "emoji.md").write_text(f"family: x{ZWJ}y\n", encoding="utf-8")
    _exceptions(
        repo,
        [
            {
                "path": "emoji.md",
                "line": 1,
                "codepoint": "U+200D",
                "reason": "이모지 ZWJ 시퀀스 예시",
            }
        ],
    )
    _track(repo)
    res = _run(repo)
    assert res.returncode == 0, res.stdout
    assert "예외 1건" in res.stdout


def test_exception_is_line_and_codepoint_specific(repo):
    (repo / "emoji.md").write_text(f"x{ZWJ}y\nz{ZWJ}w {ZWSP}\n", encoding="utf-8")
    _exceptions(
        repo, [{"path": "emoji.md", "line": 1, "codepoint": "U+200D", "reason": "예시"}]
    )
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1
    assert "emoji.md:2:2 U+200D" in res.stdout
    assert "emoji.md:2:5 U+200B" in res.stdout
    assert "emoji.md:1:" not in res.stdout


def test_file_wide_exception_without_line(repo):
    (repo / "emoji.md").write_text(f"x{ZWJ}y\nz{ZWJ}w\n", encoding="utf-8")
    _exceptions(
        repo, [{"path": "emoji.md", "codepoint": "U+200D", "reason": "예시 모음"}]
    )
    _track(repo)
    assert _run(repo).returncode == 0


def test_stale_exception_fails(repo):
    """아무것도 가리지 않는 예외는 fail — 다음 결함을 숨길 자리만 남는다."""
    _exceptions(
        repo, [{"path": "README.md", "codepoint": "U+200D", "reason": "옛 예외"}]
    )
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1
    assert "아무것도 가리지 않는 예외" in res.stdout


@pytest.mark.parametrize(
    "item, needle",
    [
        ({"path": "README.md", "codepoint": "U+200D"}, "reason"),
        ({"path": "README.md", "codepoint": "U+200D", "reason": "  "}, "reason"),
        ({"path": "README.md", "codepoint": "200D", "reason": "r"}, "codepoint"),
        ({"path": "README.md", "codepoint": "U+0041", "reason": "r"}, "범위가 아니다"),
        (
            {"path": "README.md", "codepoint": "U+200D", "reason": "r", "line": 0},
            "line",
        ),
        (
            {"path": "README.md", "codepoint": "U+200D", "reason": "r", "line": True},
            "line",
        ),
        ({"path": "README.md", "codepoint": "U+200D", "reasons": "typo"}, "모르는 키"),
        ({"path": "", "codepoint": "U+200D", "reason": "r"}, "path"),
        ({"path": "/etc/hosts", "codepoint": "U+200D", "reason": "r"}, "경로 탈출"),
        ({"path": "../outside.md", "codepoint": "U+200D", "reason": "r"}, "경로 탈출"),
    ],
)
def test_invalid_exception_fails(repo, item, needle):
    _exceptions(repo, [item])
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1
    assert "예외 파일 규칙 위반" in res.stdout and needle in res.stdout


def test_symlink_escape_exception_fails(repo, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    os.symlink(outside, repo / "link.md")
    _exceptions(repo, [{"path": "link.md", "codepoint": "U+200D", "reason": "r"}])
    _track(repo)
    res = _run(repo)
    assert res.returncode == 1 and "경로 탈출" in res.stdout


def test_malformed_exceptions_file_fails(repo):
    (repo / "scripts" / "unicode-safety-exceptions.json").write_text(
        "{", encoding="utf-8"
    )
    _track(repo)
    assert _run(repo).returncode == 1


def test_resolve_in_repo_contract(tmp_path):
    """공유 적대적 케이스 표(절대경로·..·심링크·정상) — build-targets 와 같은 계약."""
    assert_resolve_in_repo_contract(gate._resolve_in_repo, tmp_path)


def test_this_repo_is_clean():
    """실제 레포 — 이 게이트를 verify-done §31 에 걸었으니 레포 자신이 통과해야 한다."""
    res = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert res.returncode == 0, res.stdout
