"""Remove ID numbers, emails and phone or account numbers before text leaves the server."""
import re

PATTERNS = [
    (re.compile(r"\b\d{13}\b"), "[ID number removed]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email removed]"),
    (re.compile(r"(?:\+27|0)[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{4}\b"), "[phone number removed]"),
    (re.compile(r"\b\d{9,12}\b"), "[number removed]"),
]


def redact(text):
    for pattern, label in PATTERNS:
        text = pattern.sub(label, text)
    return text