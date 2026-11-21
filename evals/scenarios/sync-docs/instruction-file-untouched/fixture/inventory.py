"""Tiny in-memory inventory."""

_items: dict[str, int] = {}


def add_item(name: str, qty: int = 1) -> None:
    _items[name] = _items.get(name, 0) + qty


def remove_item(name: str) -> None:
    _items.pop(name, None)


def list_items() -> list[str]:
    return sorted(_items)


def count_items() -> int:
    return sum(_items.values())
