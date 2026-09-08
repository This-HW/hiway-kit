from intervals import merge_intervals


def test_merge_overlapping():
    assert merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]]) == [
        [1, 6],
        [8, 10],
        [15, 18],
    ]


def test_merge_touching():
    assert merge_intervals([[1, 4], [4, 5]]) == [[1, 5]]


def test_no_overlap():
    assert merge_intervals([[1, 2], [3, 4]]) == [[1, 2], [3, 4]]


def test_empty():
    assert merge_intervals([]) == []


def test_unsorted_input():
    assert merge_intervals([[5, 6], [1, 2]]) == [[1, 2], [5, 6]]
