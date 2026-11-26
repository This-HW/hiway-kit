"""Tests for protect-sensitive.py hook."""

import importlib.util
import json
import os
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "common" / "hooks"
_spec = importlib.util.spec_from_file_location(
    "protect_sensitive", HOOKS_DIR / "protect-sensitive.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["protect_sensitive"] = _mod
_spec.loader.exec_module(_mod)

check_protected = _mod.check_protected
check_content_sensitive = _mod.check_content_sensitive


def run_main(input_data: dict) -> int:
    """Run main() with given stdin JSON, return the exit code."""
    stdin_text = json.dumps(input_data)
    with patch("sys.stdin", StringIO(stdin_text)):
        try:
            _mod.main()
        except SystemExit as e:
            return e.code
    return 0


class TestCheckProtected:
    def test_env_file_blocked(self):
        blocked, msg = check_protected(".env")
        assert blocked
        assert msg

    def test_env_local_blocked(self):
        blocked, _ = check_protected(".env.local")
        assert blocked

    def test_env_production_blocked(self):
        blocked, _ = check_protected(".env.production")
        assert blocked

    def test_secrets_dir_blocked(self):
        blocked, _ = check_protected("/app/secrets/db.json")
        assert blocked

    def test_credential_file_blocked(self):
        blocked, _ = check_protected("/fixture/account/credentials.json")
        assert blocked

    def test_ssh_dir_blocked(self):
        blocked, _ = check_protected("/fixture/account/.ssh/id_rsa")
        assert blocked

    def test_aws_config_blocked(self):
        blocked, _ = check_protected("/fixture/account/.aws/credentials")
        assert blocked

    def test_pem_file_blocked(self):
        blocked, _ = check_protected("/certs/server.pem")
        assert blocked

    def test_npmrc_blocked(self):
        blocked, _ = check_protected("/fixture/account/.npmrc")
        assert blocked

    def test_token_file_blocked(self):
        blocked, _ = check_protected("/config/api_token.json")
        assert blocked

    def test_password_file_blocked(self):
        blocked, _ = check_protected("/config/my_password.txt")
        assert blocked

    # --- token/password 파일명 협소화 (외부 사용 보고 2026-07-31) ---
    # 정탐 유지: 자격증명 관례 결합형은 계속 차단
    def test_token_credential_shapes_still_blocked(self):
        for p in [
            "/config/token.json",
            "/fixture/account/.token",
            "/config/.tokens",
            "/repo/github-token.txt",
            "/repo/my_tokens.yaml",
            "/etc/app/token",  # 확장자 없는 정확명
            "/config/passwords.yml",
            "/config/user-password.txt",
        ]:
            blocked, _ = check_protected(p)
            assert blocked, f"정탐 후퇴: {p} 는 차단돼야 함"

    # 오탐 해소: 산문 복합어·소스 파일은 통과
    def test_token_prose_and_source_filenames_allowed(self):
        for p in [
            "/blog/token-efficiency-discipline.md",  # 보고된 실사례
            "/docs/tokens-and-context-windows.md",
            "/src/tokenizer.py",
            "/lib/oauth/token.py",  # 소스 파일 (oauthlib 관례)
            "/src/token_utils.py",
            "/docs/password-reset-flow.md",
        ]:
            blocked, msg = check_protected(p)
            assert not blocked, f"오탐 재발: {p} 가 차단됨 ({msg})"

    def test_normal_python_file_allowed(self):
        blocked, _ = check_protected("/app/src/main.py")
        assert not blocked

    def test_normal_json_file_allowed(self):
        blocked, _ = check_protected("/app/config/settings.json")
        assert not blocked

    def test_readme_allowed(self):
        blocked, _ = check_protected("/app/README.md")
        assert not blocked

    def test_secret_named_source_file_is_not_blocked(self):
        # 2026-11-09 뒤집음: 예전에는 이름에 'secret' 이 든 소스도 막았다. 외부 설치 보고에서
        # secret_manager.py·credential_collector.py·SP 정의가 막혀 에이전트가 Bash cat 으로
        # 우회했다. 소스·문서는 통과, 같은 이름의 데이터·설정 파일은 계속 차단.
        blocked, _ = check_protected("/app/src/secrets_manager.py")
        assert not blocked
        blocked, _ = check_protected("/app/src/secrets_manager.json")
        assert blocked

    def test_kube_config_blocked(self):
        blocked, _ = check_protected("/fixture/account/.kube/config")
        assert blocked


class TestCheckContentSensitive:
    def test_sk_api_key_blocked(self):
        sensitive, msg = check_content_sensitive("my key is sk-abcdefghij1234567890xyz")
        assert sensitive
        assert "API 키" in msg

    def test_aws_access_key_blocked(self):
        sensitive, _ = check_content_sensitive("AKIAIOSFODNN7EXAMPLE here")
        assert sensitive

    def test_github_token_blocked(self):
        sensitive, _ = check_content_sensitive("token: ghp_" + "a" * 36)
        assert sensitive

    def test_ssh_private_key_blocked(self):
        sensitive, _ = check_content_sensitive("-----BEGIN RSA PRIVATE KEY-----")
        assert sensitive

    def test_postgres_url_with_creds_blocked(self):
        sensitive, _ = check_content_sensitive("postgres://user:pass@localhost/db")
        assert sensitive

    def test_non_string_content_serialized_not_fail_open(self):
        # 적대적 리뷰 P1: 구조화(list/dict) payload에 re.search가 TypeError→fail-open하던 것.
        # str()로 강제 직렬화해 스캔하므로 크래시 없이 탐지되어야 한다.
        sensitive, _ = check_content_sensitive(
            [{"text": "key sk-abcdefghij1234567890xyz"}]
        )
        assert sensitive
        # 민감정보 없는 구조화 payload는 통과(크래시 없음)
        clean, _ = check_content_sensitive({"note": "hello world"})
        assert not clean

    def test_jwt_blocked(self):
        # Minimal valid-looking JWT
        header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        payload = "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0"
        sig = "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        sensitive, _ = check_content_sensitive(f"{header}.{payload}.{sig}")
        assert sensitive

    def test_clean_content_allowed(self):
        sensitive, _ = check_content_sensitive("Hello world, here is my code review.")
        assert not sensitive

    def test_empty_content_allowed(self):
        sensitive, _ = check_content_sensitive("")
        assert not sensitive


class TestMainIntegration:
    def test_edit_env_file_blocked(self):
        code = run_main({"tool_name": "Edit", "tool_input": {"file_path": ".env"}})
        assert code == 2

    def test_write_env_file_blocked(self):
        code = run_main(
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/.env"}}
        )
        assert code == 2

    def test_read_normal_file_allowed(self):
        code = run_main(
            {"tool_name": "Read", "tool_input": {"file_path": "/app/main.py"}}
        )
        assert code == 0

    def test_other_tool_allowed(self):
        code = run_main({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert code == 0

    def test_read_env_message_does_not_claim_edit(self, capsys):
        """Read 차단 메시지가 "수정할 수 없다"로 읽기 차단을 잘못 설명하지 않는다."""
        assert run_main({"tool_name": "Read", "tool_input": {"file_path": ".env"}}) == 2
        err = capsys.readouterr().err
        assert "수정할 수 없" not in err
        assert "읽기" in err

    def test_removed_agent_teams_tools_are_not_scanned(self):
        """Agent Teams(message/broadcast)는 제거됐다 — 그 분기와 matcher 가 남지 않는다."""
        code = run_main(
            {"tool_name": "message", "tool_input": {"content": "sk-" + "a" * 30}}
        )
        assert code == 0
        manifest = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
        matchers = [
            e.get("matcher", "")
            for e in manifest["hooks"]["PreToolUse"]
            if "protect-sensitive.py" in json.dumps(e)
        ]
        assert matchers
        for m in matchers:
            assert not {"message", "broadcast"} & set(m.split("|")), m

    def test_malformed_json_allows(self):
        with patch("sys.stdin", StringIO("not valid json")):
            try:
                _mod.main()
            except SystemExit as e:
                assert e.code == 0

    def test_missing_file_path_allows(self):
        code = run_main({"tool_name": "Edit", "tool_input": {}})
        assert code == 0


class TestEnvTemplateException:
    """env 템플릿 파일(.env.example 등)은 과차단 예외 대상이다 (W-016 FR-1)."""

    def test_env_example_allowed(self):
        blocked, _ = check_protected(".env.example")
        assert not blocked

    def test_env_sample_allowed(self):
        blocked, _ = check_protected(".env.sample")
        assert not blocked

    def test_env_template_allowed(self):
        blocked, _ = check_protected(".env.template")
        assert not blocked

    def test_env_dist_allowed(self):
        blocked, _ = check_protected(".env.dist")
        assert not blocked

    def test_env_local_example_allowed(self):
        blocked, _ = check_protected(".env.local.example")
        assert not blocked

    def test_env_example_absolute_path_allowed(self):
        blocked, _ = check_protected("/repo/project/.env.example")
        assert not blocked

    def test_env_file_still_blocked(self):
        blocked, _ = check_protected(".env")
        assert blocked

    def test_env_local_still_blocked(self):
        blocked, _ = check_protected(".env.local")
        assert blocked

    def test_env_production_still_blocked(self):
        blocked, _ = check_protected(".env.production")
        assert blocked

    def test_env_example_backup_still_blocked(self):
        # 정확 suffix 매치가 아닌 뒤붙임 변형은 계속 차단 (2.10.5)
        blocked, _ = check_protected(".env.example.backup")
        assert blocked

    def test_secret_prefixed_template_name_still_blocked(self):
        # ATK-001 회귀: 좌측 미앵커면 보호 파일명에 템플릿 접미사만 붙여 예외가 열린다
        blocked, _ = check_protected("secret.env.example")
        assert blocked

    def test_credentials_prefixed_template_name_still_blocked(self):
        # ATK-001 회귀: credential 패턴 차단이 템플릿 접미사로 무력화되면 안 된다
        blocked, _ = check_protected("credentials.env.template")
        assert blocked


class TestEnvTemplateMainIntegration:
    """Read/Edit/Write/MultiEdit 각 도구에서 env 템플릿 예외가 적용되는지 확인."""

    def test_read_env_example_allowed(self):
        code = run_main(
            {"tool_name": "Read", "tool_input": {"file_path": ".env.example"}}
        )
        assert code == 0

    def test_edit_env_example_allowed(self):
        code = run_main(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": ".env.example",
                    "old_string": "FOO=bar",
                    "new_string": "FOO=baz",
                },
            }
        )
        assert code == 0

    def test_write_env_sample_allowed(self):
        code = run_main(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/tmp/.env.sample",
                    "content": "API_KEY=your_key_here",
                },
            }
        )
        assert code == 0

    def test_multiedit_env_template_allowed(self):
        code = run_main(
            {
                "tool_name": "MultiEdit",
                "tool_input": {
                    "file_path": ".env.template",
                    "edits": [{"old_string": "FOO=bar", "new_string": "FOO=baz"}],
                },
            }
        )
        assert code == 0

    def test_env_symlink_to_real_env_still_blocked(self):
        # ATK-007 회귀 테스트: .env.example이라는 이름의 symlink가 실제 .env를 가리키면
        # realpath 재검사가 차단해야 한다.
        with tempfile.TemporaryDirectory() as tmpdir:
            real_env = os.path.join(tmpdir, ".env")
            with open(real_env, "w") as f:
                f.write("SECRET=abc123")
            symlink_path = os.path.join(tmpdir, ".env.example")
            os.symlink(real_env, symlink_path)

            code = run_main(
                {"tool_name": "Read", "tool_input": {"file_path": symlink_path}}
            )
            assert code == 2


class TestEnvTemplateContentScan:
    """FR-4: env 템플릿 쓰기 시 high-confidence 형식 시크릿만 차단, placeholder는 허용."""

    def test_write_real_secret_key_blocked(self):
        code = run_main(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": ".env.example",
                    # 대입 형태 원문은 gitleaks generic-api-key에 걸린다(M-1) — 런타임에 조립
                    "content": "OPENAI_API_KEY=" + "sk-" + "abcdefghij1234567890xyz",
                },
            }
        )
        assert code == 2

    def test_write_placeholder_allowed(self):
        code = run_main(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": ".env.example",
                    "content": "API_KEY=your_key_here",
                },
            }
        )
        assert code == 0

    def test_write_via_symlink_to_template_scanned(self):
        # 스캔은 원본 경로뿐 아니라 realpath에도 적용 — 비템플릿 이름의 symlink
        # (notes.txt → .env.example)를 경유한 실제 시크릿 기록도 차단해야 한다.
        with tempfile.TemporaryDirectory() as tmpdir:
            template = os.path.join(tmpdir, ".env.example")
            with open(template, "w") as f:
                f.write("API_KEY=your_key_here")
            symlink_path = os.path.join(tmpdir, "notes.txt")
            os.symlink(template, symlink_path)

            code = run_main(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": symlink_path,
                        # 대입 형태 원문은 gitleaks generic-api-key에 걸린다(M-1) — 런타임에 조립
                        "content": "OPENAI_API_KEY="
                        + "sk-"
                        + "abcdefghij1234567890xyz",
                    },
                }
            )
            assert code == 2

    def test_edit_new_string_with_aws_key_blocked(self):
        code = run_main(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": ".env.example",
                    "old_string": "AWS_ACCESS_KEY_ID=",
                    "new_string": "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
                },
            }
        )
        assert code == 2

    def test_write_anthropic_key_blocked(self):
        code = run_main(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": ".env.example",
                    "content": "KEY=" + "sk-ant-" + "api03-abcdefghij1234567890",
                },
            }
        )
        assert code == 2

    def test_write_stripe_key_blocked(self):
        code = run_main(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": ".env.example",
                    "content": "KEY=" + "sk_live_" + "abcdefghij1234567890",
                },
            }
        )
        assert code == 2

    def test_write_google_key_blocked(self):
        code = run_main(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": ".env.example",
                    "content": "KEY=" + "AIza" + "SyA1234567890abcdefghij_-ABCDEFGHIJK",
                },
            }
        )
        assert code == 2


class TestEnvTemplateContentScanNonStrPayload:
    """ATK-002 회귀: 비-str payload가 join TypeError → fail-open으로 스캔을 우회하면 안 된다."""

    def test_notebook_list_source_scanned(self):
        # nbformat 표준 셀 소스(줄 단위 문자열 리스트) 형태
        code = run_main(
            {
                "tool_name": "NotebookEdit",
                "tool_input": {
                    "notebook_path": ".env.example",
                    "new_source": ["KEY=" + "sk-" + "abcdefghij1234567890xyz"],
                },
            }
        )
        assert code == 2

    def test_write_dict_content_scanned(self):
        code = run_main(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": ".env.example",
                    "content": {"KEY": "sk-" + "abcdefghij1234567890xyz"},
                },
            }
        )
        assert code == 2

    def test_multiedit_non_dict_edit_item_scanned(self):
        code = run_main(
            {
                "tool_name": "MultiEdit",
                "tool_input": {
                    "file_path": ".env.example",
                    "edits": ["KEY=" + "sk-" + "abcdefghij1234567890xyz"],
                },
            }
        )
        assert code == 2

    def test_multiedit_non_list_edits_field_scanned(self):
        # edits 필드 자체가 list가 아닌 스키마 밖 형태 — 문자 단위 순회로 페이로드가
        # 쪼개져 스캔이 무력화되면 안 된다 (재검증 LOW 관찰 하드닝)
        code = run_main(
            {
                "tool_name": "MultiEdit",
                "tool_input": {
                    "file_path": ".env.example",
                    "edits": "KEY=" + "sk-" + "abcdefghij1234567890xyz",
                },
            }
        )
        assert code == 2


# 외부 설치 보고(2026-11-09, Snowflake SP·PySpark 레포): 이름 키워드가 소스·SQL·문서를 막았다.
FEEDBACK_SOURCE_PATHS = [
    "etl/collectors/credential_collector.py",
    "sql/sp/SP_UPDATE_USER_CREDENTIALS.sql",
    "docs/credential-rotation.md",
    "src/auth/secret_manager.py",
    "sql/sp/sp_rotate_secret.sql",
    "src/crypto/private_key_loader.py",
    # macOS: /tmp·$TMPDIR 의 실경로가 /private/... — 'private.*key' 가 경로 전체에 걸려 막혔다
    "/private/tmp/project/monkey.py",
    "/private/var/folders/x/T/keymap.json",
]

STILL_BLOCKED_STORES = [
    "credentials.json",
    "/fixture/account/.aws/credentials",
    "config/gcp-credentials.json",
    "aws_credentials",
    "client_secret.json",
    "deploy/secrets.yaml",
    "app/secrets/db.py",  # secrets 디렉토리는 확장자와 무관하게 막는다
    "scripts/export_secrets.sh",  # 셸은 시크릿을 export 하는 자리라 제외하지 않는다
    "infra/secrets.tf",
    "credentials.env.template",
    "keys/my_private_key",
    "certs/server.key",
    ".env",
    # 시크릿 모듈 — 이름이 키워드·수식어뿐이면 소스 확장자여도 막는다(2026-11-09 보안 점검)
    "secrets.py",
    "credentials.py",
    "settings_secrets.py",
    "config/secrets.js",
    "config.secret.ts",
    "prod.secret.md",
    "config/initializers/secret_token.rb",
    "credentials.sql",
    "credentials_backup.sql",
    "credentials.json.py",
    "api_secret.py",
    "private_key.py",
    # 이름 그대로인 디렉토리
    "credentials/prod.py",
    "secret/db.py",
    # 노트북은 출력 셀에 값이 남는다 — 소스 예외가 아니다
    "notebooks/credential_check.ipynb",
]


@pytest.mark.parametrize("path", FEEDBACK_SOURCE_PATHS)
def test_source_and_doc_files_named_after_credentials_pass(path):
    blocked, _ = check_protected(path)
    assert not blocked, path


@pytest.mark.parametrize("path", STILL_BLOCKED_STORES)
def test_real_secret_stores_stay_blocked(path):
    blocked, _ = check_protected(path)
    assert blocked, path


# ── 판정 입력의 타입 혼동은 fail-closed (ECC 조사 runtime #5a, 2026-11-21) ──────────────
# 수정 전: `{"file_path": [".env"]}` 가 `.lower()` 에서 AttributeError → blanket except → exit 0
# (허용). 같은 경로를 문자열로 주면 exit 2 — 판정이 **타입 하나로** 열렸다. 아래는 그 경계를
# 서브프로세스(실제 훅 실행)와 main() 양쪽에서 고정한다.

_HOOK = HOOKS_DIR / "protect-sensitive.py"


def _run_hook_process(payload: str) -> int:
    import subprocess

    env = {k: v for k, v in os.environ.items() if k != "HIWAY_KIT_DISABLE_HOOKS"}
    return subprocess.run(
        [sys.executable, str(_HOOK)], input=payload, text=True,
        capture_output=True, env=env, check=False, timeout=30,
    ).returncode


class TestNonStringPathFailClosed:
    def test_list_path_blocked_by_real_hook_process(self):
        """브리프의 재현 명령 그대로 — 리스트형 file_path 는 rc=2."""
        assert _run_hook_process('{"tool_name":"Read","tool_input":{"file_path":[".env"]}}') == 2

    def test_string_path_positive_control(self):
        """양성 대조 — 같은 경로를 문자열로 주면 원래도 막혔다(rc=2)."""
        assert _run_hook_process('{"tool_name":"Read","tool_input":{"file_path":".env"}}') == 2

    def test_harmless_list_path_also_blocked(self):
        """경로 값이 무해해도 타입이 틀리면 판정할 수 없다 — 내용이 아니라 타입으로 막는다."""
        assert run_main({"tool_name": "Read", "tool_input": {"file_path": ["README.md"]}}) == 2

    @pytest.mark.parametrize("value", [{"p": ".env"}, 1, 0, True, False, [], {}])
    def test_non_string_values_blocked(self, value):
        """거짓 값([]·0·False·{})도 '없음'이 아니다 — 없음은 키 부재나 null 뿐이다."""
        assert run_main({"tool_name": "Write", "tool_input": {"file_path": value}}) == 2

    @pytest.mark.parametrize("tool", ["Edit", "MultiEdit", "Write", "Read", "NotebookEdit"])
    def test_every_watched_tool(self, tool):
        assert run_main({"tool_name": tool, "tool_input": {"file_path": [".env"]}}) == 2

    def test_notebook_path_non_string_blocked(self):
        assert run_main({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": [".env"]}}) == 2

    def test_tool_input_not_object_blocked(self):
        assert run_main({"tool_name": "Read", "tool_input": [".env"]}) == 2
        assert run_main({"tool_name": "Read", "tool_input": ".env"}) == 2

    def test_second_path_field_is_judged_too(self):
        """수정 전에는 `file_path or notebook_path` 로 하나만 봤다 — 앞이 무해하면 뒤는 판정 밖."""
        assert run_main({
            "tool_name": "NotebookEdit",
            "tool_input": {"file_path": "notes.ipynb", "notebook_path": ".env"},
        }) == 2

    # ── 음성 대조: 경로가 없는 정상 케이스는 기존대로 허용 ──
    @pytest.mark.parametrize("tool_input", [{}, {"file_path": None}, {"file_path": ""}, None])
    def test_absent_path_still_allowed(self, tool_input):
        payload = {"tool_name": "Read"}
        if tool_input is not None:
            payload["tool_input"] = tool_input
        assert run_main(payload) == 0

    def test_tool_input_null_allowed(self):
        assert run_main({"tool_name": "Read", "tool_input": None}) == 0

    def test_unwatched_tool_untouched(self):
        """감시 대상 밖 도구는 타입과 무관하게 이 훅의 판정 밖이다."""
        assert run_main({"tool_name": "Bash", "tool_input": {"file_path": [".env"]}}) == 0

    def test_normal_string_path_allowed(self):
        assert run_main({"tool_name": "Read", "tool_input": {"file_path": "README.md"}}) == 0

    def test_block_message_does_not_echo_value(self, capsys):
        """차단 메시지는 필드 이름·타입만 — 값(경로)은 찍지 않는다(warning-signal §검토 6)."""
        assert run_main({"tool_name": "Read", "tool_input": {"file_path": ["topsecret-value"]}}) == 2
        err = capsys.readouterr().err
        assert "file_path" in err and "list" in err
        assert "topsecret-value" not in err

    def test_hook_errors_still_fail_open(self):
        """훅 자체 오류의 fail-open 은 유지 — 깨진 JSON 은 허용."""
        with patch("sys.stdin", StringIO("{not json")), pytest.raises(SystemExit) as exc:
            _mod.main()
        assert exc.value.code == 0

    def test_docstring_states_undetectable_limits(self):
        """한계 문서화 — Bash 경유·하드링크는 이 훅의 범위 밖이라고 적혀 있다."""
        doc = _mod.__doc__
        assert "탐지할 수 없는 것" in doc
        assert "Bash" in doc and "하드링크" in doc


# ── Grep (보안 리뷰 M-2, 5.9.0) ────────────────────────────────────────────────
# 수정 전: Grep 은 감시 대상이 아니었다(hooks.json matcher 밖·WATCHED_TOOLS 밖) — `Grep(path=".env")`
# 로 `.env` 내용을 읽을 수 있었다. 판정은 **파일 하나를 지목할 때만** 한다(독스트링 "탐지할 수 없는 것").


def _grep(tmp_path, **tool_input) -> int:
    return run_main({"tool_name": "Grep", "cwd": str(tmp_path), "tool_input": tool_input})


class TestGrep:
    def test_matcher_covers_every_watched_tool(self):
        """hooks.json matcher 와 WATCHED_TOOLS 는 같은 집합이다 — 한쪽만 고치면 훅이 안 불리거나 판정이 빈다."""
        hooks = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
        matchers = [
            entry["matcher"]
            for entry in hooks["hooks"]["PreToolUse"]
            if any("protect-sensitive.py" in a for h in entry["hooks"] for a in h.get("args", []))
        ]
        assert len(matchers) == 1
        assert set(matchers[0].split("|")) == set(_mod.WATCHED_TOOLS)
        assert "Grep" in _mod.WATCHED_TOOLS

    @pytest.mark.parametrize("path", [".env", ".env.local", "config/.env", "~/.ssh/id_rsa", "secrets/db.yml"])
    def test_grep_on_sensitive_file_blocked(self, tmp_path, path):
        assert _grep(tmp_path, pattern="KEY", path=path) == 2

    def test_grep_on_existing_sensitive_file_blocked(self, tmp_path):
        (tmp_path / ".env").write_text("A=1\n")
        assert _grep(tmp_path, pattern="A", path=str(tmp_path / ".env")) == 2

    def test_grep_symlink_to_env_blocked(self, tmp_path):
        """realpath 2단 검사 — 무해한 이름의 링크가 `.env` 를 가리키면 막는다."""
        (tmp_path / ".env").write_text("A=1\n")
        (tmp_path / "notes.txt").symlink_to(tmp_path / ".env")
        assert _grep(tmp_path, pattern="A", path=str(tmp_path / "notes.txt")) == 2

    @pytest.mark.parametrize("glob", [".env", "**/.env", ".env*", "*.env", ".env.*", "[.]env",
                                      "*.pem", "{*.md,.env}", "config/.env.production"])
    def test_grep_glob_naming_a_sensitive_file_blocked(self, tmp_path, glob):
        """ripgrep `--glob` 은 `.gitignore` 를 무시한다 — `path="."` + `glob=".env"` 는 Read(.env) 다."""
        assert _grep(tmp_path, pattern="KEY", path=str(tmp_path), glob=glob) == 2

    @pytest.mark.parametrize("glob", ["*", "**", "**/*", "*env", "config/*", "src/**", ".e?v", "*.*",
                                      ".*", "*.key", ".env,*.md", "*.md .env", ".[Z-f]nv", "[^x]env",
                                      ".ENV", "*.KEY", "secrets/*.yaml", "**/secrets/*.yaml",
                                      "credentials/*.json", "[,.]e{n,x}v"])
    def test_grep_glob_selecting_a_sensitive_file_blocked(self, tmp_path, glob):
        """와일드카드 glob 이 보호 파일을 **고를 수 있으면** 막는다(5.9.0 리뷰). Claude Code 2.1.330 의
        ripgrep 14.1.1 실측: 무시된 `.env` 를 `-g '*'`·`'**'`·`'*env'`·`'config/*'` 가 모두 읽었다.
        수정 전에는 와일드카드를 지운 이름(`*env`→`env`, `*`→빈 이름)만 봐서 전부 통과했다.
        `.[Z-f]nv`·`[^x]env` 는 ripgrep 이 `.env` 를 고르고(실측), `secrets/*.yaml` 은 파일 단위로 무시된
        `secrets/prod.yaml` 을 읽었다(실측) — 디렉토리 부분까지 판정한다."""
        assert _grep(tmp_path, pattern="KEY", path=str(tmp_path), glob=glob) == 2

    @pytest.mark.parametrize(
        "glob",
        [".\\env", "{{.env}}", "{a,b", "[abc", "[z-a]", "}x", "{" + ",".join(f"x{i}" for i in range(300)) + "}"],
    )
    def test_grep_unjudgeable_glob_blocked(self, tmp_path, glob):
        """ripgrep 과 같은 뜻으로 풀 수 없는 glob 은 막는다 — 이스케이프(`.\\env` 를 ripgrep 은 `.env`
        로 읽었다), 중첩·짝 없는 괄호, 거꾸로 된 범위, 갈래 상한 초과(잘라 보면 뒤쪽 갈래가 열린다)."""
        assert _grep(tmp_path, pattern="KEY", path=str(tmp_path), glob=glob) == 2

    def test_grep_glob_judging_time_is_bounded(self, tmp_path):
        """상한 안의 glob 으로 판정 시간을 키우지 못한다 — 훅 timeout(10초)은 차단이 아니라서 시간이
        판정을 여는 길이 된다. 수정 전에는 이 입력이 약 3.8초 걸렸다(5.9.0 리뷰: `.*_rsa$` 의 이차
        백트래킹 × 긴 갈래 256개)."""
        import time

        glob = "{" + ",".join(["b"] * 255) + "}" + "a" * 3570 + " .env"
        start = time.monotonic()
        assert _grep(tmp_path, pattern="KEY", path=str(tmp_path), glob=glob) == 2
        assert time.monotonic() - start < 1.5

    def test_grep_glob_check_cannot_skip_the_file_check(self, tmp_path, monkeypatch):
        """파일 판정이 glob 판정보다 **먼저** 돈다 — glob 판정이 예외를 내도 `path=".env"` 는 막힌다.
        수정 전에는 Python 3.9 에서 `[Z-a]` 류 glob 이 `re.error` 로 fail-open 경로에 빠져 `.env` 판정까지
        건너뛰었다(5.9.0 리뷰)."""
        def boom(_glob):
            raise RuntimeError("glob judge failed")
        monkeypatch.setattr(_mod, "glob_block_reason", boom)
        assert _grep(tmp_path, pattern="KEY", path=".env", glob="[Z-a]") == 2

    def test_grep_dir_glob_block_suggests_path(self, tmp_path, capsys):
        assert _grep(tmp_path, pattern="x", path=str(tmp_path), glob="src/**") == 2
        assert "path='src'" in capsys.readouterr().err

    def test_glob_probes_are_protected_names(self):
        """`GLOB_PROBES` 는 Read 판정이 막는 이름이어야 한다 — 아니면 glob 판정이 파일 판정보다 넓어진다."""
        for probe in _mod.GLOB_PROBES:
            assert _mod.check_protected(probe)[0], probe

    @pytest.mark.parametrize("name", [".ssh", ".aws", ".gcp", ".azure", "secrets", "credentials", ".secrets"])
    def test_grep_credential_store_directory_blocked(self, tmp_path, name):
        """이름 자체가 보관소인 디렉토리는 디렉토리 검색도 막는다 — `Read(~/.ssh/id_rsa)` 는 막히는데
        `Grep(path="~/.ssh")` 로 그 내용을 읽을 수 있었다(5.9.0 리뷰)."""
        (tmp_path / name).mkdir()
        assert _grep(tmp_path, pattern="KEY", path=str(tmp_path / name)) == 2

    @pytest.mark.parametrize("name", [".ssh", ".aws", ".gcp", ".azure", "secrets", "credentials"])
    def test_credential_store_directories_are_fully_protected_for_read(self, name):
        """디렉토리 판정은 그 안의 파일 전부를 Read 판정이 이미 막는 이름에만 건다(판정 범위를 넓히지 않는다)."""
        assert _mod.check_protected(f"/fixture/account/{name}/anything.txt")[0]

    def test_grep_home_ssh_blocked(self, tmp_path, monkeypatch):
        (tmp_path / ".ssh").mkdir()
        monkeypatch.setenv("HOME", str(tmp_path))
        assert _grep(tmp_path, pattern="KEY", path="~/.ssh") == 2

    @pytest.mark.parametrize("store", [".ssh", ".kube", ".docker", ".config/gcloud"])
    def test_grep_over_a_directory_holding_a_home_store_blocked(self, tmp_path, monkeypatch, store):
        """홈의 보관소를 **품는** 디렉토리(홈·그 조상)도 막는다. Claude Code 의 Grep 은 ripgrep 을 `--hidden`
        으로 부르고 홈에는 보통 무시 규칙이 없어 `~/.ssh` 까지 검색된다(5.9.0 리뷰)."""
        home = tmp_path / "home"
        (home / store).mkdir(parents=True)
        (home / "proj").mkdir()
        monkeypatch.setenv("HOME", str(home))
        assert _grep(home, pattern="KEY", path="~") == 2
        assert _grep(home, pattern="KEY", path=str(tmp_path)) == 2  # 조상
        assert _grep(home, pattern="KEY") == 2  # path 없음 = cwd(홈)
        assert _grep(home / "proj", pattern="KEY") == 0  # 홈 아래 프로젝트는 그대로
        assert _grep(home, pattern="KEY", path=str(home / "proj")) == 0

    def test_grep_symlink_into_credential_store_blocked(self, tmp_path):
        """무해한 이름의 링크가 보관소 디렉토리를 가리키면 realpath 로 막는다."""
        (tmp_path / ".ssh").mkdir()
        (tmp_path / "keys").symlink_to(tmp_path / ".ssh")
        assert _grep(tmp_path, pattern="KEY", path=str(tmp_path / "keys")) == 2

    # ── 음성 대조: 정상 검색은 막지 않는다 ──
    def test_grep_source_directory_allowed(self, tmp_path):
        (tmp_path / "src").mkdir()
        assert _grep(tmp_path, pattern="def ", path=str(tmp_path / "src")) == 0
        assert _grep(tmp_path, pattern="def ", path="src") == 0  # cwd 기준 상대경로

    def test_grep_without_path_allowed(self, tmp_path):
        assert _grep(tmp_path, pattern="TODO") == 0

    @pytest.mark.parametrize("name", ["credential_collector", "secret_manager", ".docker", "src"])
    def test_grep_directory_named_like_secret_is_not_judged(self, tmp_path, name):
        """보관소 이름이 아닌 디렉토리는 판정 밖(문서화된 한계) — 이름에 credential 이 든 소스 디렉토리
        검색이 막히지 않는다."""
        (tmp_path / name).mkdir()
        assert _grep(tmp_path, pattern="x", path=str(tmp_path / name)) == 0

    @pytest.mark.parametrize("glob", ["*.py", "**/*.{ts,tsx}", "*.md", "!.env", ".env.example",
                                      "token-efficiency-*.md", "*.json", "*.yaml", "src/**/*.py",
                                      "*test*", "Dockerfile*", "*.py,*.md", "*.spec.ts", "test_*.py",
                                      "[abc]*.go", "!{.env,*.key}", "**/__tests__/**/*.ts",
                                      "app/[locale]/**/*.tsx", "*.{h,hpp}"])
    def test_grep_ordinary_glob_allowed(self, tmp_path, glob):
        assert _grep(tmp_path, pattern="x", path=str(tmp_path), glob=glob) == 0

    def test_grep_source_file_allowed(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert _grep(tmp_path, pattern="x", path=str(tmp_path / "app.py")) == 0

    @pytest.mark.parametrize("field", ["path", "glob"])
    @pytest.mark.parametrize("value", [[".env"], {"p": 1}, 0])
    def test_grep_non_string_field_blocked(self, tmp_path, field, value):
        assert _grep(tmp_path, pattern="x", **{field: value}) == 2

    def test_docstring_states_grep_limits(self):
        doc = _mod.__doc__
        assert "디렉토리 대상 Grep" in doc and "Glob" in doc


# ── 파싱 실패 (보안 리뷰 L-1, 5.9.0) ──────────────────────────────────────────


def _deep(tool: str, depth: int = 100_000) -> str:
    return (
        '{"tool_name":"' + tool + '","tool_input":{"file_path":".env","x":'
        + "[" * depth + "]" * depth + "}}"
    )


class TestParseFailure:
    def test_deep_nesting_on_watched_tool_blocked(self):
        """재현: 깊은 중첩 → json.load 가 RecursionError → 예전에는 blanket except 로 허용(rc 0)."""
        assert _run_hook_process(_deep("Read")) == 2

    def test_deep_nesting_on_unwatched_tool_allowed(self):
        assert _run_hook_process(_deep("Bash")) == 0

    def test_broken_json_on_watched_tool_blocked(self):
        assert _run_hook_process('{"tool_name":"Read","tool_input":{"file_path":".env"') == 2

    def test_escaped_tool_name_inside_a_string_is_not_sniffed(self):
        """문자열 안의 `\\"tool_name\\"` 는 최상위 키가 아니다 — 감시 밖 도구로 위장된 입력을 막지 않는다."""
        payload = '{"tool_name":"Bash","tool_input":{"command":"echo \\"tool_name\\":\\"Read\\""'
        assert _run_hook_process(payload) == 0

    def test_internal_error_still_fails_open(self):
        """경계: 판정 로직 자체의 예외는 기존대로 허용(fail-open)."""
        with patch.object(_mod, "check_protected", side_effect=RuntimeError("boom")):
            assert run_main({"tool_name": "Read", "tool_input": {"file_path": "README.md"}}) == 0
