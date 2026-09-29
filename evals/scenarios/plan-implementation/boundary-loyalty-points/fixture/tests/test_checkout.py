from shop.app.checkout import checkout
from shop.domain.order import Order
from shop.infra.repository import OrderRepository


def test_checkout_persists_order():
    repo = OrderRepository()
    order = Order("o-1", "c-1", 12000)
    assert checkout(repo, order) == order
    assert repo.get("o-1") == order
