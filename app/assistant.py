"""Handle one resident message: rules, understanding, search or report, and checks."""
import csv
import logging
import re
from pathlib import Path

from app import config
from app.classifier import department_for, predict_band
from app.database import save_draft
from app.llm import write_reply
from app.redact import redact
from app.report import understand
from app.search import embed_question, search
from app.suburbs import match_suburb

log = logging.getLogger(__name__)

SYSTEM_PROMPT = config.PROMPT_FILE.read_text(encoding="utf-8")
RECORDING_NOTICE = config.NOTICE_FILE.read_text(encoding="utf-8").strip()


def _load_titles():
    """Map each document's file name (without .pdf) to its proper title from sources.csv."""
    with open(config.SOURCES_FILE, encoding="utf-8-sig", newline="") as f:
        return {Path(row["filename"]).stem: row["title"] for row in csv.DictReader(f)}


TITLES = _load_titles()

FALLBACK = ("Sorry, I can't answer right now. Please call the City on 0860 103 089 "
            "or log a request at www.capetown.gov.za/servicerequests.")
NOT_FOUND = ("I couldn't find that in the City documents I have. For help, call "
             "0860 103 089 or visit www.capetown.gov.za/servicerequests.")
EMERGENCY = ("If this is an emergency such as a fire or flooding, call the City "
             "now on 021 480 7700.")
EMERGENCY_WORDS = ("fire", "flood", "live wire", "sparking", "electrocut", "sewage in")

ASK_PROBLEM = ("I'd like to help you report this. Could you describe the problem in a bit "
               "more detail, for example what is broken, leaking or missing?")
ASK_LOCATION = "Thanks. Where is the problem? Please give the street and the suburb."

GREETINGS = {"hi", "hello", "hey", "hi there", "hello there",
             "good morning", "good afternoon", "good evening"}
GREETING_REPLY = ("Hello! I can answer questions about City of Cape Town services "
                  "or help you report a problem. What can I help you with?")
THANKS_REPLY = "You're welcome. If anything else comes up, just send a message."


# ---------- small helpers ----------

def opening_message():
    """The recording notice, shown before anything else in every conversation."""
    return RECORDING_NOTICE


def small_talk(message):
    """A friendly reply for a plain greeting or thanks; None for anything else."""
    text = re.sub(r"[^a-z ]", "", message.lower()).strip()
    if text in GREETINGS:
        return GREETING_REPLY
    if text.startswith(("thank", "cheers")) and len(text.split()) <= 6:
        return THANKS_REPLY
    return None


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
    text = message.lower().replace("fire hydrant", "")
    return any(word in text for word in EMERGENCY_WORDS)


def add_emergency_line(message, reply):
    """Put the emergency number first when the message sounds urgent."""
    if sounds_urgent(message):
        return f"{EMERGENCY}\n\n{reply}"
    return reply


def add_sources(reply, passages):
    """Under the reply, list each cited document and page once, with its proper title."""
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", reply)})
    if not cited:
        places = sorted({(TITLES.get(p["document"], p["document"]), p["page"]) for p in passages})
        return reply + "\n\nBased on:\n" + "\n".join(f"{title}, page {page}" for title, page in places)
    places = {}
    for n in cited:
        p = passages[n - 1]
        places.setdefault((p["document"], p["page"]), []).append(f"[{n}]")
    lines = [f"{' '.join(numbers)} {TITLES.get(doc, doc)}, page {page}"
             for (doc, page), numbers in places.items()]
    return reply + "\n\nSources:\n" + "\n".join(lines)


def vector_for_report(message, history, vector):
    """For follow-ups like 'Main Road, Claremont', match request types against the recent
    conversation, not just the latest message."""
    earlier = [m["content"] for m in history if m["role"] == "user"][-2:]
    if not earlier:
        return vector
    return embed_question(" ".join(earlier + [message]))


# ---------- the two paths ----------

def answer_question(message, history, vector):
    passages = search(message, vector=vector)
    if not passages:
        return NOT_FOUND

    user_turn = f"Passages:\n{build_context(passages)}\n\nResident's message:\n{message}"
    try:
        reply = write_reply(SYSTEM_PROMPT, history + [{"role": "user", "content": user_turn}])
    except Exception as error:
        log.warning("Both reply services failed (%s)", type(error).__name__)
        return FALLBACK

    reply = reply.replace("the passages you provided", "the City documents I have")
    if not cites_only_supplied(reply, len(passages)):
        log.warning("Reply cited a passage that was not supplied")
        return NOT_FOUND
    return add_sources(reply, passages)


def handle_report(info, conversation_id, channel):
    if not info["request_type"]:
        return ASK_PROBLEM

    suburb = match_suburb(info["suburb"])
    if not suburb:
        if info["suburb"]:
            return (f"I couldn't find \"{info['suburb']}\" among Cape Town's suburbs. "
                    "Could you check the spelling, or give a nearby suburb?")
        return ASK_LOCATION

    department = department_for(info["request_type"]) or "the responsible department"
    band = predict_band(info["request_type"], suburb)
    draft_id = save_draft(conversation_id, channel, info["request_type"], department,
                          suburb, info["street"], band)
    return format_draft(draft_id, info, suburb, department, band)


def format_draft(draft_id, info, suburb, department, band):
    where = f"{info['street']}, {suburb.title()}" if info["street"] else suburb.title()
    return (
        f"I've prepared draft request number {draft_id}.\n\n"
        f"Problem: {info['request_type']}\n"
        f"Where: {where}\n"
        f"Handled by: {department}\n"
        f"Usually resolved in: {band} (based on the City's 2020 records; "
        "an indication, not a promise)\n\n"
        "This draft has not been sent to the City and is not a City reference number. "
        "To log it officially, call 0860 103 089 or use www.capetown.gov.za/servicerequests."
    )


# ---------- the main entry points ----------

def answer_with_details(message, history, conversation_id="local", channel="web"):
    """Return the reply and what the assistant decided (intent, request type, suburb)."""
    message = redact(message.strip())
    history = [{"role": m["role"], "content": redact(m["content"])} for m in history]
    if len(message) > config.MAX_MESSAGE_CHARS:
        return f"Please keep your message under {config.MAX_MESSAGE_CHARS} characters."

    chat = small_talk(message)
    if chat:
        return {"reply": chat, "intent": "small_talk", "request_type": None, "suburb": ""}

    try:
        vector = embed_question(message)
        context_vector = vector_for_report(message, history, vector)
    except Exception as error:
        log.warning("Embedding failed (%s)", type(error).__name__)
        return FALLBACK

    try:
        info = understand(message, history, context_vector)
    except Exception as error:
        log.warning("Understanding failed (%s); treating as a question", type(error).__name__)
        info = {"intent": "question"}

    said = " ".join([m["content"] for m in history if m["role"] == "user"] + [message]).lower()
    if info.get("suburb") and info["suburb"].lower() not in said:
        info["suburb"] = ""

    if info.get("intent") == "report":
        reply = handle_report(info, conversation_id, channel)
    else:
        is_follow_up = len(message.split()) <= 4
        search_vector = context_vector if is_follow_up else vector
        reply = answer_question(message, history, search_vector)
    return {"reply": add_emergency_line(message, reply), "intent": info.get("intent", "question"),
            "request_type": info.get("request_type"), "suburb": info.get("suburb", "")}


def answer(message, history, conversation_id="local", channel="web"):
    """The reply only, for WhatsApp and anything else that needs just the text."""
    result = answer_with_details(message, history, conversation_id, channel)
    return result if isinstance(result, str) else result["reply"]