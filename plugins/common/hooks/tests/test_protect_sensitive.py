"""Tests for protect-sensitive.py hook."""

import importlib.util
import json
import os
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

HOOKS_DIR = Path(__file__).resolve().parent.parent
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
        blocked, _ = check_protected("/home/user/credentials.json")
        assert blocked

    def test_ssh_dir_blocked(self):
        blocked, _ = check_protected("/home/user/.ssh/id_rsa")
        assert blocked

    def test_aws_config_blocked(self):
        blocked, _ = check_protected("/home/user/.aws/credentials")
        assert blocked

    def test_pem_file_blocked(self):
        blocked, _ = check_protected("/certs/server.pem")
        assert blocked

    def test_npmrc_blocked(self):
        blocked, _ = check_protected("/home/user/.npmrc")
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
            "/home/user/.token",
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

    def test_secrets_dir_in_path_but_not_secrets_subdir(self):
        # "secrets" substring in non-directory context
        blocked, _ = check_protected("/app/src/secrets_manager.py")
        # "secret" pattern — this contains "secret" so should be blocked
        # secrets_manager.py matches the secret pattern (but not secrets dir)
        # The pattern excludes "secrets/" dir and "secrets." ext, but "secrets_" is included
        assert blocked  # "secret" literal is present without exclusion match

    def test_kube_config_blocked(self):
        blocked, _ = check_protected("/home/user/.kube/config")
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

    def test_password_literal_blocked(self):
        sensitive, _ = check_content_sensitive("password=supersecret123")
        assert sensitive

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

    def test_message_with_secret_blocked(self):
        code = run_main(
            {
                "tool_name": "message",
                "tool_input": {"content": "my key sk-abcdefghij1234567890xyz"},
            }
        )
        assert code == 2

    def test_message_without_secret_allowed(self):
        code = run_main(
            {"tool_name": "message", "tool_input": {"content": "Hello agent, proceed."}}
        )
        assert code == 0

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
        # 정확 suffix 매치가 아닌 뒤붙임 변형은 계속 차단 (DEC-001)
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


class TestSensitivePatternsUnion:
    """ATK-006: message/broadcast 스캔 패턴 = high-confidence + 휴리스틱 합집합 고정."""

    def test_union_composition(self):
        assert list(_mod.SENSITIVE_CONTENT_PATTERNS) == (
            _mod.HIGH_CONFIDENCE_CONTENT_PATTERNS + _mod.HEURISTIC_CONTENT_PATTERNS
        )
        # 휴리스틱 3종이 message 스캔에서 빠지면 회귀
        assert len(_mod.HEURISTIC_CONTENT_PATTERNS) == 3
        descriptions = [d for _, d in _mod.SENSITIVE_CONTENT_PATTERNS]
        assert "비밀번호 리터럴" in descriptions
        assert "API 키 (sk-...)" in descriptions


class TestMessageBroadcastScanUnchanged:
    """message/broadcast 콘텐츠 스캔은 기존 휴리스틱 패턴을 그대로 유지한다."""

    def test_message_password_heuristic_still_blocked(self):
        code = run_main(
            {
                "tool_name": "message",
                "tool_input": {"content": "password=supersecret123"},
            }
        )
        assert code == 2
