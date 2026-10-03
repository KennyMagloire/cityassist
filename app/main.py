"""CityAssist backend: one FastAPI application serving the web chat and WhatsApp."""
import gradio as gr
from fastapi import BackgroundTasks, FastAPI, Request, Response
from app.whatsapp import handle_message, incoming_messages, log_failed_deliveries, signature_is_valid
from fastapi.responses import PlainTextResponse, RedirectResponse

from app import config
from app.database import init_db
from app.web_chat import CSS, THEME, build_page
from app.whatsapp import handle_message, incoming_messages, signature_is_valid

app = FastAPI(title="CityAssist")


@app.get("/health")
def health():
    """Lets us, and the hosting service, check the app is running."""
    return {"status": "ok"}


@app.get("/")
def home():
    """Send anyone who opens the bare address straight to the chat page."""
    return RedirectResponse("/chat")


@app.get("/whatsapp")
def whatsapp_verify(request: Request):
    """Meta calls this once to check the address is ours (the verify token)."""
    params = request.query_params
    if (config.WHATSAPP_ENABLED
            and params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == config.WHATSAPP_VERIFY_TOKEN):
        return PlainTextResponse(params.get("hub.challenge", ""))
    return Response(status_code=403)


@app.post("/whatsapp")
async def whatsapp_receive(request: Request, background: BackgroundTasks):
    """Meta sends every incoming message here. Check it, answer later, reply OK now."""
    if not config.WHATSAPP_ENABLED:
        return Response(status_code=503)
    raw = await request.body()
    if not signature_is_valid(raw, request.headers.get("X-Hub-Signature-256")):
        return Response(status_code=403)
    payload = await request.json()
    log_failed_deliveries(payload)
    for msg in incoming_messages(payload):
        background.add_task(handle_message, msg)
    return {"status": "received"}


init_db()
app = gr.mount_gradio_app(app, build_page(), path="/chat", theme=THEME, css=CSS)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)