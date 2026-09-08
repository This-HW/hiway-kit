from textutils import shout, slugify


def test_shout_existing_behavior_unchanged():
    assert shout("hi") == "HI!"


def test_slugify_basic():
    assert slugify("Hello World!") == "hello-world"


def test_slugify_collapses_whitespace_and_punctuation():
    assert (
        slugify("  Multiple   Spaces, and Punctuation!!")
        == "multiple-spaces-and-punctuation"
    )


def test_slugify_empty_string():
    assert slugify("") == ""
