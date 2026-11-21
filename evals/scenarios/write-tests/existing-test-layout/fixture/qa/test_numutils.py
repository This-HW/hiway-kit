from numutils import is_even


def test_even_numbers():
    assert is_even(0)
    assert is_even(4)


def test_odd_numbers():
    assert not is_even(3)
