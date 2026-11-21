from textfmt import shout


def test_shout_upper_cases_and_exclaims():
    assert shout("hi") == "HI!"
