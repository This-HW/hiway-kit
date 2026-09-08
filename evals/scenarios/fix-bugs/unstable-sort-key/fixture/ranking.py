def rank_players(players):
    """Sort players by score descending. Players with equal scores must keep
    their original relative order (stable sort)."""
    ranked = sorted(players, key=lambda p: p["score"])
    ranked.reverse()
    return ranked
