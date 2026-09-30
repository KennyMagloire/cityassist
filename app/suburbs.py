"""Match what a resident typed to one of the official suburb names the model knows."""
import difflib

from app.classifier import SUBURBS

_OFFICIAL = set(SUBURBS)


def match_suburb(text):
    """Return the official suburb name, or None if nothing is close enough."""
    if not text:
        return None
    typed = " ".join(text.upper().split())
    if typed in _OFFICIAL:
        return typed
    close = difflib.get_close_matches(typed, SUBURBS, n=1, cutoff=0.8)
    return close[0] if close else None