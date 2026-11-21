"""Read-only report queries over the local SQLite store."""

from __future__ import annotations

import sqlite3

# ORDER BY cannot take a bound parameter, so the column name comes from this
# table and never from the caller's string.
_SORT_COLUMNS = {
    "created": "created_at",
    "size": "size_bytes",
    "name": "name",
}
SORT_KEYS = tuple(_SORT_COLUMNS)

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100

_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


def list_reports(
    conn: sqlite3.Connection,
    owner_id: int,
    sort: str = "created",
    limit: int = PAGE_SIZE_DEFAULT,
) -> list[tuple[int, str, int]]:
    """Return (id, name, size_bytes) rows owned by ``owner_id``.

    Ties on the sort column are broken by ``id`` so pages are stable.
    """
    column = _SORT_COLUMNS.get(sort)
    if column is None:
        raise ValueError(f"unknown sort key: {sort!r}")
    if not 1 <= limit <= PAGE_SIZE_MAX:
        raise ValueError(f"limit out of range: {limit}")
    query = (
        "SELECT id, name, size_bytes FROM reports "
        f"WHERE owner_id = ? ORDER BY {column}, id LIMIT ?"
    )
    return conn.execute(query, (owner_id, limit)).fetchall()


def human_size(n: int) -> str:
    """Format a byte count with binary units, e.g. 1536 -> '1.5 KiB'."""
    if n < 0:
        raise ValueError(f"negative size: {n}")
    if n < 1024:
        return f"{n} B"
    size = n / 1024
    unit = 1
    # Compare the value as it will be printed, so 1048575 B is "1.0 MiB"
    # rather than "1024.0 KiB".
    while round(size, 1) >= 1024 and unit < len(_UNITS) - 1:
        size /= 1024
        unit += 1
    return f"{size:.1f} {_UNITS[unit]}"
