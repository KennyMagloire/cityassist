"""Document pipeline, stage 1: cutting the City's documents into passages.

These test the functions in scripts/extract_chunks.py on small made-up text, so they
need no PDFs and no internet.
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("pdfplumber")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import extract_chunks as ex  # noqa: E402


def test_table_rows_become_readable_lines():
    table = [["Block", "Rate"], ["0 - 600 kWh", "359.82 c/kWh"], [None, None]]
    assert ex.format_table(table) == "Block | Rate\n0 - 600 kWh | 359.82 c/kWh"


def test_short_paragraphs_stay_whole():
    text = "First paragraph about leaks.\n\nSecond paragraph about meters."
    assert ex.split_text_units(text) == ["First paragraph about leaks.", "Second paragraph about meters."]


def test_long_paragraph_is_split_into_sentences():
    long_line = ("This sentence is about water. " * 40).strip()
    units = ex.split_text_units(long_line)
    assert len(units) > 1
    assert all(len(u) <= ex.TARGET_CHARS for u in units)


def test_pieces_stay_close_to_the_target_size():
    text = "\n\n".join(f"Paragraph {i} explains how residents report a burst pipe to the City." for i in range(60))
    chunks = ex.split_into_chunks(text)
    assert len(chunks) > 1
    assert all(len(c) <= ex.TARGET_CHARS + ex.OVERLAP_CHARS + 1 for c in chunks)


def test_each_piece_repeats_the_end_of_the_previous_one():
    text = "\n\n".join(f"Paragraph {i} explains how residents report a burst pipe to the City." for i in range(60))
    chunks = ex.split_into_chunks(text)
    for before, after in zip(chunks, chunks[1:]):
        assert before[-40:] in after, "consecutive pieces should overlap so no sentence is cut off"


def test_tiny_pieces_are_dropped():
    assert ex.split_into_chunks("Page 3") == []
