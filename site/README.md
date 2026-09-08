# site/ — hiway-kit 로그 (GitHub Pages)

프로젝트 개발 과정 · 업데이트 · AI 에이전트 엔지니어링 트렌드를 발행하는 정적 사이트.

- **생성기**: Hugo (extended). 외부 테마/모듈 의존 없음 — `layouts/`의 최소 커스텀 테마 사용.
- **발행**: `main`에 `site/**` 변경이 push되면 `.github/workflows/pages.yml`가 빌드→GitHub Pages 배포.
- **URL**: https://This-HW.github.io/hiway-kit/ , 글은 `/posts/<slug>/`.

## 새 글 쓰기

```bash
# site/content/posts/YYYY-MM-DD-slug.md 생성, 아래 front matter로 시작
```

```yaml
---
title: "제목"
date: 2026-07-02
description: "목록·검색·OG에 쓰이는 한 줄 요약"
categories: ["개발 과정"]   # AI 에이전트 / 리서치 / 프로젝트 업데이트 등
tags: ["키워드"]
---
```

본문은 마크다운. 인라인 HTML(콜아웃 `.callout`, 다이어그램 `.loop`)도 허용된다(`markup.goldmark.renderer.unsafe = true`).

## 로컬 미리보기

```bash
cd site && hugo server
# http://localhost:1313/hiway-kit/
```

## 최초 1회 설정 (저장소 관리자)

GitHub → Settings → Pages → **Source: GitHub Actions**. 이후 `main` push마다 자동 배포.
