"""Find the passages most relevant to a question."""
import json

import numpy as np
from google import genai
from google.genai import types

from app import config
from app.noise import noise_reason

_client = genai.Client(api_key=config.GEMINI_API_KEY)
_vectors = np.load(config.VECTORS_FILE)
_meta = json.loads(config.META_FILE.read_text(encoding="utf-8"))
_keep = np.array([noise_reason(m["text"]) is None for m in _meta])

def embed_question(question):
    """Convert a question into a normalised 768-number vector."""
    result = _client.models.embed_content(
        model=config.EMBED_MODEL,
        contents=question,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=config.EMBED_DIMENSIONS,
        ),
    )
    q = np.array(result.embeddings[0].values, dtype=np.float32)
    return q / np.linalg.norm(q)

def search(question, top_k=config.TOP_K):
    """Return up to top_k passages that score above the threshold, best first."""
    q = embed_question(question)
    scores = _vectors @ q
    scores[~_keep] = -1.0
    best = np.argsort(scores)[::-1][:top_k]

    results = []
    for i in best:
        if scores[i] < config.MIN_SCORE:
            break
        m = _meta[i]
        results.append({
            "id": m["chunk_id"],
            "document": m["document"],
            "page": m["page"],
            "text": m["text"],
            "score": float(scores[i]),
        })
    return results