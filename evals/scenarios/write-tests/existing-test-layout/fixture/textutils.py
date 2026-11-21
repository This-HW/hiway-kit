import re


def slugify(text: str) -> str:
    """Lowercase, turn every run of non-alphanumerics into one '-', strip leading/trailing '-'."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
