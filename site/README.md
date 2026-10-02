# site/ — 옛 주소 리다이렉트 전용

`https://this-hw.github.io/hiway-kit/` 는 한때 이 디렉토리의 Hugo 사이트였다. 제품 사이트는 이제 별도 레포
`thishw/hiway` 의 **https://hiway.thishw.com/** 이고, 사이트 콘텐츠·숫자는 거기가 소유한다. 이 디렉토리에는 옛
주소로 들어온 방문자·검색엔진·피드 구독자를 새 주소로 보내는 **정적 리다이렉트 스텁**만 남는다.

- `redirects.json` — 옛 경로 → 새 경로 표. **SSOT 하나.** 옛 Hugo 산출물 73개 파일 전수를 싣는다(`_meta.inventory`).
- `../scripts/build-site-redirects.py` — 표에서 경로별 HTML(`meta refresh` + `canonical` + `noindex` + 누를 링크)·
  RSS 안내·`404.html`·`robots.txt` 를 `site/public/` 에 만든다. 산출물은 커밋하지 않는다(`.gitignore`).
- `../.github/workflows/pages.yml` — main 에서 위 생성기를 돌려 `site/public/` 을 GitHub Pages 에 올린다.

```bash
python3 scripts/build-site-redirects.py --check   # 표 유효성·경로 봉쇄 (verify-done.sh §26, CI)
python3 scripts/build-site-redirects.py --write   # → site/public/
```

경로를 더하거나 바꾸려면 **표만** 고친다. 글 원문은 git 이력(`c67cde8` 이전)과 새 사이트에 있다.
