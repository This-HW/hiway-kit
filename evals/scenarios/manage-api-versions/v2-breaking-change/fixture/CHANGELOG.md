# API Changelog

## v2.0.0 — 2026-06-01
BREAKING: `/api/v1/orders` 엔드포인트 제거. `/api/v2/orders`를 사용하라.
인증 헤더가 `Authorization: Bearer` 에서 `X-Auth-Token`으로 변경됨.

## v1.9.0 — 2026-05-01
Feature: `/api/v1/orders/bulk` 벌크 생성 엔드포인트 추가.

## v1.8.2 — 2026-04-10
Patch: `/api/v1/orders/:id` 응답의 날짜 포맷 버그 수정.
