"""주문 도메인 모델."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    total: int  # 원 단위 결제 금액
