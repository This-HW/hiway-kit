from lru import LRUCache


def test_basic_get_put():
    cache = LRUCache(2)
    cache.put(1, "a")
    cache.put(2, "b")
    assert cache.get(1) == "a"


def test_eviction_of_least_recently_used():
    cache = LRUCache(2)
    cache.put(1, "a")
    cache.put(2, "b")
    cache.get(1)  # 1 becomes most-recently-used
    cache.put(3, "c")  # evicts 2 (least-recently-used)
    assert cache.get(2) == -1
    assert cache.get(1) == "a"
    assert cache.get(3) == "c"


def test_missing_key_returns_minus_one():
    cache = LRUCache(1)
    assert cache.get(99) == -1


def test_put_overwrite_existing_key():
    cache = LRUCache(2)
    cache.put(1, "a")
    cache.put(1, "b")
    assert cache.get(1) == "b"
