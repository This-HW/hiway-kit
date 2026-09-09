"""Unit tests for plugins/common/hooks/export_harness.py (W-017 / Pillar 1)."""

import importlib.util
from pathlib import Path
from types import ModuleType

HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "export_harness", HOOKS_DIR / "export_harness.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


def _fake_plugin_root(tmp_path: Path, rules: dict, *, complete: bool = True) -> Path:
    """가짜 규범 소스.

    기본은 **분류표에 등재된 룰을 전부** 만든다 — 생성기가 "표에만 있고 실물 없음"을
    실패로 취급하기 때문이다(삭제·개명된 룰이 소비자 AGENTS.md에 유령으로 남는 것을
    막는 검사). `rules` 인자로 준 것만 내용을 덮어쓴다.
    """
    root = tmp_path / "plugins" / "common"
    (root / "rules").mkdir(parents=True)
    (root / "rules" / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    # D-45 이후 분류는 규범 frontmatter 에 있다. 픽스처도 그렇게 만든다.
    _PORT = ["definition-of-done", "planning-protocol", "planning-check",
             "code-quality", "ssot", "loop-engineering", "feedback-loop"]
    _NOT = ["agent-system", "agent-delegation-chain", "parallel-worktree",
            "mcp-usage", "task-resume"]
    bodies = {}
    if complete:
        for name in _PORT + _NOT:
            bodies[name] = f"# {name}\n\n(placeholder)\n"
    bodies.update(rules)
    for name, body in bodies.items():
        text = body
        if not text.lstrip().startswith("---"):
            flag = "false" if name in _NOT else "true"
            why = ("Claude Code 고유 프리미티브에 종속" if name in _NOT
                   else "호스트 무관")
            text = f"---\ntier: core\nportable: {flag}\nportable_reason: {why}\n---\n\n" + text
        (root / "rules" / f"{name}.md").write_text(text, encoding="utf-8")
    return root


def _write_rule(root: Path, name: str, body: str, *, portable: bool = True) -> None:
    """규범 파일을 frontmatter 와 함께 쓴다 (D-45 — 분류가 파일 자신에 있다).

    테스트가 본문만 덮어쓰면 분류가 사라져 "미분류" 로 fail 한다. 그것이 생성기의
    올바른 동작이므로, 본문을 바꾸려는 테스트는 이 헬퍼를 쓴다.
    """
    why = "호스트 무관" if portable else "Claude Code 고유 프리미티브에 종속"
    (root / "rules" / f"{name}.md").write_text(
        f"---\ntier: core\nportable: {str(portable).lower()}\nportable_reason: {why}\n---\n\n{body}",
        encoding="utf-8",
    )


def _minimal(tmp_path: Path) -> Path:
    return _fake_plugin_root(
        tmp_path,
        {
            "ssot": "# SSOT\n\n단일 진실 원천을 지켜라.\n",
            "code-quality": "# Code Quality\n\n중복을 만들지 마라.\n",
            "agent-system": "# Agent System\n\nClaude Code 전용.\n",
        },
    )


# ── plugin root 해석 ──────────────────────────────────────────────


def test_plugin_root_explicit_wins(tmp_path):
    root = _minimal(tmp_path)
    assert _mod._plugin_root(str(root)) == root.resolve()


def test_missing_source_is_skipped_not_green(tmp_path, monkeypatch):
    """자동 탐색이 소스를 못 찾으면 exit 2(SKIPPED) — 절대 0으로 위장하지 않는다."""
    monkeypatch.setattr(_mod, "_plugin_root", lambda explicit: None)
    rc = _mod.main(["--target", str(tmp_path)])
    assert rc == 2
    assert not (tmp_path / "AGENTS.md").exists(), "실패 경로가 빈 파일을 남기면 안 된다"


def test_explicit_bad_plugin_root_is_error_not_skipped(tmp_path):
    """`--plugin-root`를 지정했는데 틀렸으면 exit 1이다.

    2(SKIPPED)로 내면 CI가 "kit 미설치"로 오분류하고, 메시지도 방금 지정한 사용자에게
    "지정하라"고 답하게 된다 (ATK-016).
    """
    empty = tmp_path / "nowhere"
    empty.mkdir()
    rc = _mod.main(["--plugin-root", str(empty), "--target", str(tmp_path)])
    assert rc == 1
    assert not (tmp_path / "AGENTS.md").exists()


# ── 분류 누락은 실패 ──────────────────────────────────────────────


def test_unclassified_rule_fails_loudly(tmp_path):
    # frontmatter 에 portable 선언이 없는 규범 = 미분류 (D-45)
    root = _fake_plugin_root(
        tmp_path, {"ssot": "# SSOT\n", "brand-new-rule": "---\ntier: core\n---\n\n# New\n"}
    )
    try:
        _mod.build_block(root)
    except _mod.ClassificationError as e:
        assert "brand-new-rule" in str(e)
    else:
        raise AssertionError("미분류 룰이 조용히 통과했다 — 내보내기 구멍")

    # 순수 빌더가 SystemExit을 던지면 이 모듈을 import한 호스트가 죽는다.
    assert not issubclass(_mod.ClassificationError, SystemExit)


def test_not_portable_rule_body_is_excluded(tmp_path):
    root = _minimal(tmp_path)
    block, _ = _mod.build_block(root)
    assert "단일 진실 원천을 지켜라" in block
    assert "Claude Code 전용." not in block, "이식 불가 룰의 본문이 새어나갔다"
    # 다만 '왜 없는지'는 표로 남아야 한다
    assert "rules/agent-system" in block


# ── 파일 기록 규율 ────────────────────────────────────────────────


def test_creates_new_file(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "kit:begin" in text and _mod.END_MARK in text


def test_appends_to_user_file_without_destroying_it(tmp_path):
    """마커가 없는 사용자 AGENTS.md는 덮어쓰지 않고 append한다 (consumer-first)."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    user = "# 우리 팀 규약\n\n커밋 메시지는 한국어로.\n"
    (target / "AGENTS.md").write_text(user, encoding="utf-8")

    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith(user), "사용자 콘텐츠가 파괴됐다"
    assert "kit:begin" in text


def test_replaces_only_managed_block(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _mod.main(["--plugin-root", str(root), "--target", str(target)])

    # 블록 앞뒤에 사용자 콘텐츠를 붙인다
    p = target / "AGENTS.md"
    text = p.read_text(encoding="utf-8")
    p.write_text("PRE-USER\n\n" + text + "\nPOST-USER\n", encoding="utf-8")

    # 규범을 바꾸고 재생성
    _write_rule(root, "ssot", "# SSOT\n\n바뀐 규범.\n")
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0

    out = p.read_text(encoding="utf-8")
    assert out.startswith("PRE-USER")
    assert out.rstrip().endswith("POST-USER")
    assert "바뀐 규범." in out
    assert "단일 진실 원천을 지켜라" not in out
    assert out.count("kit:begin") == 1, "블록이 중복 생성됐다"


def test_idempotent(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    first = (target / "AGENTS.md").read_text(encoding="utf-8")
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == first


# ── 드리프트 게이트 ───────────────────────────────────────────────


def test_check_detects_drift(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 0
    )

    (root / "rules" / "ssot.md").write_text(
        "# SSOT\n\n규범이 바뀌었다.\n", encoding="utf-8"
    )
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 1
    )


def test_check_fails_when_never_exported(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 1
    )


def test_check_fails_when_marker_stripped(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    (target / "AGENTS.md").write_text("마커를 지워버렸다\n", encoding="utf-8")
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 1
    )


def test_check_does_not_write(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"])
    assert not (target / "AGENTS.md").exists()


def test_not_portable_rule_change_does_not_move_sha(tmp_path):
    """이식 안 되는 룰이 바뀌었다고 소비자 AGENTS.md를 흔들지 않는다."""
    root = _minimal(tmp_path)
    _, sha1 = _mod.build_block(root)
    _write_rule(root, "agent-system", "# Agent System\n\n완전히 달라짐.\n", portable=False)
    _, sha2 = _mod.build_block(root)
    assert sha1 == sha2


def _write_broken(target: Path, body: str) -> None:
    target.mkdir(exist_ok=True)
    (target / "AGENTS.md").write_text(body, encoding="utf-8")


def test_truncated_block_refuses_instead_of_appending(tmp_path):
    """begin만 있고 end가 없으면 덧붙이지 않는다 — 덧붙이면 begin이 둘이 되고
    이후 --check가 앞의 깨진 마커를 읽어 재생성으로도 못 고치는 red가 된다."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    _write_broken(
        target,
        "# mine\n\n<!-- kit:begin rules-v9.9.9 sha256:" + "a" * 64 + " -->\n잘림\n",
    )
    before = (target / "AGENTS.md").read_text(encoding="utf-8")

    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 1
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == before, (
        "손상 파일을 건드렸다"
    )


def test_duplicate_blocks_refuse(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    p = target / "AGENTS.md"
    p.write_text(p.read_text(encoding="utf-8") * 2, encoding="utf-8")

    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 1
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 1
    )


def test_check_reports_broken_marker(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    _write_broken(target, "<!-- kit:begin x -->\n")
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 1
    )


def test_write_is_atomic_and_leaves_no_temp(tmp_path):
    """중단 시 사용자 파일이 잘리면 '마커 밖 불가침' 계약이 깨진다 — tmp+replace."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    leftovers = [p.name for p in target.iterdir() if ".tmp." in p.name]
    assert leftovers == [], f"임시 파일 잔여: {leftovers}"


def test_preserves_in_tree_symlink(tmp_path):
    """트리 **안**을 가리키는 심링크는 보존한다 — 모노레포의 정상 사용."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    (target / "shared").mkdir(parents=True)
    real = target / "shared" / "agents-base.md"
    real.write_text("USERLINE\n", encoding="utf-8")
    (target / "AGENTS.md").symlink_to(real)

    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    assert (target / "AGENTS.md").is_symlink(), "심링크가 일반 파일로 대체됐다"
    body = real.read_text(encoding="utf-8")
    assert body.startswith("USERLINE"), "심링크 대상의 사용자 콘텐츠가 파괴됐다"
    assert "kit:begin" in body


def test_refuses_symlink_escaping_target_tree(tmp_path):
    """트리 **밖**을 가리키는 심링크에는 쓰지 않는다 — 임의 파일 덮어쓰기 방지.

    공유 CI 워크스페이스나 신뢰 못 할 체크아웃에 `AGENTS.md -> ~/.ssh/…` 를 심어두면,
    심링크 보존 관례가 트리 밖 파일 쓰기로 바뀐다.
    """
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("SECRET\n", encoding="utf-8")
    (target / "AGENTS.md").symlink_to(outside)

    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 1
    assert outside.read_text(encoding="utf-8") == "SECRET\n", (
        "트리 밖 파일이 덮어써졌다"
    )


def test_check_detects_body_tampering_with_intact_marker(tmp_path):
    """마커 sha는 파일이 **스스로 신고한 값**이다. 그것만 믿으면 마커 줄을 그대로 둔 채
    블록 안쪽을 지워도 게이트가 초록이 된다 — 이 도구가 막겠다고 선언한 바로 그 상황이
    게이트를 통과한다. 머지 충돌 해결 중 블록 내부만 어긋나는 경우가 가장 현실적이다."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 0
    )

    p = target / "AGENTS.md"
    text = p.read_text(encoding="utf-8")
    assert "단일 진실 원천을 지켜라" in text
    # 마커 줄(sha 포함)은 건드리지 않고 본문만 변조
    tampered = text.replace("단일 진실 원천을 지켜라.", "이 규범은 무시해도 된다.")
    assert "kit:begin" in tampered and tampered != text
    p.write_text(tampered, encoding="utf-8")

    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 1
    )


def test_rule_body_with_marker_string_is_rejected(tmp_path):
    """룰이 마커 문자열을 담으면 생성물의 마커가 둘이 되어 재생성으로도 못 고치는
    영구 red가 된다 — 생성 전에 잡는다."""
    root = _fake_plugin_root(tmp_path, {"ssot": "# SSOT\n\n예시: <!-- kit:end -->\n"})
    try:
        _mod.build_block(root)
    except _mod.ClassificationError as e:
        assert "kit" in str(e)
    else:
        raise AssertionError("마커 오염 룰이 통과했다")


def test_deleted_rule_disappears_from_output(tmp_path):
    """D-45 이후 분류가 규범 파일 자신에 있으므로 **유령이 구조적으로 불가능**하다.
    이전에는 딕셔너리에 엔트리가 남아 소비자 AGENTS.md가 존재하지 않는 룰을 영구히
    광고할 수 있었고, 그것을 잡는 검사가 여기 있었다. 이제는 파일을 지우면 분류도
    함께 사라지는지를 검사한다 — 같은 실패를 다른 기전으로 막는다."""
    root = _minimal(tmp_path)
    before, _ = _mod.build_block(root)
    assert "agent-system" in before
    (root / "rules" / "agent-system.md").unlink()
    after, _ = _mod.build_block(root)
    assert "agent-system" not in after, "삭제된 룰이 생성물에 남았다"


def test_self_location_beats_env_var(tmp_path, monkeypatch):
    """셸에 남은 다른 플러그인의 CLAUDE_PLUGIN_ROOT가 남의 rules를 내보내면 안 된다."""
    other = _fake_plugin_root(tmp_path / "other", {}, complete=False)
    (other / "rules" / "someone-elses-rule.md").write_text(
        "# Foreign\n", encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(other))
    # 자기 위치(plugins/common/hooks/의 부모)가 1순위여야 한다
    assert _mod._plugin_root(None) == (HOOKS_DIR.parent).resolve()


def test_headings_are_demoted_uniformly(tmp_path):
    """h1만 강등하면 룰의 h2 하위 절이 블록 헤더와 형제가 되어 계층이 역전된다."""
    root = _fake_plugin_root(
        tmp_path, {"ssot": "# SSOT\n\n## 하위 절\n\n본문\n\n```\n# 코드 주석\n```\n"}
    )
    block, _ = _mod.build_block(root)
    assert "### SSOT" in block
    assert "#### 하위 절" in block
    assert "\n## 하위 절" not in block, "h2가 블록 헤더와 동급으로 남았다"
    assert "# 코드 주석" in block, "코드펜스 내부가 변조됐다"


def test_generated_block_contains_exactly_one_marker_pair(tmp_path):
    """생성기 **자신의 헤더**에 마커를 리터럴로 적으면 생성물이 자기 자신을 손상시킨다.
    (2026-08-23 실제 발생: 헤더에 마커 예시를 넣었다가 begin 2개가 됐다)"""
    root = _minimal(tmp_path)
    block, _ = _mod.build_block(root)
    assert block.count("kit:begin") == 1
    assert block.count("kit:end") == 1

    # 왕복: 생성 → 기록 → 재검사가 항상 통과해야 한다
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 0
    )


def test_empty_file_gets_preamble_like_missing_file(tmp_path):
    """빈 AGENTS.md로 시작한 소비자만 안내 헤더를 못 받는 비대칭을 없앤다."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    (target / "AGENTS.md").write_text("", encoding="utf-8")
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith(_mod.PREAMBLE), "빈 파일 경로에서 PREAMBLE이 빠졌다"


def test_symlink_escape_is_checked_before_reading(tmp_path):
    """탈출 검사가 읽기 뒤에 있으면 트리 밖 파일을 먼저 읽어 존재/내용 오라클이 된다."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("SECRET\n", encoding="utf-8")
    (target / "AGENTS.md").symlink_to(outside)

    reads: list[str] = []
    orig = _mod.Path.read_text

    def spy(self, *a, **k):
        reads.append(str(self))
        return orig(self, *a, **k)

    _mod.Path.read_text = spy
    try:
        rc = _mod.main(["--plugin-root", str(root), "--target", str(target)])
    finally:
        _mod.Path.read_text = orig
    assert rc == 1
    assert not any("AGENTS.md" in r for r in reads), f"거부 전에 읽었다: {reads}"


# ── 2026-08-24 적대적 리뷰 회귀 (ATK-001 … ATK-017) ──────────────────────────


def test_prose_mentioning_markers_is_not_treated_as_a_block(tmp_path):
    """마커를 *설명하는* 산문을 진짜 블록으로 오인하지 않는다 (ATK-001).

    이 도구의 대상 파일은 하필 "에이전트에게 이 킷을 설명하는 문서"다. 앵커 없는 관대한
    패턴은 두 인용 사이의 사용자 문장을 침묵 속에 삭제하고 exit 0을 냈다 — 그리고 그
    뒤로 --check는 green을 돌려줘 흔적도 남지 않았다.
    """
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    user = (
        "# 우리 팀 규약\n\n"
        "## 이 킷의 블록에 대해\n\n"
        "`<!-- kit:begin -->` 마커로 시작하는 구간은 자동 생성이다.\n\n"
        "**절대 손으로 고치지 마라.** 고치면 다음 재생성에서 날아간다.\n"
        "갱신은 `/harness-export`로만 한다. QA 승인 없이 배포 금지.\n\n"
        "`<!-- kit:end -->` 마커까지가 그 구간이다.\n"
    )
    (target / "AGENTS.md").write_text(user, encoding="utf-8")

    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    after = (target / "AGENTS.md").read_text(encoding="utf-8")
    for line in user.rstrip().split("\n"):
        assert line in after, f"사용자 문장이 삭제됐다: {line!r}"
    assert after.startswith(user.rstrip()), "산문 사이에 블록이 끼어들었다"


def test_malformed_marker_line_refuses(tmp_path):
    """형식이 깨진 **진짜** 마커 줄은 '마커 없음'이 아니라 손상이다.

    엄격화의 반대편 구멍: 그냥 무시하면 새 블록이 덧붙고 낡은 규범 본문이 고아로 남는다.
    """
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    _write_broken(
        target, "# mine\n\n<!-- kit:begin rules-v9.9.9 sha256:dead -->\n낡음\n"
    )
    before = (target / "AGENTS.md").read_text(encoding="utf-8")

    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 1
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == before


def test_check_and_stdout_are_mutually_exclusive(tmp_path):
    """`--check --stdout`가 검사를 건너뛰고 exit 0을 내면 완료 게이트가 무력화된다 (ATK-003)."""
    import pytest

    root = _minimal(tmp_path)
    with pytest.raises(SystemExit) as exc:
        _mod.main(
            [
                "--plugin-root",
                str(root),
                "--target",
                str(tmp_path),
                "--check",
                "--stdout",
            ]
        )
    assert exc.value.code != 0


def test_malformed_portable_value_is_rejected(tmp_path):
    """D-45 이후 양쪽 등재는 구조적으로 불가능하다(선언이 한 곳). 대신 **잘못된 값**이
    조용히 통과하지 않는지를 검사한다 — `portable: maybe` 같은 값을 미분류로 읽어
    fail 시켜야 한다. 조용히 false 로 읽으면 '내보냈다고 믿는데 안 나간' 구멍이 된다."""
    root = _minimal(tmp_path)
    (root / "rules" / "ssot.md").write_text(
        "---\ntier: core\nportable: maybe\n---\n\n# SSOT\n", encoding="utf-8"
    )
    assert _mod.main(["--plugin-root", str(root), "--target", str(tmp_path)]) == 1


def test_existing_file_mode_is_preserved(tmp_path):
    """마커 밖 불가침은 **메타데이터에도** 적용된다 (ATK-005).

    0600으로 관리하던 AGENTS.md가 재생성 후 world-readable이 되면 안 된다.
    """
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    p = target / "AGENTS.md"
    p.write_text("# mine\n", encoding="utf-8")
    p.chmod(0o600)

    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    assert oct(p.stat().st_mode & 0o777) == "0o600"


def test_check_refuses_symlink_escaping_target_tree(tmp_path, capsys):
    """--check도 쓰기와 **같은** 심링크 검사를 한다 (ATK-004)."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret\n", encoding="utf-8")
    (target / "AGENTS.md").symlink_to(outside)

    rc = _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"])
    assert rc == 1
    # exit 1만 보면 "마커 없음"과 구분되지 않는다 — 트리 밖 파일을 **읽고** 1을 냈을
    # 수도 있다. 거부 사유가 심링크임을 확인해야 이 회귀를 잡는다.
    err = capsys.readouterr().err
    assert "심링크" in err and str(outside) in err


def test_nested_four_backtick_fence_is_not_mutated(tmp_path):
    """4-백틱 펜스 안의 `# 주석`이 헤딩으로 강등되면 '원문 그대로'의 직접 위반이다 (ATK-010)."""
    root = _fake_plugin_root(
        tmp_path,
        {"ssot": "# SSOT\n\n````markdown\n```bash\n# 이 주석은 코드다\n```\n````\n"},
    )
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    out = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "# 이 주석은 코드다" in out
    assert "### 이 주석은 코드다" not in out


def test_bad_rules_version_is_rejected(tmp_path):
    """VERSION은 마커 줄에 직접 들어간다 — `>` 하나로 영구 손상이 된다 (ATK-007)."""
    root = _minimal(tmp_path)
    (root / "rules" / "VERSION").write_text("1.0 --> junk\n", encoding="utf-8")
    assert _mod.main(["--plugin-root", str(root), "--target", str(tmp_path)]) == 1
    assert not (tmp_path / "AGENTS.md").exists()


def test_heading_too_deep_fails_loudly(tmp_path):
    """h5 이상은 2단계 강등 시 h6를 넘는다 — 조용히 뭉개지 않고 멈춘다 (ATK-015)."""
    root = _fake_plugin_root(tmp_path, {"ssot": "# SSOT\n\n##### 다섯 단계\n\n본문\n"})
    assert _mod.main(["--plugin-root", str(root), "--target", str(tmp_path)]) == 1


def test_sha_covers_generator_template_not_only_rules(tmp_path, monkeypatch):
    """sha는 블록 **전체**의 지문이어야 한다 (ATK-008).

    템플릿이 빠지면 kit이 헤더 문구만 고친 릴리스에서 sha는 일치하고 전문 비교만
    어긋나, 게이트가 아무도 손대지 않은 파일을 '변조'로 지목한다.
    """
    root = _minimal(tmp_path)
    _, sha_before = _mod.build_block(root)
    monkeypatch.setattr(
        _mod,
        "BLOCK_HEADER",
        _mod.BLOCK_HEADER.replace("하네스 중립 규범", "하네스 중립 규범 (개정)"),
    )
    _, sha_after = _mod.build_block(root)
    assert sha_before != sha_after


def test_portable_reasons_are_rendered(tmp_path):
    """이식 사유가 어디에도 안 나가면 리뷰 압력이 0인 죽은 데이터다 (ATK-012).
    D-45 이후 사유는 규범 frontmatter 의 `portable_reason` 이다."""
    root = _minimal(tmp_path)
    block, _ = _mod.build_block(root)
    assert "### 이식된 룰" in block
    assert "호스트 무관" in block


def test_missing_target_root_is_not_created(tmp_path):
    """--target 오타 하나로 없는 디렉터리 트리를 만들지 않는다 (ATK-017)."""
    root = _minimal(tmp_path)
    ghost = tmp_path / "typo" / "deep"
    assert _mod.main(["--plugin-root", str(root), "--target", str(ghost)]) == 1
    assert not ghost.exists()


# ── conventions 블록 (kit2:, W-022 R7) ─────────────────────────────


def _fake_conventions_dir(target: Path) -> Path:
    """CONVENTIONS_INLINE + CONVENTIONS_REFERENCE_ONLY에 등재된 파일을 전부 만든다
    — build_conventions_block()이 "표에 있는데 실물 없음"을 실패로 보기 때문에
    (규범 블록의 PORTABLE/NOT_PORTABLE와 같은 종류의 방어)."""
    conv_dir = target / "docs" / "conventions"
    conv_dir.mkdir(parents=True)
    for fname, _title in _mod.CONVENTIONS_INLINE:
        (conv_dir / fname).write_text(f"# {fname}\n\n본문.\n", encoding="utf-8")
    for fname in _mod.CONVENTIONS_REFERENCE_ONLY:
        (conv_dir / fname).write_text(
            f"# {fname}\n\n참조 전용 본문.\n", encoding="utf-8"
        )
    return conv_dir


def test_conventions_block_is_none_without_docs_dir(tmp_path):
    """docs/conventions/가 없는 target(= 설치된 플러그인 캐시에서 도는 소비자)에서는
    conv 블록 자체가 생성 대상이 아니다 — 에러가 아니라 None."""
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.build_conventions_block(target) is None


def test_conventions_missing_inline_file_raises(tmp_path):
    target = tmp_path / "proj"
    _fake_conventions_dir(target)
    (target / "docs" / "conventions" / _mod.CONVENTIONS_INLINE[0][0]).unlink()
    try:
        _mod.build_conventions_block(target)
        raise AssertionError("빠진 인라인 파일을 조용히 넘겼다")
    except _mod.ClassificationError:
        pass


def test_conventions_missing_reference_file_raises(tmp_path):
    target = tmp_path / "proj"
    _fake_conventions_dir(target)
    (target / "docs" / "conventions" / _mod.CONVENTIONS_REFERENCE_ONLY[0]).unlink()
    try:
        _mod.build_conventions_block(target)
        raise AssertionError("빠진 참조 전용 파일을 조용히 넘겼다")
    except _mod.ClassificationError:
        pass


def test_conventions_block_written_alongside_rules_block(tmp_path):
    """rules 블록(kit:)과 conventions 블록(kit2:)이 한 파일에 독립적으로 공존한다."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _fake_conventions_dir(target)
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "kit:begin" in text and _mod.END_MARK in text
    assert "kit2:begin conventions-v" in text and _mod.CONV_END_MARK in text
    assert text.count("kit:begin") == 1
    assert text.count("kit2:begin") == 1


def test_conventions_check_passes_after_write(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _fake_conventions_dir(target)
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 0
    )


def test_conventions_drift_detected_independently_of_rules(tmp_path):
    """conventions 소스만 바뀌어도 --check가 잡는다 — rules 소스는 그대로다."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    conv_dir = _fake_conventions_dir(target)
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 0
    )

    inline_fname = _mod.CONVENTIONS_INLINE[0][0]
    (conv_dir / inline_fname).write_text("# 바뀐 conventions 본문\n", encoding="utf-8")
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 1
    )

    # 재생성하면 다시 green
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 0
    )


def test_conventions_check_ignores_rules_only_targets(tmp_path):
    """docs/conventions/가 없는 대상은 conv 블록 검사 자체를 안 한다 — 기존 rules-only
    --check 계약이 이 확장으로 조금도 안 변했다는 회귀 방지."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "kit2:" not in text
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 0
    )


def test_conventions_body_tamper_with_intact_marker_detected(tmp_path):
    """kit2 마커는 멀쩡한데 블록 안쪽만 손으로 고치면 --check가 잡는다
    (규범 블록의 test_check_detects_body_tampering_with_intact_marker와 같은 공격)."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _fake_conventions_dir(target)
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    p = target / "AGENTS.md"
    text = p.read_text(encoding="utf-8")
    # 제목에 박힌 킷 이름을 하드코딩하지 않는다 — 개명 때 이 테스트가 조용히
    # 무의미해진다(치환이 0건이면 tampered == text 라 어서션만 깨진다).
    tampered = text.replace("— Project Conventions", "— 변조된 제목")
    assert tampered != text
    p.write_text(tampered, encoding="utf-8")
    assert (
        _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 1
    )


def test_conventions_marker_string_in_source_body_is_rejected(tmp_path):
    """conventions 소스 파일 본문에 kit2 마커 문자열이 있으면 생성물이 자기 자신을
    손상시킨다 — build_block()의 test_rule_body_with_marker_string_is_rejected와 같은
    방어를 conv 쪽에도 건다."""
    target = tmp_path / "proj"
    conv_dir = _fake_conventions_dir(target)
    inline_fname = _mod.CONVENTIONS_INLINE[0][0]
    (conv_dir / inline_fname).write_text(
        "본문 중간에 <!-- kit2:begin conventions-vX sha256:" + "0" * 64 + " -->\n",
        encoding="utf-8",
    )
    try:
        _mod.build_conventions_block(target)
        raise AssertionError("kit2 마커 문자열이 섞인 소스를 그대로 실었다")
    except _mod.ClassificationError:
        pass


def test_conventions_idempotent(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _fake_conventions_dir(target)
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    first = (target / "AGENTS.md").read_text(encoding="utf-8")
    _mod.main(["--plugin-root", str(root), "--target", str(target)])
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == first


def test_conventions_preserves_user_content_around_both_blocks(tmp_path):
    """kit: 블록 앞, kit: 와 kit2: 사이, kit2: 블록 뒤 — 세 군데 사용자 콘텐츠가 전부
    살아남는다."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    _fake_conventions_dir(target)
    _mod.main(["--plugin-root", str(root), "--target", str(target)])

    p = target / "AGENTS.md"
    text = p.read_text(encoding="utf-8")
    rules_end = text.index(_mod.END_MARK) + len(_mod.END_MARK)
    conv_begin = text.index("<!-- kit2:begin")
    new_text = (
        text[:rules_end] + "\n\nMID-USER\n\n" + text[conv_begin:] + "\nPOST-USER\n"
    )
    p.write_text("PRE-USER\n\n" + new_text, encoding="utf-8")

    # 규범과 conventions 둘 다 바꿔서 재생성이 실제로 콘텐츠를 건드리게 한다
    _write_rule(root, "ssot", "# SSOT\n\n바뀐 규범.\n")
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0

    out = p.read_text(encoding="utf-8")
    assert out.startswith("PRE-USER")
    assert "MID-USER" in out
    assert out.rstrip().endswith("POST-USER")
    assert out.count("kit:begin") == 1
    assert out.count("kit2:begin") == 1


# ── 구 마커 이행 경로 (v3.9.0) ────────────────────────────────────────────────
#
# 소비자의 AGENTS.md 에는 이미 구 토큰(`cck:`) 블록이 들어 있다. 새 토큰만 인식하면  (old-name-ok: 구 마커 인식 = 이행 경로)
# 그 블록이 **고아로 남은 채** 새 블록이 덧붙어, 한 파일에 규범 블록이 둘이 된다.
# 읽기는 둘 다 받고 쓰기는 새 토큰으로만 — 그래야 다음 export 가 제자리에서 교체한다.


def test_old_marker_block_is_replaced_in_place_not_duplicated(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    (target / "AGENTS.md").write_text(
        "# 내 파일\n\n앞 문장\n\n"
        "<!-- cck:begin rules-v9.9.9 sha256:" + "a" * 64 + " -->\n"  # old-name-ok: 구 마커 인식 = 이행 경로
        "낡은 규범 본문\n"
        "<!-- cck:end -->\n\n"  # old-name-ok: 구 마커 인식 = 이행 경로
        "뒤 문장\n",
        encoding="utf-8",
    )
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    out = (target / "AGENTS.md").read_text(encoding="utf-8")

    # 제자리 교체: 블록은 하나뿐이고 새 토큰이며, 구 토큰은 남지 않는다.
    assert out.count("kit:begin") == 1
    assert out.count("kit:end") == 1
    assert "cck:begin" not in out and "cck:end" not in out  # old-name-ok: 구 마커 인식 = 이행 경로
    assert "낡은 규범 본문" not in out
    # 마커 밖 사용자 콘텐츠는 불가침.
    assert "앞 문장" in out and "뒤 문장" in out and "# 내 파일" in out


# ── 다중 진입점 (v3.10.0) ────────────────────────────────────────────────────
#
# 하네스마다 읽는 파일 이름이 다르다(AGENTS.md / GEMINI.md). 내용은 같으므로 블록도
# sha 도 하나이고 파일만 여럿이다. 한 파일에만 내보내면 나머지 하네스는 규율 밖에서 돈다.


def test_writes_all_entrypoints_with_identical_block(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    texts = [(target / n).read_text(encoding="utf-8") for n in _mod.ENTRYPOINTS]
    assert len(texts) >= 2, "진입점이 하나뿐이면 이 계약은 의미가 없다"
    # 같은 블록·같은 sha — 전문에 파일 이름이 들어가면 여기서 갈린다.
    assert len(set(texts)) == 1, "진입점마다 내용이 갈렸다"
    for t in texts:
        assert t.count("kit:begin") == 1


def test_check_reports_every_stale_entrypoint_not_just_the_first(tmp_path):
    """첫 실패에서 멈추면 '하나만 낡음'과 '전부 낡음'을 구별할 수 없다."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(["--plugin-root", str(root), "--target", str(target)]) == 0
    assert _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 0
    # 두 진입점을 모두 망가뜨린다.
    for n in _mod.ENTRYPOINTS:
        f = target / n
        f.write_text(f.read_text(encoding="utf-8").replace("단일 진실 원천", "손댐"), encoding="utf-8")
    assert _mod.main(["--plugin-root", str(root), "--target", str(target), "--check"]) == 1


def test_entrypoints_flag_overrides_default(tmp_path):
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(
        ["--plugin-root", str(root), "--target", str(target), "--entrypoints", "ONLY.md"]
    ) == 0
    assert (target / "ONLY.md").exists()
    assert not (target / "AGENTS.md").exists()



# ─────────────────────────────────────────────────────────────────────────────
# ATK-002 / ATK-009 — 진입점 이름 경로 봉쇄 (docs/conventions/path-containment.md)
#
# `--entrypoints`는 사용자 입력이고 `target_root / name`은 name이 절대경로면
# target_root를 통째로 버린다. 봉쇄 전에는 트리 밖 파일에 13,824바이트를 실제로 썼다.
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_contract_cases():
    """`scripts/tests/resolve_in_repo_contract.py`의 공유 적대적 케이스 표 (D-15).

    이 표는 **레포 로컬**이다 — 소비자의 플러그인 캐시에는 `scripts/`가 없으므로
    없으면 건너뛴다. 여기서 케이스를 다시 베끼면 계약이 두 벌이 된다.
    """
    import sys as _sys

    repo_tests = HOOKS_DIR.parent.parent.parent / "scripts" / "tests"
    if not (repo_tests / "resolve_in_repo_contract.py").is_file():
        return None
    if str(repo_tests) not in _sys.path:
        _sys.path.insert(0, str(repo_tests))
    import resolve_in_repo_contract

    return resolve_in_repo_contract


def test_resolve_in_repo_matches_shared_contract(tmp_path):
    """봉쇄 헬퍼가 다른 두 구현과 **같은 계약**을 만족한다 (절대경로·`..`·심링크·대조군).

    관례를 새로 발명하는 것이 이 결함이 네 번 반복된 이유이므로, 이 구현도
    `build-targets.py`·`check_eval_coverage.py`와 같은 표로 검증한다.
    """
    contract = _resolve_contract_cases()
    if contract is None:  # 레포 밖(플러그인 캐시)에서는 표가 없다
        return
    for case in contract.CASES:
        container = tmp_path / f"container-{case.name}"
        rel = case.setup(container)
        real, err = _mod._resolve_in_repo(container, rel)
        if case.should_escape:
            assert real is None and err, f"{case.name}: 탈출이 봉쇄되지 않았다"
        else:
            assert real is not None and err is None, f"{case.name}: 정상 경로를 막았다"


def test_absolute_entrypoint_cannot_write_outside_target(tmp_path, capsys):
    """절대경로 진입점은 트리 밖에 쓰지 못한다 (ATK-002, 재현 확인)."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    outside = tmp_path / "outside" / "pwned.md"
    outside.parent.mkdir()

    rc = _mod.main(
        ["--plugin-root", str(root), "--target", str(target),
         "--entrypoints", str(outside)]
    )
    assert rc == 1
    assert not outside.exists(), "트리 밖에 파일이 생성됐다"
    assert "절대경로" in capsys.readouterr().err


def test_dotdot_entrypoint_cannot_write_outside_target(tmp_path, capsys):
    """`..` 순회 진입점도 같은 봉쇄에 걸린다 (ATK-002)."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    (tmp_path / "outside").mkdir()

    rc = _mod.main(
        ["--plugin-root", str(root), "--target", str(target),
         "--entrypoints", "../outside/dotdot.md"]
    )
    assert rc == 1
    assert not (tmp_path / "outside" / "dotdot.md").exists(), "트리 밖에 파일이 생성됐다"
    assert "순회" in capsys.readouterr().err


def test_check_applies_the_same_entrypoint_containment(tmp_path):
    """`--check`에도 **같은** 봉쇄를 건다 — 2.14.1은 쓰기에만 걸어 구멍이 남았다.

    exit 1만 보면 "마커 없음"과 구별되지 않으므로, 트리 밖 파일을 **읽지 않았다**는
    것까지 확인한다(존재·디코딩 오류가 오라클로 새어나가는 경로).
    """
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("not-a-secret-placeholder\n", encoding="utf-8")

    reads: list[str] = []
    orig = _mod.Path.read_text

    def spy(self, *a, **k):
        reads.append(str(self))
        return orig(self, *a, **k)

    _mod.Path.read_text = spy
    try:
        rc = _mod.main(
            ["--plugin-root", str(root), "--target", str(target),
             "--entrypoints", str(outside), "--check"]
        )
    finally:
        _mod.Path.read_text = orig

    assert rc == 1
    assert str(outside) not in reads, "봉쇄 전에 트리 밖 파일을 읽었다"


def test_in_tree_symlink_target_is_read_and_written_through_resolved_path(tmp_path):
    """검사한 객체와 읽고 쓰는 객체가 같아야 한다 (ATK-009).

    트리 안 심링크는 정상 사용이므로 **보존**되고, 읽기·쓰기 모두 해석된 실경로
    하나로만 일어난다 — 해석 전 경로를 따로 읽으면 그 사이가 TOCTOU 창이다.
    """
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    (target / "shared").mkdir(parents=True)
    real = target / "shared" / "agents-base.md"
    real.write_text("USERLINE\n", encoding="utf-8")
    (target / "AGENTS.md").symlink_to(real)

    reads: list[str] = []
    orig = _mod.Path.read_text

    def spy(self, *a, **k):
        reads.append(str(self))
        return orig(self, *a, **k)

    _mod.Path.read_text = spy
    try:
        rc = _mod.main(["--plugin-root", str(root), "--target", str(target)])
    finally:
        _mod.Path.read_text = orig

    assert rc == 0
    assert str(real) in reads, "해석된 실경로로 읽지 않았다"
    assert str(target / "AGENTS.md") not in reads, (
        "해석 전 경로를 따로 읽었다 — 검사한 객체와 쓰는 객체가 갈린다"
    )
    assert (target / "AGENTS.md").is_symlink()
    assert "kit:begin" in real.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# ATK-003 — conventions 블록 실패가 규범 블록 기록을 막으면 안 된다 (consumer-first)
# ─────────────────────────────────────────────────────────────────────────────


def test_consumer_repo_with_its_own_conventions_dir_still_gets_rules_block(tmp_path):
    """자기 관례 문서를 가진 소비자 레포에서도 규범 블록은 기록된다 (ATK-003).

    `docs/conventions/`가 있으나 `CONVENTIONS_INLINE`의 파일이 **하나도** 없으면
    그 레포는 kit 레포가 아니다 — 오류가 아니라 대상 아님이다. 수정 전에는
    ClassificationError → `return 1`로 진입점 루프 **전에** 종료해서, 이 도구의
    본래 목적인 규범 블록이 한 글자도 써지지 않았다.
    """
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    (target / "docs" / "conventions").mkdir(parents=True)
    (target / "docs" / "conventions" / "our-style.md").write_text(
        "# 우리 레포의 관례\n", encoding="utf-8"
    )

    rc = _mod.main(["--plugin-root", str(root), "--target", str(target)])
    assert rc == 0, "소비자 레포에서 실패했다 — consumer-first 위반"
    body = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "kit:begin" in body, "규범 블록이 기록되지 않았다"
    assert "kit2:begin" not in body, "대상이 아닌 레포에 conventions 블록이 생겼다"


def test_partial_conventions_is_drift_but_rules_block_is_still_written(tmp_path, capsys):
    """kit 레포의 **부분** 드리프트는 red 로 유지하되, 규범 블록은 기록한다.

    `CONVENTIONS_INLINE`이 일부만 있으면 그건 실제 드리프트이므로 조용히 넘기지
    않는다 — 전용 종료코드 3과 stderr 경고로 구분한다.
    """
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    conv = target / "docs" / "conventions"
    conv.mkdir(parents=True)
    (conv / _mod.CONVENTIONS_INLINE[0][0]).write_text("# 하나만 있다\n", encoding="utf-8")

    rc = _mod.main(["--plugin-root", str(root), "--target", str(target)])
    assert rc == 3, "부분 드리프트가 green 이거나 일반 실패와 구별되지 않는다"
    err = capsys.readouterr().err
    assert "conventions 블록을 건너뛴다" in err, "조용히 넘어갔다"
    assert "kit:begin" in (target / "AGENTS.md").read_text(encoding="utf-8"), (
        "conventions 실패가 규범 블록 기록을 막았다 (ATK-003)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# ATK-010 — 구/신 마커 공존은 영구 red 가 아니라 이행 경로다
# ─────────────────────────────────────────────────────────────────────────────


def _seed_legacy_duplicate(target: Path, *, old: str = "kit", new: str = "cck") -> str:  # old-name-ok: 구 마커 인식 = 이행 경로
    """정상 생성물의 블록을 구 토큰으로 복제해 구 1 + 신 1 공존 상태를 만든다."""
    import re as _re

    path = target / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    b = _re.search(rf"^<!-- {old}:begin .*-->$", text, _re.MULTILINE)
    e = _re.search(rf"^<!-- {old}:end -->$", text, _re.MULTILINE)
    block = text[b.start() : e.end()]
    legacy = block.replace(f"{old}:begin", f"{new}:begin").replace(
        f"{old}:end", f"{new}:end"
    )
    marker = "USER-CONTENT-MUST-SURVIVE"
    path.write_text(f"{legacy}\n\n{marker}\n\n{text}", encoding="utf-8")
    return marker


def test_legacy_and_new_block_coexistence_is_migrated_not_refused(tmp_path):
    """구 토큰 블록 1개 + 신 토큰 블록 1개는 **구 블록을 제거하고 신 블록을 갱신**한다.

    수정 전에는 `begins=2, ends=2` → MarkerError → 재생성으로도 못 고치는 영구 red였다
    (LESSONS에 x3로 등재된 패턴). 마커 밖 사용자 콘텐츠는 그대로 살아 있어야 한다.
    """
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(
        ["--plugin-root", str(root), "--target", str(target), "--entrypoints", "AGENTS.md"]
    ) == 0
    marker = _seed_legacy_duplicate(target)

    rc = _mod.main(
        ["--plugin-root", str(root), "--target", str(target), "--entrypoints", "AGENTS.md"]
    )
    assert rc == 0, "이행 가능한 공존이 거부됐다 — 영구 red"
    body = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "cck:begin" not in body, "구 토큰 블록이 남았다"  # old-name-ok: 구 마커 인식 = 이행 경로
    assert body.count("<!-- kit:begin") == 1
    assert marker in body, "마커 밖 사용자 콘텐츠가 삭제됐다"

    # 재생성 후 --check가 초록이어야 "재생성으로 고쳐진다"가 실제로 참이다.
    assert _mod.main(
        ["--plugin-root", str(root), "--target", str(target),
         "--entrypoints", "AGENTS.md", "--check"]
    ) == 0


def test_check_reports_legacy_coexistence_as_drift_not_green(tmp_path, capsys):
    """`--check`는 공존을 **초록으로 넘기지 않는다** — 그러면 구 블록이 영구히 남는다."""
    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(
        ["--plugin-root", str(root), "--target", str(target), "--entrypoints", "AGENTS.md"]
    ) == 0
    _seed_legacy_duplicate(target)

    rc = _mod.main(
        ["--plugin-root", str(root), "--target", str(target),
         "--entrypoints", "AGENTS.md", "--check"]
    )
    assert rc == 1
    assert "공존" in capsys.readouterr().err, "공존을 다른 실패와 구별해 보고하지 않는다"


def test_other_marker_corruption_is_still_refused(tmp_path):
    """이행 경로는 **구 1 + 신 1** 한 형태만이다. 그 외 손상은 지금처럼 거부한다.

    추측해서 고치면 사용자 콘텐츠를 잃는다 — 생성기는 해석이 하나가 아닐 때 멈춘다.
    """
    import re as _re

    root = _minimal(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    assert _mod.main(
        ["--plugin-root", str(root), "--target", str(target), "--entrypoints", "AGENTS.md"]
    ) == 0
    path = target / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    # begin 만 하나 더 (짝 없는 구 begin) — begins=2, ends=1
    b = _re.search(r"^<!-- kit:begin .*-->$", text, _re.MULTILINE)
    path.write_text(
        text[: b.start()] + b.group(0).replace("kit:", "cck:") + "\n" + text[b.start() :],  # old-name-ok: 구 마커 인식 = 이행 경로
        encoding="utf-8",
    )
    before = path.read_text(encoding="utf-8")

    rc = _mod.main(
        ["--plugin-root", str(root), "--target", str(target), "--entrypoints", "AGENTS.md"]
    )
    assert rc == 1, "해석이 여럿인 손상을 추측해서 고쳤다"
    assert path.read_text(encoding="utf-8") == before, "거부했는데 파일이 바뀌었다"


# ─────────────────────────────────────────────────────────────────────────────
# ATK-016 — 이름은 매니페스트에서 파생한다. 마커 토큰은 불변이다.
# ─────────────────────────────────────────────────────────────────────────────


def _kit_copy_with_manifest_name(tmp_path: Path, name: str, homepage: str) -> ModuleType:
    """이 플러그인을 복사해 매니페스트 이름만 바꾼 뒤 그 사본 모듈을 로드한다.

    이름 파생은 **import 시점**에 매니페스트를 읽으므로, 상수를 몽키패치하는 대신
    실제 매니페스트를 바꿔 로드해야 파생 경로가 실제로 도는지 확인된다.
    """
    import json
    import shutil

    dst = tmp_path / "common"
    shutil.copytree(HOOKS_DIR.parent, dst)
    mp = dst / ".claude-plugin" / "plugin.json"
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    manifest["name"] = name
    manifest["homepage"] = homepage
    mp.write_text(json.dumps(manifest), encoding="utf-8")

    spec = importlib.util.spec_from_file_location(
        f"export_harness_{name}", dst / "hooks" / "export_harness.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.__dict__["_KIT_COPY_ROOT"] = dst
    return mod


def test_kit_name_and_homepage_are_derived_from_the_manifest(tmp_path):
    """개명 시 헤더가 따라간다 (ATK-016).

    하드코딩이면 개명 때 **모든 소비자의 AGENTS.md** 가 옛 이름을 영구히 광고한다 —
    이 레포는 이름을 매니페스트에서 파생하는 정책(§18/§20 게이트)을 갖고 있다.
    """
    mod = _kit_copy_with_manifest_name(
        tmp_path, "renamed-kit", "https://example.invalid/renamed-kit"
    )
    assert mod.KIT_NAME == "renamed-kit"
    block, _ = mod.build_block(mod.__dict__["_KIT_COPY_ROOT"])
    assert "## renamed-kit — 하네스 중립 규범" in block, "블록 헤더가 파생되지 않았다"
    assert "[renamed-kit](https://example.invalid/renamed-kit)" in block
    assert "hiway-kit" not in block, "구 이름이 생성물에 남았다"


def test_marker_token_is_never_derived(tmp_path):
    """마커 토큰은 이름이 아니라 생성물의 **구조**다 — 개명해도 불변이어야 한다.

    파생시키면 기존 소비자의 AGENTS.md 가 전부 "마커 없음"으로 읽혀 새 블록이 덧붙고,
    낡은 규범 본문이 고아로 남는다.
    """
    mod = _kit_copy_with_manifest_name(
        tmp_path, "renamed-kit", "https://example.invalid/renamed-kit"
    )
    block, _ = mod.build_block(mod.__dict__["_KIT_COPY_ROOT"])
    assert block.startswith("<!-- kit:begin rules-v"), "마커 토큰이 개명에 끌려갔다"
    assert mod.END_MARK == "<!-- kit:end -->"
    assert mod.CONV_END_MARK == "<!-- kit2:end -->"
    assert "renamed-kit:begin" not in block


def test_manifest_read_failure_does_not_break_the_tool(tmp_path):
    """매니페스트를 못 읽어도 도구는 동작한다 (fail-open) — 훅은 소비자 환경에서 자족한다."""
    import shutil

    dst = tmp_path / "common"
    shutil.copytree(HOOKS_DIR.parent, dst)
    (dst / ".claude-plugin" / "plugin.json").unlink()
    spec = importlib.util.spec_from_file_location(
        "export_harness_nomanifest", dst / "hooks" / "export_harness.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.KIT_NAME == "kit", "폴백 이름이 적용되지 않았다"
    block, _ = mod.build_block(dst)
    assert "<!-- kit:begin rules-v" in block


# ─────────────────────────────────────────────────────────────────────────────
# 이식 불가 표의 에이전트 수는 **세어서** 적는다 (리터럴 33 이 32 로 줄어도 안 고쳐졌다)
# ─────────────────────────────────────────────────────────────────────────────


def _plugin_root_with_agents(tmp_path, count: int):
    """rules/ 와 agents/ 를 갖춘 최소 플러그인 루트."""
    root = tmp_path / "common"
    (root / "rules").mkdir(parents=True)
    (root / "rules" / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (root / "rules" / "sample.md").write_text(
        "---\ntier: core\nportable: true\n---\n\n# Sample\n\nbody\n", encoding="utf-8"
    )
    agents = root / "agents" / "dev"
    agents.mkdir(parents=True)
    for i in range(count):
        (agents / f"a{i}.md").write_text("---\nname: a\n---\n", encoding="utf-8")
    return root


def test_agent_count_in_block_is_counted_not_literal(tmp_path):
    """에이전트를 하나 더하면 표의 수가 따라 움직여야 한다 — 리터럴이면 여기서 실패한다."""
    import export_harness as eh

    root = _plugin_root_with_agents(tmp_path, 7)
    block, _ = eh.build_block(root)
    assert "서브에이전트 정의 (7종)" in block

    (root / "agents" / "dev" / "extra.md").write_text("---\nname: b\n---\n", encoding="utf-8")
    block2, _ = eh.build_block(root)
    assert "서브에이전트 정의 (8종)" in block2


def test_agent_count_is_omitted_when_uncountable(tmp_path):
    """셀 수 없으면 수를 **안 적는다**. '0종' 은 그 자체가 거짓말이다.

    설치 형태에 따라 `agents/` 가 없을 수 있고, 그때 "(0종)" 을 적으면 생성물이 소비자에게
    거짓을 말한다 — 이 표는 다른 하네스가 읽는 **사실**이 되는 자리다.
    """
    import shutil

    import export_harness as eh

    root = _plugin_root_with_agents(tmp_path, 3)
    shutil.rmtree(root / "agents")
    block, _ = eh.build_block(root)
    assert "서브에이전트 정의 |" in block
    assert "종)" not in block.split("서브에이전트 정의")[1].split("|")[0]
