"""The safety rules in assistant.py that do not depend on the AI services."""
from app import assistant as a

PASSAGES = [
    {"document": "doc_a", "page": 3, "text": "Leaks on your side of the meter are yours to fix."},
    {"document": "doc_b", "page": 7, "text": "Report leaks on 0860 103 089."},
]


# ---------- greetings ----------

def test_greetings_get_a_friendly_reply_without_ai():
    for message in ["hi", "Hello!", "good morning", "Hey"]:
        assert a.small_talk(message) == a.GREETING_REPLY, message


def test_thanks_gets_a_closing_reply():
    assert a.small_talk("Thanks for your help!") == a.THANKS_REPLY


def test_a_real_request_is_not_small_talk():
    assert a.small_talk("hi, my water is off") is None
    assert a.small_talk("There is a pothole") is None


# ---------- emergency line ----------

def test_urgent_words_trigger_the_emergency_line():
    for message in ["My house is on fire", "The street is flooded", "a live wire is down",
                    "the box is sparking"]:
        assert a.sounds_urgent(message), message


def test_fire_hydrant_is_not_an_emergency():
    assert not a.sounds_urgent("The fire hydrant on my street is leaking")


def test_emergency_number_comes_first():
    reply = a.add_emergency_line("there is a fire", "Thanks.")
    assert reply.startswith(a.EMERGENCY)


# ---------- citations and sources ----------

def test_citations_must_point_to_supplied_passages():
    assert a.cites_only_supplied("Fix it yourself [1]. Call the City [2].", 2)
    assert not a.cites_only_supplied("According to [3], ...", 2)


def test_sources_list_titles_and_pages_for_cited_passages():
    out = a.add_sources("Leaks are yours to fix [1].", PASSAGES)
    assert "Sources:" in out
    assert "[1]" in out and "page 3" in out
    assert "page 7" not in out          # passage 2 was not cited


def test_no_sources_when_the_reply_says_it_has_no_answer():
    reply = "I'm sorry, but the City documents I have don't include that information."
    assert a.add_sources(reply, PASSAGES) == reply


def test_uncited_answer_lists_documents_used():
    out = a.add_sources("You can report it by phone.", PASSAGES)
    assert "Based on:" in out


def test_the_word_passages_is_never_shown_to_residents():
    out = a.tidy("As the passages you provided say, call the City. See passage [2].")
    assert "passage" not in out.lower()
    assert "[2]" in out


def test_context_numbers_each_passage_with_its_page():
    ctx = a.build_context(PASSAGES)
    assert ctx.startswith("[1] (doc_a, page 3)")
    assert "[2] (doc_b, page 7)" in ctx


# ---------- invented suburbs ----------

def test_suburb_the_resident_wrote_is_kept_even_with_a_typo():
    assert a.resident_wrote("Claremont", "main road, claremon")
    assert a.resident_wrote("Sea Point", "pothole on main road, sea point")


def test_suburb_the_resident_never_wrote_is_rejected():
    said = "the stormwater drain outside 54 voortrekker road is blocked"
    assert not a.resident_wrote("Mowbray", said)
    assert not a.resident_wrote("Camps Bay", said)


# ---------- drafts ----------

def test_draft_says_it_was_not_sent_to_the_city():
    info = {"request_type": "Pothole&Defect Road Foot Bic Way/Kerbs", "street": "Main Road"}
    text = a.format_draft(8, info, "CLAREMONT", "Roads Infrastructure Management", "Over 14 days")
    assert "draft request number 8" in text
    assert "Main Road, Claremont" in text
    assert "has not been sent to the City" in text
    assert "an indication, not a promise" in text


def test_overlong_messages_are_refused_before_any_ai_call():
    reply = a.answer("x" * 1001, [])
    assert "under 1000 characters" in reply
