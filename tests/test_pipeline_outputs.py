"""Checks on the files the two pipelines produced, which the chatbot loads at start-up.

If any of these fail, a pipeline step went wrong or a file was replaced by mistake.
"""
import csv
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app import config
from app.noise import noise_reason

ROOT = Path(__file__).resolve().parent.parent
VECTORS = np.load(config.VECTORS_FILE)
META = json.loads(config.META_FILE.read_text(encoding="utf-8"))
BUNDLE = joblib.load(config.MODEL_FILE)
LOOKUP = json.loads(config.LOOKUP_FILE.read_text(encoding="utf-8"))
GROUPS = json.loads(config.GROUPS_FILE.read_text(encoding="utf-8"))


# ---------- AI pipeline: passages and embeddings ----------

def test_one_embedding_per_passage():
    assert VECTORS.shape == (len(META), config.EMBED_DIMENSIONS)
    assert len(META) == 1476


def test_embeddings_are_clean_and_normalised():
    assert not np.isnan(VECTORS).any()
    norms = np.linalg.norm(VECTORS, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3), "cosine similarity relies on unit-length vectors"


def test_every_passage_has_a_source_page_and_text():
    ids = [m["chunk_id"] for m in META]
    assert len(ids) == len(set(ids)), "passage IDs must be unique"
    for m in META:
        assert m["document"] and m["text"].strip()
        assert int(m["page"]) >= 1


def test_every_document_is_listed_in_sources_csv():
    with open(config.SOURCES_FILE, encoding="utf-8-sig", newline="") as f:
        listed = {Path(r["filename"]).stem for r in csv.DictReader(f)}
    used = {m["document"] for m in META}
    assert used <= listed, f"documents without a source entry: {used - listed}"
    assert len(used) == 23        # 17 City PDFs + 6 guides


def test_noise_filter_removes_a_small_share_only():
    flagged = sum(noise_reason(m["text"]) is not None for m in META)
    assert flagged == 89, "noise filter result changed; check no real content is being dropped"


def test_request_type_vectors_match_their_names():
    vectors = np.load(config.TYPE_VECTORS_FILE)
    names = json.loads(config.TYPE_NAMES_FILE.read_text(encoding="utf-8"))
    assert vectors.shape == (len(names), config.EMBED_DIMENSIONS)
    assert set(names) == set(LOOKUP), "every type the AI can choose must have a department"


# ---------- data science pipeline: lookup and model ----------

def test_department_lookup_covers_455_types():
    assert len(LOOKUP) == 455
    for code, entry in LOOKUP.items():
        assert entry["department"], code
        assert 0 < entry["agreement"] <= 1, code
        assert code in GROUPS, f"{code} has no code group, so the model can't use it"


def test_model_uses_only_what_is_known_when_a_resident_writes():
    features = BUNDLE["categorical"] + BUNDLE["numeric"]
    assert features == ["code", "code_group", "official_suburb", "day_of_week", "month", "is_weekend"]
    assert "department" not in features and "directorate" not in features, "leakage"


def test_model_predicts_the_four_bands_in_order():
    assert BUNDLE["bands"] == ["Same day (under 1 day)", "1–3 days", "4–14 days", "Over 14 days"]
    assert set(BUNDLE["model"].classes_) == set(BUNDLE["bands"])


def test_model_knows_the_official_suburbs():
    suburbs = BUNDLE["encoder"].categories_[BUNDLE["categorical"].index("official_suburb")]
    assert len(suburbs) >= 775
    assert "Not recorded" in suburbs


def test_model_gives_different_answers_for_different_problems():
    """A model that always says the same band has learned nothing beyond the baseline."""
    rows = pd.DataFrame([{
        "code": code, "code_group": GROUPS[code], "official_suburb": "Not recorded",
        "day_of_week": "Tuesday", "month": 5, "is_weekend": 0,
    } for code in list(LOOKUP)[:40]])
    X = rows[BUNDLE["categorical"] + BUNDLE["numeric"]].copy()
    X[BUNDLE["categorical"]] = BUNDLE["encoder"].transform(X[BUNDLE["categorical"]])
    assert len(set(BUNDLE["model"].predict(X))) > 1
