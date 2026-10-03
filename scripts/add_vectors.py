"""Embed only the chunks that are not in the vector file yet, and add them to it."""
import json
import sys
from pathlib import Path

import numpy as np
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import config

CHUNKS_FILE = ROOT / "data" / "processed" / "chunks.json"
MAX_NEW = 50


def load():
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    meta = json.loads(config.META_FILE.read_text(encoding="utf-8"))
    vectors = np.load(config.VECTORS_FILE)
    return chunks, meta, vectors


def drop_changed(chunks, meta, vectors):
    """Remove saved pieces whose text changed or disappeared, so they get embedded again."""
    if len(meta) != len(vectors):
        raise SystemExit(f"meta.json has {len(meta)} rows but vectors.npy has {len(vectors)}.")
    text_by_id = {c["chunk_id"]: c["text"] for c in chunks}
    keep = [i for i, m in enumerate(meta) if text_by_id.get(m["chunk_id"]) == m["text"]]
    print(f"Removed {len(meta) - len(keep)} changed pieces.")
    return [meta[i] for i in keep], vectors[keep]


def embed(texts):
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    result = client.models.embed_content(
        model=config.EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=config.EMBED_DIMENSIONS,
        ),
    )
    new = np.array([e.values for e in result.embeddings], dtype=np.float32)
    return new / np.linalg.norm(new, axis=1, keepdims=True)


def main():
    chunks, meta, vectors = load()
    meta, vectors = drop_changed(chunks, meta, vectors)

    known = {m["chunk_id"] for m in meta}
    new_chunks = [c for c in chunks if c["chunk_id"] not in known]
    if not new_chunks:
        print("Nothing new to embed.")
        return
    if len(new_chunks) > MAX_NEW:
        raise SystemExit(f"{len(new_chunks)} new pieces: too many for one request. "
                         "Use build_vectors.py instead.")

    new_vectors = embed([c["text"] for c in new_chunks])
    vectors = np.vstack([vectors, new_vectors])
    meta += [{"chunk_id": c["chunk_id"], "document": c["document"],
              "page": c["page"], "text": c["text"]} for c in new_chunks]

    np.save(config.VECTORS_FILE, vectors)
    config.META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Added {len(new_chunks)} pieces. Now {len(meta)} pieces, vectors {vectors.shape}.")


if __name__ == "__main__":
    main()