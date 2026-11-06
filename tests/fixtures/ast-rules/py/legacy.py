CALLS = 0


def old_api(x, scale=1):
    global CALLS  # noqa: PLW0603 - fixture counts legacy calls
    CALLS += 1
    return x * scale
