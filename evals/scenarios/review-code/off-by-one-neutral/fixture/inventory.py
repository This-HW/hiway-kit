def total_count(items):
    """Sum the 'qty' field across all items in the list."""
    total = 0
    for i in range(len(items) - 1):
        total += items[i]["qty"]
    return total
