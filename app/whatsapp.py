"""WhatsApp channel: check messages really come from Meta, answer them, send replies."""
import hashlib
import hmac
import logging
import time
from collections import defaultdict, deque

import httpx

from app import config
from app.assistant import FALLBACK, answer, opening_message
from app.database import get_history, save_message
from app.redact import redact

log = logging.getLogger(__name__)

MAX_PER_MINUTE = 6
MAX_REPLY_CHARS = 4000
NOT_TEXT = "Sorry, I can only read text messages for now. Please type your question or problem."
TOO_MANY = "You're sending messages quickly. Please wait a minute and try again."

_seen_ids = deque(maxlen=500)
_recent = defaultdict(deque)


# ---------- checks ----------

def signature_is_valid(raw_body, header):
    """True only if Meta signed this exact message with our app secret."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(config.WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def within_limit(sender):
    """At most MAX_PER_MINUTE messages per sender in any 60 seconds."""
    now = time.monotonic()
    times = _recent[sender]
    while times and now - times[0] > 60:
        times.popleft()
    if len(times) >= MAX_PER_MINUTE:
        return False
    times.append(now)
    return True


# ---------- small helpers ----------

def incoming_messages(payload):
    """Pull the messages out of Meta's nested envelope."""
    found = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            found.extend(change.get("value", {}).get("messages", []))
    return found

def log_failed_deliveries(payload):
    """Meta reports what happened to each message we sent; log the failures."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for status in change.get("value", {}).get("statuses", []):
                if status.get("status") == "failed":
                    log.warning("WhatsApp delivery failed: %s", status.get("errors"))

def conversation_id_for(number):
    """A stable ID per sender that does not store the phone number itself."""
    return "wa-" + hashlib.sha256(number.encode()).hexdigest()[:16]


def for_whatsapp(text):
    """WhatsApp uses *single* asterisks for bold and limits message length."""
    return



def send_text(to, text):
    if not isinstance(text, str) or not text.strip():
        log.warning("Reply was empty or not text (%s); sending the fallback instead",
                    type(text).__name__)
        text = FALLBACK
    response = httpx.post(
        f"{config.GRAPH_API_URL}/{config.WHATSAPP_PHONE_ID}/messages",
        headers={"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"},
        json={"messaging_product": "whatsapp", "to": to,
              "type": "text", "text": {"body": text}},
        timeout=15,
    )
    if response.status_code >= 400:
        log.warning("WhatsApp send failed: %s %s", response.status_code, response.text[:300])


# ---------- the main job ----------

def handle_message(msg):
    """Answer one incoming WhatsApp message. Runs in the background."""
    message_id = msg.get("id")
    if message_id in _seen_ids:
        return
    _seen_ids.append(message_id)

    sender = msg.get("from")
    if not sender:
        return
    if not within_limit(sender):
        send_text(sender, TOO_MANY)
        return
    if msg.get("type") != "text":
        send_text(sender, NOT_TEXT)
        return

    text = msg["text"]["body"]
    conversation_id = conversation_id_for(sender)
    history = get_history(conversation_id)
    if not history:
        send_text(sender, opening_message())
        save_message(conversation_id, "whatsapp", "assistant", opening_message())

    try:
        reply = answer(text, history, conversation_id, "whatsapp")
    except Exception:
        reply = FALLBACK

    save_message(conversation_id, "whatsapp", "user", redact(text))
    save_message(conversation_id, "whatsapp", "assistant", reply)
    send_text(sender, for_whatsapp(reply))