from ranking import rank_players


def test_sorted_descending():
    players = [
        {"name": "a", "score": 10},
        {"name": "b", "score": 30},
        {"name": "c", "score": 20},
    ]
    result = rank_players(players)
    assert [p["name"] for p in result] == ["b", "c", "a"]


def test_ties_preserve_original_order():
    players = [
        {"name": "a", "score": 10},
        {"name": "b", "score": 10},
        {"name": "c", "score": 10},
    ]
    result = rank_players(players)
    assert [p["name"] for p in result] == ["a", "b", "c"]
