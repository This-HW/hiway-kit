def chunk(items, size):
    """Split items into consecutive lists of at most `size` elements."""
    if size < 1:
        raise ValueError("size must be >= 1")
    return [items[i : i + size] for i in range(0, len(items) - size + 1, size)]
