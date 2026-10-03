"""Web chat page. Based on Keo's Gradio page from the first prototype,
connected to the shared assistant."""
import uuid

import gradio as gr

from app.assistant import FALLBACK, answer_with_details, opening_message
from app.database import save_message
from app.redact import redact
from app.whatsapp import TOO_MANY, within_limit
HISTORY_TURNS = 6

THEME = gr.themes.Soft(primary_hue="teal", secondary_hue="slate")
CSS = """
.gradio-container {max-width: 820px !important; margin: auto;}
#footer {font-size: 0.85em; color: #6b7280; text-align: center;}
"""


def as_text(content):
    """Gradio may store a message as plain text or as a list of parts; return text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return str(content)

def client_key(request):
    """Identify the sender by IP address (Render passes it in x-forwarded-for)."""
    ip = ""
    if request is not None:
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip()
        if not ip and request.client:
            ip = request.client.host
    return "web-" + (ip or "unknown")


def respond(message, history, conversation_id, request: gr.Request):
    if not message or not message.strip():
        return history, ""
    if not within_limit(client_key(request)):
        return history + [{"role": "user", "content": message},
                          {"role": "assistant", "content": TOO_MANY}], ""

    earlier = [{"role": m["role"], "content": as_text(m["content"])}
               for m in history[-HISTORY_TURNS:]]
    try:
        result = answer_with_details(message, earlier, conversation_id, "web")
    except Exception:
        result = FALLBACK
    if isinstance(result, str):
        result = {"reply": result, "intent": None, "request_type": None}

    save_message(conversation_id, "web", "user", redact(message))
    save_message(conversation_id, "web", "assistant", result["reply"],
                 result["intent"], result["request_type"])

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": result["reply"]},
    ]
    return history, ""

def start():
    """A new conversation: a fresh ID, and the recording notice first."""
    return [{"role": "assistant", "content": opening_message()}], str(uuid.uuid4())


def build_page():
    with gr.Blocks(title="CityAssist") as page:
        gr.Markdown(
            "# 🏙️ CityAssist\n"
            "Ask about water, electricity, refuse and roads in Cape Town, "
            "or describe a problem you want to report."
        )
        chatbot = gr.Chatbot(height="65vh", show_label=False)
        conversation_id = gr.State()

        with gr.Row():
            msg = gr.Textbox(placeholder="Type your message here...",
                             show_label=False, scale=8)
            send = gr.Button("Send", variant="primary", scale=1)
        clear = gr.Button("Clear conversation")

        gr.Examples(
            examples=[
                "How much does water cost per kilolitre?",
                "I have a water leak at my house",
                "There's a pothole on my street",
                "My refuse bin was not collected",
            ],
            inputs=msg,
            label="Try asking",
        )

        gr.Markdown(
            "Student prototype, not an official City of Cape Town service. "
            "To log a request officially: 0860 103 089 · www.capetown.gov.za/servicerequests",
            elem_id="footer",
        )

        send.click(respond, [msg, chatbot, conversation_id], [chatbot, msg])
        msg.submit(respond, [msg, chatbot, conversation_id], [chatbot, msg])
        clear.click(start, None, [chatbot, conversation_id], queue=False)
        page.load(start, None, [chatbot, conversation_id])
    return page