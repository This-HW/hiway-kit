def add_item(item, bucket=[]):
    """Append item to bucket and return it. Each call made without an explicit
    bucket argument must start from a fresh, empty bucket."""
    bucket.append(item)
    return bucket
