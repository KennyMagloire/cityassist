"""Embed the 455 request-type names once, so the app can find likely types for a message."""
import json
import sys
import time
from pathlib import Path

import numpy as np
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import config
from app.classifier import VALID_TYPES

BATCH_SIZE = 50
PAUSE = 35


def describe(code, groups):
    """The type name plus its group gives the embedding a little more meaning."""
    return f"{code} ({groups.get(code, '')})"


def main():
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    groups = json.loads(config.GROUPS_FILE.read_text(encoding="utf-8"))
    texts = [describe(code, groups) for code in VALID_TYPES]

    vectors = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        result = client.models.embed_content(
            model=config.EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=config.EMBED_DIMENSIONS,
            ),
        )
        vectors.extend(e.values for e in result.embeddings)
        print(f"{len(vectors)} of {len(texts)}")
        if start + BATCH_SIZE < len(texts):
            time.sleep(PAUSE)

    matrix = np.array(vectors, dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    np.save(config.TYPE_VECTORS_FILE, matrix)
    config.TYPE_NAMES_FILE.write_text(json.dumps(VALID_TYPES, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    print("saved", matrix.shape)


if __name__ == "__main__":
    main()