def parse_duration(text):
    """Convert a duration string such as "1h30m", "45s" or "2m" to whole seconds.

    Units are h, m and s, each at most once and in that order. An empty string,
    an unknown unit or a malformed string raises ValueError.
    """
    raise NotImplementedError
