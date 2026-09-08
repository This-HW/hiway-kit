from src.inventory import add_widget, get_stock_level


def test_add_widget():
    add_widget("bolt", 5)
    assert get_stock_level("bolt") == 5
