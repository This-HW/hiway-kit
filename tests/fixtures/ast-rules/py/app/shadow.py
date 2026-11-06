"""Has its own old_api; unrelated to legacy."""


def old_api(x):
    return -x


def use():
    return old_api(5)
