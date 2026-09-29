"""결제 유스케이스."""
from shop.domain.order import Order
from shop.infra.repository import OrderRepository


def checkout(repo: OrderRepository, order: Order) -> Order:
    repo.save(order)
    return order
