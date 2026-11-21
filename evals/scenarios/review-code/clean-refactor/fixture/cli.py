"""Command line entry point: list one owner's reports."""

from __future__ import annotations

import argparse
import sqlite3

from reports import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX, SORT_KEYS, human_size, list_reports


def _limit(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
    if not 1 <= value <= PAGE_SIZE_MAX:
        raise argparse.ArgumentTypeError(f"must be between 1 and {PAGE_SIZE_MAX}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reports")
    parser.add_argument("db")
    parser.add_argument("owner_id", type=int)
    parser.add_argument("--sort", default="created", choices=SORT_KEYS)
    parser.add_argument("--limit", type=_limit, default=PAGE_SIZE_DEFAULT)
    args = parser.parse_args(argv)

    conn = sqlite3.connect(args.db)
    try:
        for rid, name, size in list_reports(conn, args.owner_id, args.sort, args.limit):
            print(f"{rid}\t{name}\t{human_size(size)}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
