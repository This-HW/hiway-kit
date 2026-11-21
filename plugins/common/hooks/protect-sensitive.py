#!/usr/bin/env python3
"""
PreToolUse Hook: 민감한 파일 보호

Edit/MultiEdit/Write/NotebookEdit/Read/Grep 도구가 민감한 파일에 접근하려 할 때 차단합니다.
env 템플릿(.env.example 등) 쓰기는 허용하되, 실제 형식의 시크릿을 기록하면 차단합니다.

Grep(5.9.0, 보안 리뷰 M-2)은 파일 판정을 먼저 하고, 그다음 Grep 이 **닿는** 곳을 본다:
- `path` 가 디렉토리가 아닌 민감 파일(realpath 포함) — Read 와 같은 판정
- 검색 디렉토리가 **이름 자체가 자격증명 보관소**일 때(`~/.ssh`·`~/.aws`·`secrets/`·`credentials/` —
  `SENSITIVE_DIR_PATTERNS`, 그 안의 파일 전부를 Read 판정이 이미 막는 이름만. `path` 문자열로 보고
  심링크면 realpath 도 본다 — path 가 없으면 `.` 이라 이름이 보이지 않는다), 또는 검색 디렉토리
  (`path`, 없으면 cwd)가 **홈의 보관소를 품을 때**(홈·그 조상 — `HOME_CREDENTIAL_STORES`, realpath 로
  본다). Claude Code 의 Grep 은 ripgrep 을 `--hidden` 으로 부른다(2.1.330 바이너리에서 확인)
- `glob` 이 보호 파일을 지목하거나 **고를 수 있을 때**. ripgrep 의 `--glob` 은 `.gitignore` 를 무시하고
  고른 파일을 읽는다 — Claude Code 2.1.330 에 든 ripgrep 14.1.1 실측: 무시된 `.env` 를 `-g '*'`·`'**'`·
  `'*env'`·`'config/*'`·`'.[Z-f]nv'`·`'[^x]env'`·`'.\\env'` 가 모두 읽었고 glob 없는 검색은 읽지 않았다.
  판정은 갈래마다 (1) 디렉토리 부분까지 남긴 대표 경로를 Read 판정에 넣고(`secrets/*.yaml`), (2) 이름
  부분이 와일드카드면 `GLOB_PROBES`(대표 보호 이름)와 맞춘다. ripgrep 과 같은 뜻으로 풀 수 없는 glob
  (이스케이프·중첩/짝 없는 괄호·거꾸로 된 범위·상한 초과)은 **막는다**.
  의도대로 막히는 흔한 형태: 디렉토리 범위 glob(`src/**`·`tests/*` — `path` 로 옮기면 된다)과 대표
  이름에 겹치는 glob(`server.*`·`cert*`·`*.h*`·`.*rc` — 확장자까지 적으면 된다: `*.{h,hpp}`).

차단되는 파일:
- .env* (환경 변수)
- **/secrets/** (시크릿 디렉토리)
- **/*credential*, **/*secret* — 데이터·설정 파일만. 소스·문서(.py·.sql·.md 등)는 통과
- ~/.ssh/** (SSH 키)
- ~/.aws/** (AWS 인증)

끄기: HIWAY_KIT_DISABLE_HOOKS 에 protect-sensitive(또는 all) — 프로젝트 .claude/settings.json 의 env.

env 템플릿 쓰기 콘텐츠 스캔 (형식-확정 패턴만):
- API 키 패턴 (sk-, pk_, AKIA 등)
- SSH 개인키 블록
- 데이터베이스 연결 문자열

사용법:
  settings.json에서 PreToolUse hook으로 등록

종료 코드:
  0: 허용
  2: 차단 (Claude에게 피드백)

실패 모드:
  훅 자체의 오류(예기치 않은 예외)는 허용(fail-open) — 훅이 세션을 막으면 안 된다.
  **입력 파싱 실패는 도구로 가른다**: 원문에서 최상위 `tool_name` 을 읽어 감시 대상 도구면 **차단**,
  감시 대상 밖이거나 도구를 알 수 없으면 허용한다. 예전에는 깊게 중첩된 `tool_input` 하나가
  `json.load` 에서 `RecursionError` 를 내고 blanket except 로 빠져 `Read(.env)` 가 허용됐다(보안 리뷰
  L-1). 런타임은 `tool_name` 을 `tool_input` 보다 앞에 싣고, 문자열 안의 `"tool_name"` 은 이스케이프돼
  있어(`\\"`) 최상위 키로 읽히지 않는다.
  단 **판정 입력의 타입 혼동은 그 길로 빠지지 않는다**: 감시 대상 도구에서 경로 필드
  (`file_path`·`notebook_path`)가 있는데 문자열이 아니거나(리스트·dict·숫자 …) `tool_input`
  자체가 객체가 아니면 **차단**한다. 예전에는 `{"file_path": [".env"]}` 가 `.lower()` 에서
  예외를 내고 blanket except 로 빠져 허용됐다(타입 하나로 판정이 조용히 열렸다).
  경로 필드가 아예 없거나 null·빈 문자열인 것은 정상 — 판정할 경로가 없으니 허용한다.

탐지할 수 없는 것 (이 훅의 범위 밖 — 없는 보호를 있다고 믿지 않도록 적는다):
  - **Bash 경유 접근.** 이 훅은 Edit/MultiEdit/Write/NotebookEdit/Read/Grep 만 본다. `cat .env`,
    `cp .env x` 처럼 셸로 읽고 쓰는 것은 가로채지 않는다(셸 명령 파싱은 오탐이 Bash 우회를 부르고,
    정확히 하려면 셸 해석기를 다시 써야 한다).
  - **하드링크 이름 세탁.** `ln .env notes.txt` 뒤 `notes.txt` 를 Read 하면 통과한다. 하드링크는
    realpath 로 드러나지 않는다(두 이름이 동등한 원본이다). 심링크는 realpath 2단 검사로 잡는다.
  - **이름이 아닌 내용.** 보호 패턴에 안 걸리는 이름의 파일에 든 시크릿은 막지 않는다 — 내용 스캔은
    env 템플릿 쓰기에만 돈다. 시크릿 스캔은 gitleaks(이 레포의 CI·verify-done §24)의 몫이다.
  - **디렉토리 대상 Grep.** `Grep(path=".")`·`Grep(path="config/")` 는 그 아래 민감 파일까지 검색할
    수 있지만 경로 매칭으로는 막을 수 없다(디렉토리 이름은 무엇을 읽을지 말해 주지 않는다 — 막으면
    정상 검색이 전부 막힌다). 이름 자체가 보관소인 디렉토리와 홈의 보관소를 품는 디렉토리만 막는다.
    ripgrep 이 `.gitignore` 를 따르므로 무시된 `.env` 는 보통 빠지지만, 추적되는 민감 파일·무시 규칙이
    없는 레포는 그대로 검색된다. 프로젝트 안의 보관소 디렉토리를 cwd 로 두고 `path="."` 로 부르면(경로
    문자열에 그 이름이 없고 심링크도 아니다) 보지 않는다.
  - **데이터 파일로 좁히는 glob.** `*.json`·`*.yaml`·`cr*`·`t*` 도 무시된 `credentials.json`·
    `token.json` 을 고를 수 있지만 막지 않는다 — 막으면 그 형식의 검색이 전부 막힌다. `GLOB_PROBES` 는
    대표 이름이라 거기 없는 보호 이름을 고르는 glob 은 놓친다. `type` 필드(언어 필터)도 보지 않는다.
  - **Glob.** 파일 **이름**만 돌려주고 내용을 읽지 않으므로 감시 대상이 아니다(민감 파일의 존재는 드러난다).
  - **Codex 등 다른 하네스.** `hooks-codex.json` 은 이 훅을 등록하지 않는다(PreToolUse 없음).
"""

import fnmatch
import json
import os
import re
import sys

# 공통 유틸리티 import (스크립트 위치 기반 동적 경로)
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import debug_log, hook_disabled, is_debug_mode
except ImportError:

    def hook_disabled(name):
        return False

    def debug_log(msg, error=None):
        pass

    def is_debug_mode():
        return False


# 시크릿이 없는 env 템플릿(placeholder 전용, git-tracked이 정상)은 보호 대상 아님.
# 정확 suffix 매치 4종만 예외(2.10.5) — 뒤붙임 변형(.env.example.backup)은 계속 차단.
# 접두사형 템플릿(app.env.example)은 의도적으로 미지원 — 보호 키워드 배제 로직이 필요해 예외가 복잡해진다.
# 템플릿은 Read 도 허용한다. 템플릿에 실수로 넣은 실제 시크릿은 gitleaks·저장소 위생의 몫이다.
# 좌측 (^|/) 앵커 필수(ATK-001): 미앵커 search는 credentials.env.example처럼 보호
# 파일명에 템플릿 접미사만 붙여 credential/secret 차단을 재개방시킨다.
ENV_TEMPLATE_RE = re.compile(
    r"(^|/)\.env(\.[a-z0-9_-]+)?\.(example|sample|template|dist)$"
)

# 보호할 패턴 (정규식)
PROTECTED_PATTERNS = [
    # 환경 변수
    r"\.env($|\.)",  # .env, .env.local, .env.production 등
    # 시크릿/인증 디렉토리
    r"/secrets/",  # secrets 디렉토리
    # SSH
    r"\.ssh/",  # SSH 키 디렉토리
    r"id_rsa",  # SSH 개인키
    r"id_ed25519",  # SSH 개인키
    r"id_ecdsa",  # SSH 개인키
    r"known_hosts",  # SSH known hosts
    # 클라우드 설정
    r"\.aws/",  # AWS 설정
    r"\.gcp/",  # GCP 설정
    r"\.azure/",  # Azure 설정
    r"\.kube/config",  # Kubernetes config
    r"\.docker/config\.json",  # Docker credentials
    # 패키지 관리자 토큰
    r"\.npmrc$",  # npm 토큰
    r"\.yarnrc$",  # yarn 설정
    r"\.pypirc$",  # PyPI 토큰
    r"\.netrc$",  # netrc 파일
    # 키 파일
    r"\.pem$",  # 인증서/키 파일
    r"\.key$",  # 키 파일
    r"\.p12$",  # PKCS#12 파일
    r"\.pfx$",  # PFX 파일
    r"_rsa$",  # RSA 키 — `re.search` 라 앞의 `.*` 는 뜻이 같고 긴 입력에서 이차 백트래킹만 낳는다(5.9.0 리뷰)
    r"_ecdsa$",  # ECDSA 키
    # 기타 민감 파일 — 자격증명 관례 결합만 차단 (외부 사용 보고 2026-07-31: 산문
    # 복합어 파일명 'token-efficiency-discipline.md'가 substring 매치로 오차단).
    # 차단: 정확명(token, token.json, .token) + 접미 결합(api_token.json, github-token.txt).
    # 통과: 산문 복합어(token-efficiency-*.md), 소스 파일(tokenizer.py, oauth/token.py).
    # 좁힌 만큼의 잔여(예: token_prod.json 같은 접두 복합)는 **이 훅이 보호하지 않는다** —
    # 콘텐츠 스캔은 env 템플릿 쓰기에만 돌고 Read 에는 없다. gitleaks 는 이 레포의 CI 에서만 돈다.
    r"(^|/)\.?tokens?(\.(json|ya?ml|txt|env|cfg|conf|ini|toml|properties))?$",
    r"[_-]tokens?(\.(json|ya?ml|txt|env|cfg|conf|ini|toml|properties))?$",
    r"(^|/)\.?passwords?(\.(json|ya?ml|txt|env|cfg|conf|ini|toml|properties))?$",
    r"[_-]passwords?(\.(json|ya?ml|txt|env|cfg|conf|ini|toml|properties))?$",
    r"\.htpasswd$",  # Apache htpasswd
]

# 이름 키워드 — 데이터·설정 파일만 막고 **소스·문서는 통과**시킨다.
# 외부 설치 보고(2026-11-09): 키워드가 경로 어디에 있든 막자 수집기 코드
# (credential_collector.py)·SP 정의(SP_UPDATE_USER_CREDENTIALS.sql)·운영 문서
# (credential-rotation.md)·secret_manager.py 가 막혔고, 오탐은 에이전트를 Bash `cat`
# 우회로 민다 — 보호가 오히려 약해진다. token/password 를 좁힌 2026-07-31 과 같은 판단이다.
# **통과시킨 소스·문서는 읽기·쓰기 모두 이 훅의 보호 밖이다** — 콘텐츠 스캔은 env 템플릿
# 쓰기에만 돌고, gitleaks 는 소비자 레포가 아니라 이 레포의 CI 에서만 돈다. 그래서 통과 범위를
# 좁게 잡는다:
# - 제외는 확장자 **나열**(SOURCE_DOC_EXTENSIONS) — 모르는 확장자는 기본 차단. 셸·Terraform·
#   노트북(출력 셀에 값이 남는다)은 시크릿이 놓이는 자리라 제외하지 않는다.
# - 이름이 키워드와 수식어로만 된 **시크릿 모듈**(secrets.py·config.secret.ts·secret_token.rb·
#   credentials_backup.sql)과 secret(s)/credential(s) **디렉토리**는 확장자와 무관하게 막는다.
#   통과하는 것은 키워드가 다른 낱말을 꾸미는 복합어(credential_collector·secret_manager·
#   SP_UPDATE_USER_CREDENTIALS)뿐이다.
STRICT_KEYWORD_PATTERNS = [
    r"(^|/)\.?(secrets?|credentials?)/",  # 이름 그대로인 디렉토리
]

#: 시크릿 모듈 판정 — 이름의 낱말이 전부 이 둘(+수식어)이고 키워드가 하나 이상이면 모듈이다.
_STORE_KEYWORDS = frozenset({"secret", "secrets", "credential", "credentials"})
_STORE_PARTS = _STORE_KEYWORDS | {
    "token", "tokens", "key", "keys", "api", "client", "master", "private", "auth",
}
_STORE_QUALIFIERS = frozenset({
    "dev", "development", "prod", "production", "local", "staging", "stage", "test", "testing",
    "settings", "config", "app", "default", "base", "my", "env",
    "backup", "bak", "dump", "old", "orig", "copy",
    "json", "yaml", "yml", "toml", "ini", "cfg", "conf", "txt",
})


def _is_secret_store_name(path_lower: str) -> bool:
    name = path_lower.rsplit("/", 1)[-1].lstrip(".")
    stem = name.rpartition(".")[0] if "." in name else name
    core = {t for t in re.split(r"[._-]+", stem) if t and t not in _STORE_QUALIFIERS}
    return bool(core) and core <= _STORE_PARTS and (
        bool(core & _STORE_KEYWORDS) or {"private", "key"} <= core
    )


NAME_KEYWORD_PATTERNS = [
    r"credential",  # credential 포함 파일·디렉토리
    r"secrets?(?=[._/\d-]|$)",  # 'secret(s)' 토큰: mysecret.txt·api_secret 포함, 'secretary' 제외
    # 개인 키 — 한 파일 이름 안에서만. 경로 전체에 걸면 macOS 의 /private/tmp·/private/var
    # 아래 이름에 'key' 가 든 모든 파일(monkey.py·keymap.json)이 막혔다.
    r"(^|/)[^/]*private[^/]*key[^/]*$",
]

SOURCE_DOC_EXTENSIONS = frozenset(
    {
        # 문서
        "md", "mdx", "rst", "adoc",
        # 데이터 질의
        "sql",
        # 소스
        "py", "pyi", "java", "kt", "kts", "scala", "groovy", "go", "rs",
        "js", "jsx", "mjs", "cjs", "ts", "tsx", "vue", "svelte",
        "rb", "php", "cs", "fs", "swift", "dart", "m", "mm",
        "c", "h", "cc", "cpp", "cxx", "hpp", "hh",
        "r", "jl", "lua", "ex", "exs", "erl", "hs", "clj",
        "html", "css", "scss",
    }
)


def _is_source_or_doc(path_lower: str) -> bool:
    name = path_lower.rsplit("/", 1)[-1]
    stem, dot, extension = name.lstrip(".").rpartition(".")
    return bool(dot and stem) and extension in SOURCE_DOC_EXTENSIONS

# 콘텐츠 내 민감 정보 패턴 — env 템플릿(.env.example 등) 쓰기 콘텐츠 스캔용.
# 형식-확정 패턴만: 실제 시크릿 형식(sk-, AKIA, PEM 블록 등)에만 매치되어
# placeholder(API_KEY=your_key_here)와 충돌할 확률이 사실상 0이다 (2.10.5).
# (휴리스틱 할당 패턴 `password=…` 류는 제거된 Agent Teams 의 message/broadcast
#  스캔 전용이었다 — 그 분기와 함께 v5.0.0 에서 삭제했다. 호출 경로가 0 이었다.)
HIGH_CONFIDENCE_CONTENT_PATTERNS = [
    # API 키 패턴
    (r"sk-[a-zA-Z0-9]{20,}", "API 키 (sk-...)"),
    (r"sk-ant-[a-zA-Z0-9_-]{20,}", "Anthropic API 키"),
    (r"sk_(?:live|test)_[a-zA-Z0-9]{16,}", "Stripe 시크릿 키"),
    (r"pk_[a-zA-Z0-9]{20,}", "API 키 (pk_...)"),
    (r"AIza[0-9A-Za-z_-]{35}", "Google API 키"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"xoxb-[0-9]{10,13}-[a-zA-Z0-9-]+", "Slack Bot Token"),
    (r"xoxp-[0-9]{10,13}-[a-zA-Z0-9-]+", "Slack User Token"),
    # SSH 개인키 블록
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "SSH 개인키"),
    (r"-----BEGIN CERTIFICATE-----", "인증서"),
    # 데이터베이스 연결 문자열
    (r"(?:postgres|mysql|mongodb)://\S+:\S+@", "DB 연결 문자열 (인증 정보 포함)"),
    (r"(?:redis|amqp)://:\S+@", "Redis/AMQP 연결 문자열"),
    # JWT 토큰
    (r"eyJ[a-zA-Z0-9_-]{20,}\.eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}", "JWT 토큰"),
]

# 차단 메시지
BLOCK_MESSAGES = {
    # Read 도 이 메시지를 받는다 — "수정할 수 없다"로 쓰면 읽기 차단을 잘못 설명한다.
    "env": "환경 변수 파일(.env)은 보호됩니다 — 읽기·쓰기 모두 차단. 값이 필요하면 사용자에게 요청하세요.",
    "secrets": "시크릿 파일/디렉토리는 보호됩니다.",
    "credential": "인증 정보 파일은 보호됩니다.",
    "ssh": "SSH 키는 보호됩니다.",
    "key": "개인 키 파일은 보호됩니다.",
    "cloud": "클라우드 설정 파일은 보호됩니다.",
    "token": "토큰/패스워드 파일은 보호됩니다.",
    "package": "패키지 관리자 인증 파일은 보호됩니다.",
}


def check_content_sensitive(
    content, patterns=HIGH_CONFIDENCE_CONTENT_PATTERNS
) -> tuple[bool, str]:
    """콘텐츠에 민감 정보가 포함되어 있는지 확인 (S-C-08).

    content가 str이 아니어도(list/dict payload) str()로 강제 직렬화해 스캔한다 —
    구조화 payload에 re.search가 TypeError를 던져 blanket except로 fail-open(스캔 우회)
    되던 문제(적대적 리뷰 P1)를 막는다.

    patterns: 형식-확정 패턴(HIGH_CONFIDENCE_CONTENT_PATTERNS) — placeholder
    false-positive를 피한다(2.10.5).
    """
    if not content:
        return False, ""
    if not isinstance(content, str):
        content = str(content)  # list/dict 등도 직렬화해 스캔(우회 차단)

    for pattern, description in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            # **매칭된 값의 원문 조각을 남기지 않는다.** 이 훅의 출력은 터미널에만
            # 머물지 않는다 — 에이전트 트랜스크립트·CI 로그로 옮겨 다닌다
            # (`docs/conventions/warning-signal.md` §6). 앞 4자+뒤 2자를 찍던
            # 방식은 같은 레포의 `.private-names` 가드(첫 글자+길이)보다 느슨해,
            # 한 저장소 안에 마스킹 기준이 둘이었다. 더 보수적인 쪽으로 통일한다.
            #
            # 판정에 필요한 정보는 *"무엇이 걸렸나(description)"* 와 *"얼마나 긴가"*
            # 이지 *"값이 무엇인가"* 가 아니다 — 값은 사용자가 이미 갖고 있다.
            matched_text = match.group(0)
            masked = f"{matched_text[:1]}…({len(matched_text)}자)"
            debug_log(f"Sensitive content detected: {description} ({masked})")
            msg = f"쓰려는 내용에 민감 정보가 포함되어 있습니다: {description}. 민감 정보를 제거한 후 다시 시도하세요."
            return True, msg

    return False, ""


def check_protected(file_path: str) -> tuple[bool, str]:
    """파일이 보호 대상인지 확인"""
    path_lower = file_path.lower()

    # env 템플릿(.env.example 등)은 시크릿이 없는 placeholder 전용 파일이 정상이므로
    # 보호 대상에서 제외한다(2.10.5). main()의 원본→realpath 2단 검사
    # 구조 덕분에 symlink로 실제 .env를 가리키는 우회는 여전히 차단된다(ATK-007).
    if ENV_TEMPLATE_RE.search(path_lower):
        return False, ""

    patterns = list(PROTECTED_PATTERNS) + STRICT_KEYWORD_PATTERNS
    if not _is_source_or_doc(path_lower) or _is_secret_store_name(path_lower):
        patterns += NAME_KEYWORD_PATTERNS
    for pattern in patterns:
        if re.search(pattern, path_lower):
            debug_log(f"Pattern matched: {pattern} for {file_path}")

            # 어떤 유형인지 파악
            if ".env" in path_lower:
                return True, BLOCK_MESSAGES["env"]
            elif "secret" in path_lower:
                return True, BLOCK_MESSAGES["secrets"]
            elif "credential" in path_lower:
                return True, BLOCK_MESSAGES["credential"]
            elif (
                ".ssh" in path_lower
                or "id_rsa" in path_lower
                or "id_ed25519" in path_lower
            ):
                return True, BLOCK_MESSAGES["ssh"]
            elif any(
                k in path_lower for k in [".kube", ".docker", ".aws", ".gcp", ".azure"]
            ):
                return True, BLOCK_MESSAGES["cloud"]
            elif any(
                k in path_lower for k in [".npmrc", ".yarnrc", ".pypirc", ".netrc"]
            ):
                return True, BLOCK_MESSAGES["package"]
            elif any(k in path_lower for k in ["token", "password"]):
                return True, BLOCK_MESSAGES["token"]
            elif any(
                k in path_lower
                for k in [".pem", ".key", ".p12", ".pfx", "private", "_rsa", "_ecdsa"]
            ):
                return True, BLOCK_MESSAGES["key"]
            else:
                return True, "이 파일은 보안상 보호됩니다."

    return False, ""


#: 경로로 판정하는 도구. NotebookEdit 는 `notebook_path` 를, Grep 은 `path`·`glob` 을, 나머지는
#: `file_path` 를 쓴다. `hooks.json` 의 PreToolUse matcher 와 같은 집합이어야 한다(테스트가 대조한다).
WATCHED_TOOLS = ("Edit", "MultiEdit", "Write", "Read", "NotebookEdit", "Grep")
PATH_FIELDS = ("file_path", "notebook_path")
GREP_FIELDS = ("path", "glob")

#: 와일드카드 Grep `glob` 이 **고를 수 있는지** 맞춰 볼 대표 보호 이름(5.9.0 리뷰). 이름 부분이 하나라도
#: 고르면 막는다(대문자 이름도 맞춘다 — ripgrep glob 은 대소문자를 가린다). 확장자가 흔한 데이터
#: 이름(credentials.json·secrets.yaml·token.txt)은 넣지 않는다 — `*.json` 같은 정상 검색이 전부
#: 막힌다(독스트링 "탐지할 수 없는 것").
GLOB_PROBES = (
    ".env", ".env.local", ".env.production",
    ".npmrc", ".yarnrc", ".pypirc", ".netrc", ".htpasswd",
    "id_rsa", "id_ed25519", "id_ecdsa",
    "server.pem", "server.key", "cert.p12", "cert.pfx",
)

#: 이름 자체가 자격증명 보관소인 디렉토리 — 디렉토리 대상 Grep 은 이 이름일 때 막는다(5.9.0 리뷰).
#: 그 안의 파일 전부를 Read 판정(`PROTECTED_PATTERNS`·`STRICT_KEYWORD_PATTERNS`)이 이미 막는 이름만
#: 둔다. 이름 키워드(credential_collector/·secret_manager/ 같은 소스 디렉토리)는 넣지 않는다.
SENSITIVE_DIR_PATTERNS = (
    (r"\.ssh/", "ssh"),
    (r"\.aws/", "cloud"),
    (r"\.gcp/", "cloud"),
    (r"\.azure/", "cloud"),
    (r"(^|/)\.?secrets?/", "secrets"),
    (r"(^|/)\.?credentials?/", "credential"),
)

#: 홈의 자격증명 보관소 — 디렉토리 대상 Grep 이 이것을 **품으면**(그 디렉토리이거나 조상이면) 막는다.
#: Claude Code 의 Grep 은 ripgrep 을 `--hidden` 으로 부르고(2.1.330 바이너리에서 확인) 홈에는 보통
#: 무시 규칙이 없어, `Grep(path="~")` 는 `~/.ssh/id_rsa` 까지 검색한다(5.9.0 리뷰).
HOME_CREDENTIAL_STORES = (".ssh", ".aws", ".gcp", ".azure", ".kube", ".docker", ".config/gcloud")

#: glob 판정 비용 상한 — 넘으면 판정 불가로 막는다. ripgrep 에는 이 상한이 없어서, 잘라서 보면 뒤쪽
#: 갈래가 판정 없이 열린다(5.9.0 리뷰: 대안 65개의 마지막 `.env` 를 ripgrep 은 읽었다).
_MAX_GLOB_LENGTH = 4096
_MAX_GLOB_ALTERNATIVES = 256
#: 판정할 갈래 문자 총량 — 길이·갈래 상한을 둘 다 지나도 곱이 커지면(긴 갈래 256개) 판정 시간이 훅
#: timeout(10초)에 다가간다. timeout 은 차단이 아니므로 시간으로 판정을 여는 길이 된다(5.9.0 리뷰).
_MAX_GLOB_TOTAL_CHARS = 65536


class GlobUnjudgeable(ValueError):
    """Grep `glob` 을 ripgrep 과 같은 뜻으로 풀 수 없다 — 판정 불가는 막는다."""


#: 파싱하지 못한 입력에서 최상위 도구 이름을 읽는다. 문자열 안의 `"tool_name"` 은 `\\"` 로
#: 이스케이프돼 있으므로 이 패턴(따옴표로 시작·끝나는 키)에 걸리지 않는다.
_TOOL_NAME_SNIFF_RE = re.compile(r'(?<!\\)"tool_name"\s*:\s*"([A-Za-z_][\w-]*)"')


def _sniff_tool_names(raw: str) -> list[str]:
    """원문에 보이는 `"tool_name": "<이름>"` 전부 — 하나라도 감시 대상이면 감시 대상으로 본다(보수)."""
    return _TOOL_NAME_SNIFF_RE.findall(raw)


def _glob_alternatives(glob: str) -> list[str]:
    """Grep `glob` 을 ripgrep(globset)과 같은 뜻의 **갈래**로 푼다. 제외 glob(`!…`)은 뺀다.

    - 중괄호·문자 클래스 밖의 콤마·공백은 glob 구분으로 본다 — ripgrep 에서 `a,b` 는 하나의 glob
      이지만 하네스가 여러 glob 을 한 값에 실어 넘길 수 있고, 나누면 갈래가 늘 뿐이라(막는 쪽으로만
      움직인다) 보수적으로 나눈다. 클래스 안의 콤마(`[,.]`)는 글자다.
    - `{a,b}` 는 펼친다(곱). ripgrep 은 중첩 중괄호를 오류로 거부한다 — 여기서도 판정 불가.
    - **판정 불가(`GlobUnjudgeable`)**: 이스케이프 `\\`(globset 은 `\\e` 를 `e` 로 본다), 중첩·짝 없는
      중괄호, 닫히지 않은 클래스, 거꾸로 된 범위(`[z-a]`), 길이·갈래 상한 초과.
    """
    if len(glob) > _MAX_GLOB_LENGTH:
        raise GlobUnjudgeable("너무 길다")
    if "\\" in glob:
        raise GlobUnjudgeable("이스케이프 문자")
    out: list[str] = []
    current = [""]  # 지금 glob 의 갈래들
    group = None  # 열린 중괄호 안의 조각들
    piece: list[str] = []
    in_class = False
    class_body: list[str] = []

    def emit(ch: str) -> None:
        nonlocal current
        if group is not None:
            piece.append(ch)
        else:
            current = [c + ch for c in current]

    def finish() -> None:
        nonlocal current
        for alt in current:
            if alt and not alt.startswith("!"):  # 제외 glob 은 무엇도 고르지 않는다
                out.append(alt)
        if len(out) > _MAX_GLOB_ALTERNATIVES:
            raise GlobUnjudgeable("갈래가 너무 많다")
        current = [""]

    for ch in glob:
        if in_class:
            emit(ch)
            if ch == "]" and class_body and class_body != ["!"] and class_body != ["^"]:
                body = "".join(class_body).lstrip("!^")
                for k in range(len(body) - 2):
                    if body[k + 1] == "-" and body[k] > body[k + 2]:
                        raise GlobUnjudgeable("거꾸로 된 범위")
                in_class = False
                continue
            class_body.append(ch)
            continue
        if ch == "[":
            emit(ch)
            in_class = True
            class_body = []
        elif ch == "{":
            if group is not None:
                raise GlobUnjudgeable("중첩 중괄호")
            group = []
            piece = []
        elif ch == "}":
            if group is None:
                raise GlobUnjudgeable("짝 없는 중괄호")
            group.append("".join(piece))
            current = [c + g for c in current for g in group]
            if len(current) > _MAX_GLOB_ALTERNATIVES:
                raise GlobUnjudgeable("갈래가 너무 많다")
            group = None
        elif ch == "," and group is not None:
            group.append("".join(piece))
            piece = []
        elif group is None and (ch == "," or ch.isspace()):
            finish()
        else:
            emit(ch)
    if in_class or group is not None:
        raise GlobUnjudgeable("닫히지 않은 괄호")
    finish()
    return out


def _glob_representatives(alt: str) -> list[str]:
    """갈래 하나를 판정용 **경로** 로 바꾼다 — 와일드카드를 지운 것과 `x` 로 채운 것 둘.

    `*.pem`→`.pem`·`x.pem`, `.env*`→`.env`, `secrets/*.yaml`→`secrets/x.yaml`, `[.]env`→`.env`.
    디렉토리 부분까지 남긴다 — 이름만 보면 `secrets/*.yaml` 이 `x.yaml` 이 되어 보관소 판정을 빠져나간다
    (5.9.0 리뷰, ripgrep 실측: 파일 단위로 무시된 `secrets/prod.yaml` 을 읽었다).
    """
    def classes(text: str, negated_as: str) -> str:
        return re.sub(
            r"\[([!^]?)(\]?[^\]]*)\]",
            lambda m: negated_as if m.group(1) else (m.group(2)[:1] or "x"),
            text,
        )
    stripped = classes(alt, "").replace("*", "").replace("?", "")
    filled = classes(alt, "x").replace("*", "x").replace("?", "x")
    return [r for r in dict.fromkeys((stripped, filled)) if r.strip("/")]


def _probe_hit(alt: str) -> str:
    """갈래의 이름 부분이 와일드카드면 `GLOB_PROBES` 중 고르는 이름(없으면 "")."""
    name = alt.rstrip("/").rsplit("/", 1)[-1]
    if not any(ch in name for ch in "*?["):
        return ""  # 와일드카드 없는 이름은 _glob_representatives 판정으로 충분하다
    pattern = name.replace("[^", "[!")  # globset 은 `[^…]` 도 부정이다 — fnmatch 표기로
    for probe in GLOB_PROBES:
        for candidate in (probe, probe.upper()):
            try:
                if fnmatch.fnmatchcase(candidate, pattern):
                    return probe
            except re.error as err:  # 범위 검사를 지나온 해석 차이 — 판정 불가
                raise GlobUnjudgeable(f"해석 불가({err})") from err
    return ""


def glob_block_reason(glob: str) -> tuple[str, str]:
    """Grep `glob` 이 보호 파일을 지목하거나 고를 수 있으면 (갈래, 이유), 아니면 ("", "").

    판정 불가(`GlobUnjudgeable`)도 막는 이유로 돌려준다 — 갈래는 원문 전체.
    """
    try:
        alternatives = _glob_alternatives(glob.strip())
        if sum(len(a) for a in alternatives) > _MAX_GLOB_TOTAL_CHARS:
            raise GlobUnjudgeable("판정할 갈래가 너무 길다")
        for alt in alternatives:
            for rep in _glob_representatives(alt):
                protected, message = check_protected(rep)
                if protected:
                    return alt, message
            probe = _probe_hit(alt)
            if probe:
                return alt, f"{probe} 같은 보호 파일을 고른다."
    except GlobUnjudgeable as err:
        return glob, f"이 glob 은 판정할 수 없다({err})."
    return "", ""


def sensitive_dir_message(path: str, cwd: str) -> str:
    """디렉토리 대상 Grep 이 자격증명 보관소에 닿으면 차단 메시지, 아니면 "". 파일·없는 경로는 "".

    - 이름 자체가 보관소인 디렉토리(`SENSITIVE_DIR_PATTERNS`): 경로 문자열을 보고, 심링크로 들어간
      경우에만 realpath 도 본다 — 파일 판정의 원본→realpath 2단과 같은 규칙이다.
    - 홈의 보관소(`HOME_CREDENTIAL_STORES`)를 품는 디렉토리(그 디렉토리이거나 조상) — realpath 로 본다.
    """
    try:
        base = cwd if isinstance(cwd, str) and cwd else os.getcwd()
        expanded = os.path.expanduser(path)
        full = os.path.join(base, expanded)
        if not os.path.isdir(full):
            return ""
        real = os.path.realpath(full)
        candidates = [expanded]
        if real != os.path.abspath(full):
            candidates.append(real)
    except (ValueError, OSError):
        return ""
    for candidate in candidates:
        d = candidate.lower().rstrip("/") + "/"
        for pattern, kind in SENSITIVE_DIR_PATTERNS:
            if re.search(pattern, d):
                return BLOCK_MESSAGES[kind]
    try:
        home = os.path.expanduser("~")
        root = real.rstrip(os.sep) + os.sep
        for store in HOME_CREDENTIAL_STORES:
            store_path = os.path.join(home, store)
            if os.path.exists(store_path) and (os.path.realpath(store_path) + os.sep).startswith(root):
                kind = "ssh" if store == ".ssh" else "cloud"
                return f"{BLOCK_MESSAGES[kind]} (이 디렉토리 아래에 ~/{store} 가 있다)"
    except (ValueError, OSError):
        return ""
    return ""


def extract_grep_targets(tool_input, cwd: str) -> tuple[list[str], str]:
    """Grep 이 **파일 하나로 지목하는** 판정 대상과 타입 오류(없으면 "").

    - `path` 가 디렉토리면 대상이 아니다(독스트링 "탐지할 수 없는 것" — 보관소 디렉토리는
      `_check_grep_reach` 가 따로 막는다). 디렉토리가 아닌 값(파일·아직 없는 경로)은 그대로 판정한다.
      상대경로는 입력의 `cwd` 기준으로 디렉토리 여부만 본다.
    - `glob` 은 여기서 판정하지 않는다 — `_check_grep_reach`(`glob_block_reason`)의 몫이다.
    - 두 필드가 문자열이 아니면 타입 오류 — `extract_paths` 와 같은 fail-closed.
    """
    if tool_input is None:
        return [], ""
    if not isinstance(tool_input, dict):
        return [], f"tool_input 이 객체가 아니다({type(tool_input).__name__})"
    for field in GREP_FIELDS:
        value = tool_input.get(field)
        if value is not None and not isinstance(value, str):
            return [], f"경로 필드 '{field}' 가 문자열이 아니다({type(value).__name__})"
    targets: list[str] = []
    path = tool_input.get("path") or ""
    if path:
        try:
            base = cwd if isinstance(cwd, str) and cwd else os.getcwd()
            is_dir = os.path.isdir(os.path.join(base, os.path.expanduser(path)))
        except (ValueError, OSError):
            is_dir = False
        if not is_dir:
            targets.append(path)
    return targets, ""


def extract_paths(tool_input) -> tuple[list[str], str]:
    """판정할 경로 목록과 **타입 오류**(없으면 "").

    - `tool_input` 이 없거나 null → 경로 없음(정상)
    - `tool_input` 이 객체가 아님 → 타입 오류
    - 경로 필드가 없거나 null·"" → 그 필드는 건너뜀(정상)
    - 경로 필드가 문자열이 아님 → 타입 오류. `[]`·`0` 처럼 거짓인 값도 오류다 — "없음"은 키가
      없거나 null 일 때뿐이다. 거짓 값을 없음으로 읽으면 판정 입력이 다시 타입에 따라 열린다.

    두 필드를 **모두** 본다. 예전에는 `file_path or notebook_path` 로 하나만 골라, 앞 필드가
    무해하면 뒤 필드는 판정하지 않았다.
    """
    if tool_input is None:
        return [], ""
    if not isinstance(tool_input, dict):
        return [], f"tool_input 이 객체가 아니다({type(tool_input).__name__})"
    paths: list[str] = []
    for field in PATH_FIELDS:
        value = tool_input.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            return [], f"경로 필드 '{field}' 가 문자열이 아니다({type(value).__name__})"
        if value:
            paths.append(value)
    return paths, ""


def _parse_failed(raw: str, err: BaseException) -> None:
    """입력을 파싱하지 못했다 — 감시 대상 도구면 차단, 아니면(알 수 없음 포함) 허용."""
    watched = [t for t in _sniff_tool_names(raw) if t in WATCHED_TOOLS]
    debug_log(f"stdin parse failure ({type(err).__name__}) watched={watched!r}")
    if watched:
        tool = watched[0]
        print(
            f"🔒 차단됨: {tool} 입력을 해석하지 못했다({type(err).__name__}) — "
            "민감 경로 판정을 할 수 없어 막는다.",
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(0)


def main():
    try:
        # stdin이 TTY면(파이프 입력 없음) json.load가 무한 블록한다 — 즉시 통과.
        if sys.stdin.isatty() or hook_disabled("protect-sensitive"):
            sys.exit(0)
        raw = sys.stdin.read()
        try:
            input_data = json.loads(raw)
        except (ValueError, RecursionError) as err:
            # JSONDecodeError 는 ValueError 다. RecursionError 는 깊은 중첩(보안 리뷰 L-1) — 예전에는
            # 아래 blanket except 로 빠져 허용됐다. 판정은 도구로 가른다(독스트링 "실패 모드").
            _parse_failed(raw, err)

        if not isinstance(input_data, dict):
            sys.exit(0)  # 도구를 알 수 없다 — 감시 대상인지조차 판정할 수 없으니 훅 오류와 같이 허용
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input")

        # 파일 경로 기반 도구만 검사. MultiEdit/NotebookEdit도 편집 도구이므로 포함해야
        # 시크릿 파일 우회를 막는다(MultiEdit로 .env 편집 우회 방지, 적대적 리뷰 P1).
        if tool_name not in WATCHED_TOOLS:
            sys.exit(0)

        if tool_name == "Grep":
            file_paths, type_error = extract_grep_targets(tool_input, input_data.get("cwd", ""))
        else:
            file_paths, type_error = extract_paths(tool_input)
        if type_error:
            # **판정 입력의 타입 혼동은 fail-closed.** 아래 blanket except(fail-open)로 빠지기
            # 전에 여기서 막는다 — 값은 찍지 않는다(경로 자체가 민감할 수 있다).
            print(f"🔒 차단됨: {type_error}", file=sys.stderr)
            print("   민감 경로 판정을 할 수 없는 입력이라 막는다 — 경로는 문자열 하나로 넘겨라.",
                  file=sys.stderr)
            sys.exit(2)
        for file_path in file_paths:
            _check_path(tool_name, tool_input, file_path)
        if tool_name == "Grep":
            # 파일 판정 **다음에** 돈다 — 새 판정의 결함이 기존 판정을 건너뛰게 하지 못한다(5.9.0 리뷰).
            _check_grep_reach(tool_input, input_data.get("cwd", ""))
        sys.exit(0)  # 0 = 허용

    except Exception as e:
        # fail-open: 예기치 않은 오류 시 허용 (가용성 우선 설계). 타입 혼동·감시 도구의 파싱 실패는
        # 위에서 이미 막았다 — 여기로 오는 것은 판정 로직 자체의 결함뿐이다.
        debug_log(f"Hook error: {e}", e)
        sys.exit(0)


def _check_grep_reach(tool_input, cwd: str) -> None:
    """파일 하나를 지목하지 않아도 Grep 이 **닿는** 보호 대상 — 보관소 디렉토리(경로가 없으면 cwd),
    보호 파일을 지목하거나 고를 수 있는 glob, 판정할 수 없는 glob. 막아야 하면 exit 2."""
    if not isinstance(tool_input, dict):
        return
    path = tool_input.get("path") or ""
    message = sensitive_dir_message(path or ".", cwd)
    if message:
        print(f"🔒 차단됨: Grep {path or '(cwd)'}", file=sys.stderr)
        print(f"   {message}", file=sys.stderr)
        print("   자격증명 보관소에 닿는 디렉토리 검색은 막는다 — 검색할 하위 디렉토리를 path 로 좁혀라.",
              file=sys.stderr)
        sys.exit(2)
    glob = tool_input.get("glob") or ""
    alt, reason = glob_block_reason(glob)
    if reason:
        shown = alt if len(alt) <= 120 else alt[:117] + "…"
        print(f"🔒 차단됨: Grep glob '{shown}' — {reason}", file=sys.stderr)
        hint = ("glob 을 빼거나(디렉토리 검색은 .gitignore 를 따른다) 파일 형식까지 적어라"
                "(예: *.py, **/__tests__/**/*.ts)")
        m = re.match(r"^([^*?\[\]{}!]+)/\*{1,2}/?$", alt)
        if m:
            hint = f"디렉토리로 좁히려면 glob 대신 path='{m.group(1)}' 를 써라(디렉토리 검색은 .gitignore 를 따른다)"
        print(f"   ripgrep 의 glob 은 .gitignore 를 무시하고 고른 파일을 읽는다 — {hint}.", file=sys.stderr)
        sys.exit(2)


def _check_path(tool_name: str, tool_input: dict, file_path: str) -> None:
    """경로 하나를 판정한다 — 막아야 하면 exit 2, 아니면 돌아온다."""
    # 원본 경로부터 검사 — syscall 없는 순수 문자열 검사를 먼저 실행해, 뒤의
    # realpath(syscall)가 ValueError(널바이트 등)로 예외를 던져도 이 게이트가
    # 건너뛰어지지 않게 한다(적대적 리뷰 P2: 순서 fail-open 방지).
    is_protected, message = check_protected(file_path)
    if is_protected:
        print(f"🔒 차단됨: {file_path}", file=sys.stderr)
        print(f"   {message}", file=sys.stderr)
        sys.exit(2)  # 2 = 차단

    # 실제 경로(resolved) 항상 검사 — 중간 경로 symlink 우회 방지 (ATK-007)
    try:
        real_path = os.path.realpath(file_path)
    except (ValueError, OSError):
        real_path = file_path  # realpath 실패 시에도 위 원본 검사는 이미 통과함
    if real_path != os.path.abspath(file_path):
        is_protected_real, message_real = check_protected(real_path)
        if is_protected_real:
            print(
                f"🔒 차단됨 (심볼릭 링크 대상): {file_path} → {real_path}",
                file=sys.stderr,
            )
            print(f"   {message_real}", file=sys.stderr)
            sys.exit(2)

    # env 템플릿(.env.example 등) 쓰기 콘텐츠 스캔 (2.10.5).
    # 예외로 통과한 경로라도 실제 형식의 시크릿을 기록하는 쓰기는 차단한다.
    # placeholder(API_KEY=your_key_here)와 충돌하지 않도록 HIGH_CONFIDENCE 패턴만 사용.
    # 원본 경로뿐 아니라 realpath도 확인 — symlink(foo.txt → .env.example)를
    # 경유한 쓰기가 스캔을 우회하지 못하게 한다.
    if tool_name in ("Edit", "MultiEdit", "Write", "NotebookEdit") and (
        ENV_TEMPLATE_RE.search(file_path.lower())
        or ENV_TEMPLATE_RE.search(real_path.lower())
    ):
        write_contents = []
        if tool_name == "Write":
            write_contents.append(tool_input.get("content", ""))
        elif tool_name == "Edit":
            write_contents.append(tool_input.get("new_string", ""))
        elif tool_name == "MultiEdit":
            edits = tool_input.get("edits", []) or []
            if isinstance(edits, list):
                for edit in edits:
                    # 비-dict 항목도 스캔 대상에 포함 — 건너뛰면 payload 조작 우회
                    write_contents.append(
                        edit.get("new_string", "")
                        if isinstance(edit, dict)
                        else edit
                    )
            else:
                # 스키마 밖 형태(dict/str 등)는 통짜 직렬화로 스캔 — dict 키 순회나
                # 문자 단위 순회로 페이로드가 쪼개져 스캔이 무력화되는 것을 방지
                write_contents.append(edits)
        elif tool_name == "NotebookEdit":
            write_contents.append(tool_input.get("new_source", ""))

        # str() 강제: 비-str payload(list 형태 NotebookEdit source, dict content 등)가
        # join에서 TypeError → blanket except → fail-open으로 스캔을 우회하지 못하게
        # 한다(ATK-002 — check_content_sensitive의 P1 직렬화 방어와 동일 정책).
        combined_content = "\n".join(str(c) for c in write_contents if c)
        is_sensitive, content_msg = check_content_sensitive(
            combined_content, patterns=HIGH_CONFIDENCE_CONTENT_PATTERNS
        )
        if is_sensitive:
            print(
                f"🔒 차단됨 (env 템플릿에 실제 시크릿 기록 시도): {file_path}",
                file=sys.stderr,
            )
            print(f"   {content_msg}", file=sys.stderr)
            sys.exit(2)


if __name__ == "__main__":
    main()
