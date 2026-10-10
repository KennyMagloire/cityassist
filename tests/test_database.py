"""Saving messages and drafts, using a temporary database so real records are untouched."""
import pytest

from app import config, database


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_FILE", tmp_path / "test.db")
    database.init_db()


def test_history_comes_back_oldest_first():
    database.save_message("c1", "web", "user", "hi")
    database.save_message("c1", "web", "assistant", "Hello!", "small_talk")
    assert database.get_history("c1") == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello!"},
    ]


def test_conversations_are_kept_apart():
    database.save_message("c1", "web", "user", "first person")
    database.save_message("c2", "web", "user", "second person")
    assert [m["content"] for m in database.get_history("c2")] == ["second person"]


def test_text_that_looks_like_sql_is_stored_safely():
    attack = "'); DROP TABLE messages; --"
    database.save_message("c1", "web", "user", attack)
    assert database.get_history("c1")[0]["content"] == attack


def test_each_draft_gets_its_own_number():
    first = database.save_draft("c1", "web", "No Power", "Electricity", "LANGA", "", "Same day (under 1 day)")
    second = database.save_draft("c1", "web", "No Power", "Electricity", "LANGA", "", "Same day (under 1 day)")
    assert second == first + 1
