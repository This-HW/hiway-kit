import os


def write_if_absent(path, content):
    """Write content to path only if it doesn't already exist (used by multiple
    concurrent worker processes writing cache entries)."""
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(content)
