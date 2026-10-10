"""Contents pages and near-empty table fragments must never be used as answers."""
from app.noise import noise_reason


def test_contents_page_is_noise():
    text = "1. Introduction ........................ 3\n2. Definitions ........................ 5\n" * 4
    assert noise_reason(text) == "contents page"


def test_very_short_fragment_is_noise():
    assert noise_reason("| R | 5.91 | | |") == "too little text"


def test_real_paragraph_is_kept():
    text = ("The owner of a property is responsible for maintaining the water installation on "
            "their side of the meter, including repairing any leaks, and the City may require the "
            "owner to repair a leak within a reasonable period after giving notice. If the owner "
            "fails to do so the City may carry out the work and recover the costs.")
    assert noise_reason(text) is None
