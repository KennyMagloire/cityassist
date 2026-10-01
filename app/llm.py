"""Write a reply with Groq, and fall back to Gemini if Groq fails."""
import logging

from google import genai
from google.genai import types
from groq import Groq

from app import config

log = logging.getLogger(__name__)
_groq = Groq(api_key=config.GROQ_API_KEY)
_gemini = genai.Client(api_key=config.GEMINI_API_KEY)

def _ask_groq(system, messages):
    response = _groq.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[{"role": "system", "content": system}] + messages,
        temperature=0.1,
        max_tokens=1000,
        reasoning_effort="low",
    )
    return response.choices[0].message.content
def _ask_gemini(system, messages):
    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]
    response = _gemini.models.generate_content(
        model=config.GEMINI_CHAT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.1,
            max_output_tokens=1000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return response.text
def write_reply(system, messages):
    """Try Groq first; if it fails for any reason, use Gemini."""
    try:
        return _ask_groq(system, messages)
    except Exception as error:
        log.warning("Groq failed (%s); falling back to Gemini", type(error).__name__)
    return _ask_gemini(system, messages)