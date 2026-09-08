def clamp(value, lo, hi):
    """value를 [lo, hi] 범위로 자른다."""
    if lo > hi:
        raise ValueError("lo must be <= hi")
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value
