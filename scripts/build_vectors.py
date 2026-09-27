"""
CityAssist - stage 2. Converts each chunk into 768 numbers and saves them.
Free tier allows 100 texts per minute, so this paces itself and resumes
if interrupted. Expect about 17 minutes.
"""

import json
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
CHUNKS_FILE = ROOT / "data" / "processed" / "chunks.json"
VEC_DIR = ROOT / "data" / "vectors"
PARTIAL = VEC_DIR / "partial.npy"

MODEL = "gemini-embedding-001"
DIMENSIONS = 768
BATCH_SIZE = 50
PAUSE = 35          # seconds between batches: 50 texts / 35s = 85 per minute
MAX_ATTEMPTS = 5


def embed_batch(client, texts):
    result = client.models.embed_content(
        model=MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            output_dimensionality=DIMENSIONS,
            task_type="RETRIEVAL_DOCUMENT",
        ),
    )
    return [e.values for e in result.embeddings]


def main():
    load_dotenv()
    client = genai.Client()
    VEC_DIR.mkdir(parents=True, exist_ok=True)

    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))

    # resume if a previous run was interrupted
    if PARTIAL.exists():
        done = np.load(PARTIAL)
        if len(done) > len(chunks):
            raise SystemExit("chunks.json has changed - delete partial.npy and start over")
        vectors = [row for row in done]
        print(f"Resuming: {len(vectors)} of {len(chunks)} already done\n")    # resume if a previous run was interrupted
    if PARTIAL.exists():
        done = np.load(PARTIAL)
        if len(done) > len(chunks):
            raise SystemExit("chunks.json has changed - delete partial.npy and start over")
        vectors = [row for row in done]
        print(f"Resuming: {len(vectors)} of {len(chunks)} already done\n")
    else:
        vectors = []
        print(f"{len(chunks)} chunks to embed - roughly 17 minutes\n")

    while len(vectors) < len(chunks):
        start = len(vectors)
        texts = [c["text"] for c in chunks[start:start + BATCH_SIZE]]

        for attempt in range(MAX_ATTEMPTS):
            try:
                vectors.extend(embed_batch(client, texts))
                break
            except Exception as exc:
                if attempt == MAX_ATTEMPTS - 1:
                    np.save(PARTIAL, np.array(vectors, dtype=np.float32))
                    raise
                wait = 60 if "429" in str(exc) else 10
                print(f"  rate limited at {start}, waiting {wait}s")
                time.sleep(wait)

        np.save(PARTIAL, np.array(vectors, dtype=np.float32))
        print(f"  {len(vectors)}/{len(chunks)}")

        if len(vectors) < len(chunks):
            time.sleep(PAUSE)

    arr = np.array(vectors, dtype=np.float32)
    arr = arr / np.linalg.norm(arr, axis=1, keepdims=True)
    np.save(VEC_DIR / "vectors.npy", arr)

    meta = [{k: c[k] for k in ("chunk_id", "document", "page", "text")} for c in chunks]
    (VEC_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    PARTIAL.unlink(missing_ok=True)

    size_mb = (VEC_DIR / "vectors.npy").stat().st_size / 1_000_000
    print(f"\nSaved {arr.shape[0]} vectors of {arr.shape[1]} numbers ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()