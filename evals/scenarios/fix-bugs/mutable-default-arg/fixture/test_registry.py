from registry import add_item


def test_independent_calls_start_fresh():
    assert add_item("a") == ["a"]
    assert add_item("b") == ["b"]


def test_explicit_bucket_still_accumulates():
    bucket = []
    assert add_item("x", bucket) == ["x"]
    assert add_item("y", bucket) == ["x", "y"]
