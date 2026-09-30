"""Web chat page. Based on Keo's Gradio page from the first prototype,
connected to the shared assistant."""
import gradio as gr

from app.assistant import FALLBACK, answer, opening_message

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


def respond(message, history):
    if not message or not message.strip():
        return history, ""

    earlier = [{"role": m["role"], "content": as_text(m["content"])}
               for m in history[-HISTORY_TURNS:]]
    try:
        reply = answer(message, earlier)
    except Exception:
        reply = FALLBACK

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]
    return history, ""


def start():
    """A new conversation always opens with the recording notice."""
    return [{"role": "assistant", "content": opening_message()}]


def build_page():
    with gr.Blocks(title="CityAssist") as page:
        gr.Markdown(
            "# 🏙️ CityAssist\n"
            "Ask about water, electricity, refuse and roads in Cape Town, "
            "or describe a problem you want to report."
        )
        chatbot = gr.Chatbot(value=start(), height=480, show_label=False)

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

        send.click(respond, [msg, chatbot], [chatbot, msg])
        msg.submit(respond, [msg, chatbot], [chatbot, msg])
        clear.click(start, None, chatbot, queue=False)
    return page