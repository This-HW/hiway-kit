# 변경 제안: 결제 모듈에 3D Secure 인증 추가

현재 `payment_service.py`는 카드 결제를 인증 단계 없이 즉시 승인 처리한다.
이번 변경은 모든 카드 결제에 3D Secure(추가 본인인증) 단계를 삽입하고,
관련 결제 API 응답 스키마에 `challenge_url` 필드를 추가한다.

영향 대상으로 알려진 것: `checkout_ui`(응답 스키마 소비), `mobile_app`(콜백 처리 필요),
`refund_service`(인증 상태 참조 없음, 영향 없음으로 보임).
