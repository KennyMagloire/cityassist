import os
from pathlib import Path
from dotenv import load_dotenv


# Section 1: find the project folder and load the .env file
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Section 2: where the files are
VECTORS_FILE = ROOT / "data" / "vectors" / "vectors.npy"
META_FILE = ROOT / "data" / "vectors" / "meta.json"
MODEL_FILE = ROOT / "models" / "band_classifier.joblib"
LOOKUP_FILE = ROOT / "models" / "department_lookup.json"
PROMPT_FILE = ROOT / "prompts" / "system_prompt.txt"
NOTICE_FILE = ROOT / "prompts" / "recording_notice.txt"
DB_FILE = ROOT / "data" / "conversations.db"

# Section 3: the models and limits
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMENSIONS = 768
GROQ_MODEL = "openai/gpt-oss-20b"
GEMINI_CHAT_MODEL = "gemini-2.5-flash"

TOP_K = 5
MIN_SCORE = 0.60
MAX_MESSAGE_CHARS = 1000

# Section 4: the API keys, checked when the app starts
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GEMINI_API_KEY:
    raise SystemExit("GEMINI_API_KEY is missing from .env")
if not GROQ_API_KEY:
    raise SystemExit("GROQ_API_KEY is missing from .env")