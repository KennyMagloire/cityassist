"""Handle one resident message: rules, search, reply and checks."""
import logging
import re

from app import config
from app.llm import write_reply
from app.search import search

log = logging.getLogger(__name__)

SYSTEM_PROMPT = config.PROMPT_FILE.read_text(encoding="utf-8")
RECORDING_NOTICE = config.NOTICE_FILE.read_text(encoding="utf-8").strip()

FALLBACK = ("Sorry, I can't answer right now. Please call the City on 0860 103 089 "
            "or log a request at www.capetown.gov.za/servicerequests.")
NOT_FOUND = ("I couldn't find that in the City documents I have. For help, call "
             "0860 103 089 or visit www.capetown.gov.za/servicerequests.")
EMERGENCY = ("If this is an emergency such as a fire or flooding, call the City "
             "now on 021 480 7700.")
EMERGENCY_WORDS = ("fire", "flood", "live wire", "sparking", "electrocut", "sewage in")

def opening_message():
    """The recording notice, shown before anything else in every conversation."""
    return RECORDING_NOTICE


def build_context(passages):
    """Number the passages so the model can cite them as [1], [2]..."""
    blocks = []
    for n, p in enumerate(passages, start=1):
        blocks.append(f"[{n}] ({p['document']}, page {p['page']})\n{p['text']}")
    return "\n\n".join(blocks)


def cites_only_supplied(reply, passage_count):
    """True if every [n] in the reply refers to a passage we actually gave."""
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", reply)}
    return cited <= set(range(1, passage_count + 1))


def sounds_urgent(message):
    text = message.lower()
    return any(word in text for word in EMERGENCY_WORDS)

def answer(message, history):
    """Return the reply to one message. history = earlier turns as role/content dicts."""
    message = message.strip()
    if len(message) > config.MAX_MESSAGE_CHARS:
        return f"Please keep your message under {config.MAX_MESSAGE_CHARS} characters."

    try:
        passages = search(message)
    except Exception as error:
        log.warning("Search failed (%s)", type(error).__name__)
        return FALLBACK

    if not passages:
        return NOT_FOUND

    user_turn = f"Passages:\n{build_context(passages)}\n\nResident's message:\n{message}"
    try:
        reply = write_reply(SYSTEM_PROMPT, history + [{"role": "user", "content": user_turn}])
    except Exception as error:
        log.warning("Both reply services failed (%s)", type(error).__name__)
        return FALLBACK

    if not cites_only_supplied(reply, len(passages)):
        log.warning("Reply cited a passage that was not supplied")
        return NOT_FOUND

    return add_emergency_line(message, add_sources(reply, passages))

def add_emergency_line(message, reply):
    """Put the emergency number first when the message sounds urgent."""
    if sounds_urgent(message):
        return f"{EMERGENCY}\n\n{reply}"
    return reply

def add_sources(reply, passages):
    """Under the reply, list the document and page behind each [n] it cites."""
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", reply)})
    if not cited:
        return reply
    lines = [f"[{n}] {passages[n - 1]['document']}, page {passages[n - 1]['page']}"
             for n in cited]
    return reply + "\n\nSources:\n" + "\n".join(lines)