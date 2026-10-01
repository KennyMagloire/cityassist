"""CityAssist backend: one FastAPI application serving the web chat (and later WhatsApp)."""
import gradio as gr
from fastapi.responses import RedirectResponse
from fastapi import FastAPI

from app.database import init_db
from app.web_chat import CSS, THEME, build_page

app = FastAPI(title="CityAssist")


@app.get("/health")
def health():
    @app.get("/")
    def home():
        """Send anyone who opens the bare address straight to the chat page."""
        return RedirectResponse("/chat")
    """Lets us, and the hosting service, check the app is running."""
    return {"status": "ok"}


init_db()
app = gr.mount_gradio_app(app, build_page(), path="/chat", theme=THEME, css=CSS)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)