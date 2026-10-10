"""Personal details must be removed before anything is saved or sent to an AI service."""
from app.redact import redact


def test_removes_sa_id_number():
    assert "8001015009087" not in redact("My ID is 8001015009087")
    assert "[ID number removed]" in redact("My ID is 8001015009087")


def test_removes_phone_numbers_in_common_formats():
    for number in ["082 123 4567", "0821234567", "+27 82 123 4567", "082-123-4567"]:
        out = redact(f"call me on {number}")
        assert "[phone number removed]" in out, number
        assert "4567" not in out, number


def test_removes_email_address():
    out = redact("email me at thandi.m@example.co.za please")
    assert "@" not in out
    assert "[email removed]" in out


def test_removes_long_account_numbers():
    assert "[number removed]" in redact("my account is 1234567890")


def test_keeps_ordinary_text_and_house_numbers():
    message = "There is a burst pipe outside 54 Voortrekker Road in Bellville"
    assert redact(message) == message
