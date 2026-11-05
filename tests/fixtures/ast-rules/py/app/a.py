"""Module a: uses legacy.old_api in several shapes."""
from legacy import old_api

MSG = "call old_api(9) here"  # old_api(9) in a comment must stay


def one():
    return old_api(2)


def two():
    return old_api(3, 4)


def kw():
    return old_api(5, scale=6)


def multi():
    return old_api(
        7,
        8,
    )


def nested():
    return old_api(old_api(2), 3)
