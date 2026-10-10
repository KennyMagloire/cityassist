"""WhatsApp safeguards: signature check, rate limit, privacy of phone numbers, formatting."""
import hashlib
import hmac

from app import whatsapp as w


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()


def test_message_signed_by_meta_is_accepted():
    body = b'{"entry": []}'
    assert w.signature_is_valid(body, _sign(body))


def test_fake_or_missing_signature_is_rejected():
    body = b'{"entry": []}'
    assert not w.signature_is_valid(body, "sha256=" + "0" * 64)
    assert not w.signature_is_valid(body, None)
    assert not w.signature_is_valid(body, "")


def test_changed_message_fails_the_signature():
    body = b'{"text": "hello"}'
    assert not w.signature_is_valid(b'{"text": "HACKED"}', _sign(body))


def test_rate_limit_allows_six_messages_a_minute_then_blocks():
    sender = "unit-test-sender"
    results = [w.within_limit(sender) for _ in range(7)]
    assert results == [True] * 6 + [False]


def test_rate_limit_is_per_person():
    for _ in range(6):
        w.within_limit("person-a")
    assert w.within_limit("person-b")


def test_phone_number_is_never_stored_in_the_conversation_id():
    cid = w.conversation_id_for("27821234567")
    assert "27821234567" not in cid
    assert cid == w.conversation_id_for("27821234567")      # same person, same conversation
    assert cid != w.conversation_id_for("27829999999")


def test_reply_formatting_for_whatsapp():
    assert w.for_whatsapp("**Call** the City") == "*Call* the City"
    assert len(w.for_whatsapp("a" * 5000)) == w.MAX_REPLY_CHARS


def test_messages_are_pulled_out_of_metas_envelope():
    payload = {"entry": [{"changes": [{"value": {"messages": [{"id": "m1"}, {"id": "m2"}]}}]}]}
    assert [m["id"] for m in w.incoming_messages(payload)] == ["m1", "m2"]
