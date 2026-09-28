"""Quick check that search works end to end. Costs one embedding per run."""
import json
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
VEC_DIR = ROOT / "data" / "vectors"

load_dotenv(ROOT / ".env")
client = genai.Client()                       # stored, so it stays alive

vectors = np.load(VEC_DIR / "vectors.npy")
meta = json.loads((VEC_DIR / "meta.json").read_text(encoding="utf-8"))

question = " ".join(sys.argv[1:]) or "who has to fix a leak on my side of the water meter?"

result = client.models.embed_content(
    model="gemini-embedding-001",
    contents=question,
    config=types.EmbedContentConfig(output_dimensionality=768,
                                    task_type="RETRIEVAL_QUERY"),
)
q = np.array(result.embeddings[0].values, dtype=np.float32)
q /= np.linalg.norm(q)

scores = vectors @ q                          # the whole search, one line
print(f"\nQ: {question}\n")
for i in scores.argsort()[::-1][:3]:
    print(f"{float(scores[i]):.3f}  {meta[i]['document']}  p.{meta[i]['page']}")
    print("      " + meta[i]["text"][:200].replace("\n", " ") + " ...\n")