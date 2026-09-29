"""주문 저장소 (메모리 구현)."""
from shop.domain.order import Order


class OrderRepository:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> Order:
        return self._orders[order_id]
