from dupes import find_duplicates


def test_no_duplicates():
    assert sorted(find_duplicates([1, 2, 3])) == []


def test_some_duplicates():
    assert sorted(find_duplicates([1, 2, 2, 3, 3, 3])) == [2, 3]


def test_empty():
    assert find_duplicates([]) == []


def test_all_same():
    assert sorted(find_duplicates([5, 5, 5, 5])) == [5]
