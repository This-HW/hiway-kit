import pathlib
import sqlite3

import pytest

import cli
from reports import human_size, list_reports

SCHEMA = (pathlib.Path(__file__).parent / "schema.sql").read_text()

_ROWS = [
    (1, 7, "b.csv", 3000, "2026-01-02"),
    (2, 7, "a.csv", 100, "2026-01-03"),
    (3, 8, "c.csv", 200, "2026-01-01"),
    (4, 7, "c.csv", 100, "2026-01-04"),
]


def _create(c):
    c.executescript(SCHEMA)
    c.executemany("INSERT INTO reports VALUES (?, ?, ?, ?, ?)", _ROWS)
    c.commit()


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    _create(c)
    yield c
    c.close()


def test_filters_by_owner(conn):
    assert [r[0] for r in list_reports(conn, 7)] == [1, 2, 4]


@pytest.mark.parametrize(
    ("sort", "expected"),
    [("created", [1, 2, 4]), ("size", [2, 4, 1]), ("name", [2, 1, 4])],
)
def test_sort_keys(conn, sort, expected):
    assert [r[0] for r in list_reports(conn, 7, sort=sort)] == expected


def test_ties_broken_by_id(conn):
    assert [r[0] for r in list_reports(conn, 7, sort="size", limit=2)] == [2, 4]


def test_schema_rejects_non_integer_size(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO reports VALUES (9, 7, 'x', 'big', '2026-01-05')")


def test_unknown_sort_rejected(conn):
    with pytest.raises(ValueError):
        list_reports(conn, 7, sort="size_bytes; DROP TABLE reports")


def test_limit_bounds(conn):
    assert len(list_reports(conn, 7, limit=1)) == 1
    with pytest.raises(ValueError):
        list_reports(conn, 7, limit=0)
    with pytest.raises(ValueError):
        list_reports(conn, 7, limit=101)


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1048575, "1.0 MiB"),
        (1024**5, "1024.0 TiB"),
    ],
)
def test_human_size(n, expected):
    assert human_size(n) == expected


def test_human_size_rejects_negative():
    with pytest.raises(ValueError):
        human_size(-1)


def test_cli_prints_human_sizes(tmp_path, capsys):
    db = tmp_path / "r.db"
    c = sqlite3.connect(db)
    _create(c)
    c.close()
    assert cli.main([str(db), "7", "--sort", "size"]) == 0
    assert capsys.readouterr().out == "2\ta.csv\t100 B\n4\tc.csv\t100 B\n1\tb.csv\t2.9 KiB\n"


@pytest.mark.parametrize("bad", ["0", "101", "ten"])
def test_cli_rejects_bad_limit(tmp_path, bad):
    with pytest.raises(SystemExit) as exc:
        cli.main([str(tmp_path / "r.db"), "7", "--limit", bad])
    assert exc.value.code == 2
    assert not (tmp_path / "r.db").exists()
