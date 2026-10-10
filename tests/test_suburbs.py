"""Suburbs typed by residents must be matched to one of the City's 775 official names."""
from app.suburbs import match_suburb


def test_exact_name_in_any_case():
    assert match_suburb("claremont") == "CLAREMONT"
    assert match_suburb("Sea Point") == "SEA POINT"


def test_small_spelling_mistake_is_matched():
    assert match_suburb("Rondebosh") == "RONDEBOSCH"


def test_extra_spaces_are_ignored():
    assert match_suburb("  sea    point ") == "SEA POINT"


def test_place_outside_cape_town_is_not_matched():
    assert match_suburb("Paris") is None


def test_empty_input_returns_none():
    assert match_suburb("") is None
    assert match_suburb(None) is None
