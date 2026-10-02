---
title: "hiway-kit 제품 사이트 — hiway.thishw.com"
status: planning
created: 2026-10-02
size: large
---

# hiway-kit 제품 사이트 설계

**Goal:** plugin.json·디렉토리 목록이 GitHub 레포 주소 대신 가리킬 **전문적이고 고급스러운 제품 사이트**를 `hiway.thishw.com` 에 연다.
**Architecture:** 사이트는 `thishw/hiway`(thishw 개인 계정, public) 레포의 Hugo 프로젝트 사이트 + 커스텀 도메인으로, 운영은 syndicator
세션이 맡는다. 사실(개수·버전·CHANGELOG·PRIVACY)은 빌드가 `This-HW/hiway-kit` 의 **태그된 릴리스**에서 읽어 생성하고, 산문·테마·초기
콘텐츠는 이쪽이 PR 로 낸다.

**결정 경위**: 사용자 승인 2026-10-01(권장안 — Hugo 유지·새 테마, 영어 기본 + 한국어, 블로그는 현행 개념만 최신화 이관) ·
도메인 `hiway.thishw.com`(1번, 컨트롤 판단 — "github 이 보이면 없어 보인다"는 문제 제기에 github.io 가 남는 안은 맞지 않음) ·
사용자 지시 2026-10-02 *"도메인·웹페이지는 syndicator catshark 세션과 협의, 운영·유지보수는 그 세션"* → 합의(아래 "합의" 절).

## 요구사항

- **R1** 영어 기본(`/`) + 한국어(`/ko/`). hreflang·canonical·sitemap 은 Hugo 기본.
- **R2** 페이지: Home(랜딩) · Docs(Getting started, Concepts) · Blog(이관 4편) · Privacy · (CHANGELOG 는 생성 페이지 또는 GitHub 링크).
- **R3** 랜딩 구성: 한 줄 가치 제안 → 문제(계획 없이 짜고 스스로 "다 됐다") → 작동 방식(기획 관문 → 구현 루프 → 검증 관문) →
  핵심 기능 6(기획 관문 · 적대적 리뷰 · 명령으로 판정하는 완료 · 실패 학습 · 경계 도구 강제 · 멀티 하네스) → 지원 하네스 → 설치 → CTA.
  **주장은 실물이 있는 것만**(README "핵심 개념" 표·CHANGELOG 와 대조). 디렉토리 설치 명령은 소비자 환경 확인 전까지 넣지 않는다(CLAUDE.md).
- **R4** 디자인: 타이포그래피 중심의 절제된 고급감, 다크·라이트, 넉넉한 여백, 모바일~데스크톱. 테마는 **사이트 레포 안에 직접**(Hugo 모듈·외부 테마 없음).
- **R5** 추적기 0 · 외부 폰트/스크립트 CDN 0(폰트 자체 호스팅) · AdSense 스니펫·`ads.txt` 0. robots.txt 는 GPTBot·ClaudeBot·PerplexityBot·Google-Extended 허용, `llms.txt` 제공.
- **R6** 손으로 쓴 숫자 0 — 에이전트·스킬·규칙 개수, 버전은 `data/` 생성물에서만 렌더.
- **R7** 사실 갱신: 사이트 빌드가 `This-HW/hiway-kit` 최신 **릴리스 태그**에서 개수·버전·CHANGELOG·`PRIVACY.md` 를 읽어 `data/`(와 privacy 본문)로 생성.
  트리거 ① 주 1회 schedule ② 수동 dispatch(③ `repository_dispatch` 는 이후 — 토큰 필요). **산문(기능 설명)은 자동 갱신 대상이 아니다** —
  개념이 바뀌는 릴리스는 이쪽이 `thishw/hiway` 에 PR.
- **R8** 블로그 이관: 4편(병렬 git 격리 · 게이트 적대적 감사 · durable 완료 게이트 · 마지막 태스크 마감) — **현행 킷과 사실 대조**(경로·이름·규칙명·개수)
  후 최신화, 영어판 작성. `harness-loop-engineering-landscape`(시점 묶인 리서치)는 이관하지 않는다.
- **R9** 옛 주소: 새 사이트 서빙 확인 **뒤에** hiway-kit `site/` 를 리다이렉트 스텁(경로별 meta refresh + canonical, 이관 글은 새 경로 매핑)으로 교체하고
  Hugo 원본을 걷어낸다. 두 사이트가 동시에 비는 시간 0.
- **R10** hiway-kit 매니페스트: `homepage`·Codex `websiteURL`·`privacyPolicyURL` 을 **도메인이 실제로 서빙된 뒤** 교체(패치 릴리스). `repository`·`supportURL` 은 GitHub 유지.
  README 의 사이트 링크도 교체. OpenAI 심사 중인 5.2.0 은 건드리지 않는다(다음 업로드에 반영). Claude 목록 정보는 제출 시점 고정이라 이번 변경과 무관.

## 합의 (syndicator_plan_control, 2026-10-02)

| 항목 | 합의 |
| --- | --- |
| 호스팅 | `thishw/hiway`(public) 프로젝트 사이트 + 커스텀 도메인. 전용 org 없음. 근거: thishw.com verified domain 이 **thishw 개인 계정**에 있어 그 계정 레포만 서브도메인 claim 가능. 선례 `hub`·`hw_insight`·`scanday` |
| 레포 생성·Pages | syndicator 가 생성(README·LICENSE)·Pages(Actions) 활성 |
| DNS | 도메인 검증 추가 작업 없음. CNAME `hiway` → `thishw.github.io`, **DNS-only**. CF 토큰 부재로 **사용자가 CF 대시보드에서 1줄** — 값은 syndicator 가 준비 후 전달. 순서: 레포 → Pages → 커스텀 도메인 → CNAME → HTTPS 강제. 도메인은 **첫 PR 병합 뒤** |
| GSC | 기존 `sc-domain:thishw.com` 이 서브도메인 포함 — 추가 없음 |
| 테마 | 독립(media-hugo-shared 아님), 레포 안에 직접 |
| 분담 | 구현(테마·초기 콘텐츠·이관)= hiway-kit 이 PR(브랜치 `synd/post/*` 금지). 검수·병합·운영·도메인 = syndicator |
| 검수 기준 | 빌드 성공 · 깨진 링크 0 · 손숫자 0 · 추적기/폰트 CDN 0 → **PR CI 로 기계 판정**(이쪽이 워크플로 포함) + 이관 글 사실 대조표를 PR 본문에 |
| 레포 | **https://github.com/thishw/hiway**(public, main `03a8035` = README·LICENSE MIT). Pages `build_type=workflow`. 쓰기 권한 없음 → **포크 `This-HW/hiway` → PR**(포크 PR CI 는 `pull_request` 로 시크릿 없이). 자동 검수 잡 없음, 수동 검수 |
| 도메인 순서 (수정) | baseURL 고정 시 github.io 미리보기가 깨지는 충돌(이쪽 제기) → **도메인을 첫 병합 전에 붙인다**: 사용자 CF CNAME 등록 → Pages 커스텀 도메인 → 인증서 → HTTPS 강제 → 첫 PR 병합. 그 사이 도메인은 GitHub 404(노출 없음, verified 라 탈취 위험 없음). CNAME 이 늦으면 원안(github.io 단계는 워크플로 성공 + 산출물 존재만 확인) |
| 시각 검수 | PR CI artifact + PR 본문 스크린샷(데스크톱·모바일 × en/ko × 다크/라이트) + syndicator 로컬 `hugo --baseURL http://localhost:1313/` 검수 빌드(레포엔 override 없음) |
| 정책 | CF proxy 끔 · AdSense/ads.txt 금지(thishw.com 09-04 반려, 도메인 단위 판정) · `baseURL = "https://hiway.thishw.com/"` 고정, pages 워크플로에 `--baseURL` override 넣지 않음(hw_insight CSS 404 전례) |

## 접근 방식

Hugo(extended, 버전 핀 + 바이너리 sha256 검증 — 현 `pages.yml` 관례) + 레포 내 커스텀 테마. 대안 Astro/Next(Node 의존·공급망 증가)와 손 HTML(다국어·블로그
중복)은 기각 — 사용자 승인.

## 컴포넌트 구조 (`thishw/hiway`)

```
hugo.toml                       baseURL 고정, languages en(기본)/ko
layouts/                        baseof · index(랜딩) · docs · blog list/single · privacy · partials(header/footer/head/hero/feature/pipeline)
assets/css/                     토큰(색·타이포·간격) → 다크/라이트 · Hugo Pipes 로 minify·fingerprint
static/fonts/                   자체 호스팅 woff2 (라이선스 OFL 등 재배포 허용만)
content/{_index,docs,blog,privacy}.{en,ko}.md
data/kit.json                   생성물 — 개수·버전·릴리스 태그·날짜 (커밋하지 않거나, 커밋하면 생성기만 쓴다)
scripts/fetch-kit-facts.py      태그된 릴리스에서 개수·버전·CHANGELOG·PRIVACY 를 읽어 data/·privacy 본문 생성
.github/workflows/pages.yml     schedule 주1·dispatch·push → fetch → hugo build → deploy
.github/workflows/check.yml     PR: 빌드 · 링크 검사 · 손숫자 검사 · 외부 origin 검사
static/robots.txt · llms.txt
```

## 데이터 흐름

`This-HW/hiway-kit` 최신 릴리스 태그(GitHub API, 무인증 — public) → `fetch-kit-facts.py`(tarball 또는 raw 파일: `plugins/common/agents/**/*.md`·`skills/*/SKILL.md`·
`rules/*.md` 개수, `.claude-plugin/plugin.json` version, `CHANGELOG.md`, `PRIVACY.md`) → `data/kit.json` + `content/privacy` 본문 → Hugo 렌더.

## 에러 처리

- 태그 조회·다운로드 실패: **빌드 실패**(옛 숫자로 조용히 배포하지 않는다 — warning-signal §측정 8). 단 schedule 빌드 실패는 배포 중단일 뿐 기존 사이트는 유지된다.
- 개수 산출 규칙은 hiway-kit `scripts/check_doc_counts.py` 와 **같은 정의**를 쓴다(정의가 둘이면 갈린다) — 구현 시 그 스크립트의 계수 규칙을 확인해 맞춘다.
- 생성물 스키마 검증(필수 키·정수) 실패 시 빌드 실패.

## 테스트 전략 (PR CI = 검수 기준의 기계 판정)

- `hugo --gc --minify` rc 0 (경고를 오류로: `--panicOnWarning`)
- 깨진 링크 0: 빌드 산출물에 대한 내부 링크 검사(htmltest 등 — 버전 핀)
- 손숫자 0: `content/`·`layouts/` 에 개수 문맥 숫자(예: `\b\d+\s+(agents|skills|rules|에이전트|스킬|규칙)`)가 없는지 — 생성물 참조만 허용
- 외부 origin 0: 산출 HTML 의 `<script src>`·`<link href>`·`@font-face url` 이 같은 origin 인지
- **각 검사는 의도적 위반 1건으로 red 를 한 번 확인**하고 그 결과를 PR 본문에 남긴다(양성 대조)
- Lighthouse 등 점수는 참고치(게이트 아님)

## hiway-kit 레포 쪽 변경 (이쪽, 도메인 서빙 확인 후)

1. 패치 릴리스: `plugin.json` homepage, `packaging/targets.json` websiteURL·privacyPolicyURL → `build-targets.py --write`, README 링크, CHANGELOG
2. `site/` → 리다이렉트 스텁(R9), `scripts/check_doc_counts.py` 의 `site/` 패턴 정리(사이트 숫자의 소유가 `thishw/hiway` 로 이동)
3. `docs/codex-submission-checklist.md`·`docs/marketplace-submission.md` 의 URL 기록 갱신

## 범위 외

문서 검색 · 댓글 · 뉴스레터 · 분석 도구 · 광고 · `repository_dispatch` 자동 트리거(토큰 필요 — 이후) · Claude 디렉토리 목록 정보 변경(제출 시점 고정).
