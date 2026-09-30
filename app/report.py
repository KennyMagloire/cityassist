"""Understand a reported problem: is it a report, what type, and where."""
import json
import re

import numpy as np

from app import config
from app.llm import write_reply

_type_vectors = np.load(config.TYPE_VECTORS_FILE)
_type_names = json.loads(config.TYPE_NAMES_FILE.read_text(encoding="utf-8"))

CANDIDATES = 8

UNDERSTAND_PROMPT = """You read messages sent to a City of Cape Town assistant.
Decide whether the resident is REPORTING a problem (something broken, missing, leaking, dirty or dangerous that needs fixing) or ASKING a question.
If it is a report, choose the request type from the numbered list, or 0 if none fits.
Use the whole conversation: the location may have been given in an earlier message.
Reply with JSON only, no other text:
{"intent": "report" or "question", "type_number": number, "suburb": "suburb name or empty", "street": "street or landmark or empty"}"""

def candidate_types(vector):
    """The request types whose names are closest in meaning to the message."""
    scores = _type_vectors @ vector
    best = np.argsort(scores)[::-1][:CANDIDATES]
    return [_type_names[i] for i in best]

def understand(message, history, vector):
    """Return intent, a valid request type (or None), suburb and street as typed."""
    candidates = candidate_types(vector)
    numbered = "\n".join(f"{n}. {name}" for n, name in enumerate(candidates, start=1))
    user_turn = f"Request types:\n{numbered}\n\nLatest message:\n{message}"

    raw = write_reply(UNDERSTAND_PROMPT, history + [{"role": "user", "content": user_turn}])
    data = _parse_json(raw)

    n = data.get("type_number", 0)
    valid = isinstance(n, int) and 1 <= n <= len(candidates)
    return {
        "intent": data.get("intent", "question"),
        "request_type": candidates[n - 1] if valid else None,
        "suburb": data.get("suburb") or "",
        "street": data.get("street") or "",
    }


def _parse_json(raw):
    """Pull the JSON object out of the reply; an empty dict if there is none."""
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}