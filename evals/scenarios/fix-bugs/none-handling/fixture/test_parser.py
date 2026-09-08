from parser import get_domain


def test_valid_email():
    assert get_domain("user@example.com") == "EXAMPLE.COM"


def test_no_at_sign_returns_none():
    assert get_domain("not-an-email") is None


def test_none_input_returns_none():
    assert get_domain(None) is None


def test_empty_string_returns_none():
    assert get_domain("") is None
