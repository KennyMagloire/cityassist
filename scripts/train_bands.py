"""
CityAssist - trains the resolution-time band classifier.
Reads the cleaned service request data, compares a few models, saves the best.
No API calls. Takes about 5-10 minutes.
"""

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "processed" / "sr_hex_clean.csv.gz"
MODELS = ROOT / "models"

# Only what a resident's first message can give us.
CATEGORICAL = ["code", "code_group", "official_suburb", "day_of_week"]
NUMERIC = ["month", "is_weekend"]
TARGET = "resolution_band"

BAND_ORDER = ["Same day (under 1 day)", "1–3 days", "4–14 days", "Over 14 days"]


def load():
    cols = CATEGORICAL + NUMERIC + [TARGET, "department", "directorate"]
    df = pd.read_csv(DATA, low_memory=False, usecols=cols)
    print(f"{len(df):,} rows read")

    labelled = df[df[TARGET].notna()].copy()
    print(f"{len(labelled):,} rows have a band ({len(df) - len(labelled):,} have no completion time)\n")

    print(labelled[TARGET].value_counts(normalize=True).mul(100).round(1).to_string())
    print()
    return df, labelled


def build_lookup(df):
    """Most common department for each request type, and how often it is right."""
    counts = df.groupby(["code", "department"]).size().reset_index(name="n")
    top = counts.sort_values("n", ascending=False).drop_duplicates("code")

    lookup = {}
    for _, r in top.iterrows():
        total = counts.loc[counts["code"] == r["code"], "n"].sum()
        lookup[r["code"]] = {
            "department": r["department"],
            "agreement": round(r["n"] / total, 4),
            "ambiguous": bool(r["n"] < total),
        }

    hits = sum(counts.loc[(counts["code"] == c) & (counts["department"] == v["department"]), "n"].sum()
               for c, v in lookup.items())
    print(f"code -> department lookup: {len(lookup)} request types, "
          f"{hits / counts['n'].sum() * 100:.1f}% agreement with the recorded department")
    print(f"{sum(v['ambiguous'] for v in lookup.values())} request types map to more than one department\n")
    return lookup


def prepare(labelled):
    X = labelled[CATEGORICAL + NUMERIC].copy()
    for c in CATEGORICAL:
        X[c] = X[c].fillna("Not recorded").astype(str)

    enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    X[CATEGORICAL] = enc.fit_transform(X[CATEGORICAL])
    X[NUMERIC] = X[NUMERIC].apply(pd.to_numeric, errors="coerce").fillna(0)

    y = labelled[TARGET].astype(str)
    return X, y, enc


def evaluate(name, model, Xtr, ytr, Xte, yte, cat_idx=None):
    t0 = time.time()
    if isinstance(model, HistGradientBoostingClassifier):
        model.fit(Xtr, ytr)
    else:
        model.fit(Xtr, ytr)
    train_s = time.time() - t0

    acc = accuracy_score(yte, model.predict(Xte))

    tmp = MODELS / f"_tmp_{name}.joblib"
    joblib.dump(model, tmp, compress=3)
    size_mb = tmp.stat().st_size / 1_000_000
    tmp.unlink()

    print(f"  {name:22} accuracy {acc*100:5.1f}%   {size_mb:6.1f} MB   {train_s:5.1f}s")
    return {"name": name, "model": model, "accuracy": acc, "size_mb": size_mb}


def main():
    MODELS.mkdir(exist_ok=True)

    df, labelled = load()
    lookup = build_lookup(df)
    X, y, enc = prepare(labelled)

    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)
    print(f"train {len(Xtr):,}   test {len(Xte):,}\n")

    cat_idx = [X.columns.get_loc(c) for c in CATEGORICAL if X[c].nunique() <= 255]
    print("Model comparison:")

    results = [
        evaluate("baseline (most common)",
                 DummyClassifier(strategy="most_frequent"), Xtr, ytr, Xte, yte),
        evaluate("decision tree",
                 DecisionTreeClassifier(max_depth=15, min_samples_leaf=50,
                                        random_state=42), Xtr, ytr, Xte, yte),
        evaluate("random forest",
                 RandomForestClassifier(n_estimators=60, max_depth=18,
                                        min_samples_leaf=20, n_jobs=-1,
                                        random_state=42), Xtr, ytr, Xte, yte),
        evaluate("gradient boosting",
                 HistGradientBoostingClassifier(categorical_features=cat_idx,
                                                max_iter=200, random_state=42),
                 Xtr, ytr, Xte, yte),
    ]

    usable = [r for r in results if r["size_mb"] < 50 and r["name"] != "baseline (most common)"]
    best = max(usable, key=lambda r: r["accuracy"])
    baseline = results[0]["accuracy"]

    print(f"\nSelected: {best['name']}")
    print(f"  {best['accuracy']*100:.1f}% against a {baseline*100:.1f}% baseline "
          f"({(best['accuracy']-baseline)*100:+.1f} points)\n")

    pred = best["model"].predict(Xte)
    print(classification_report(yte, pred, labels=BAND_ORDER, zero_division=0))

    cm = confusion_matrix(yte, pred, labels=BAND_ORDER)
    print("Confusion matrix (rows actual, columns predicted):")
    print(pd.DataFrame(cm, index=BAND_ORDER, columns=BAND_ORDER).to_string())

    joblib.dump({"model": best["model"], "encoder": enc,
                 "categorical": CATEGORICAL, "numeric": NUMERIC,
                 "bands": BAND_ORDER}, MODELS / "band_classifier.joblib", compress=3)
    (MODELS / "department_lookup.json").write_text(
        json.dumps(lookup, ensure_ascii=False, indent=2), encoding="utf-8")

    (MODELS / "model_comparison.json").write_text(json.dumps(
        [{k: v for k, v in r.items() if k != "model"} for r in results],
        indent=2), encoding="utf-8")

    size = (MODELS / "band_classifier.joblib").stat().st_size / 1_000_000
    print(f"\nSaved band_classifier.joblib ({size:.1f} MB) and department_lookup.json")


if __name__ == "__main__":
    main()