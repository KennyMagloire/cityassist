"""Data quality checks on the cleaned service-request data, and the model's accuracy on it.

The cleaned file is too large for GitHub, so these tests run only on a computer that has
data/processed/sr_hex_clean.csv.gz. Elsewhere they are skipped, not failed.
"""
import os
from pathlib import Path

import joblib
import pandas as pd
import pytest
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from app import config

DATA = Path(os.environ.get("CITYASSIST_CLEAN_DATA",
                           Path(__file__).resolve().parent.parent / "data" / "processed" / "sr_hex_clean.csv.gz"))
pytestmark = pytest.mark.skipif(not DATA.exists(), reason="cleaned dataset not on this computer")

COLUMNS = ["code", "code_group", "official_suburb", "day_of_week", "month", "is_weekend", "resolution_band"]
BANDS = ["Same day (under 1 day)", "1–3 days", "4–14 days", "Over 14 days"]


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(DATA, usecols=COLUMNS, low_memory=False)


@pytest.fixture(scope="module")
def labelled(df):
    return df[df["resolution_band"].notna()].copy()


def test_impossible_records_were_removed(df):
    assert len(df) < 941_634, "the 5,483 records completed before creation should be gone"


def test_number_of_requests_with_a_usable_time(labelled):
    assert len(labelled) == 912_253


def test_only_the_four_bands_are_used(labelled):
    assert set(labelled["resolution_band"]) == set(BANDS)


def test_band_shares_match_part_c(labelled):
    shares = labelled["resolution_band"].value_counts(normalize=True) * 100
    expected = {"Same day (under 1 day)": 35.6, "1–3 days": 20.6, "4–14 days": 20.1, "Over 14 days": 23.7}
    for band, share in expected.items():
        assert abs(shares[band] - share) < 0.2, band


def test_suburb_names_have_no_stray_spaces(df):
    names = df["official_suburb"].dropna().astype(str)
    assert (names == names.str.strip()).all()
    assert not names.str.contains("  ").any()


def test_months_and_days_are_valid(df):
    assert df["month"].between(1, 12).all()
    days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
    assert set(df["day_of_week"].dropna()) <= days


def test_model_accuracy_on_the_held_out_test_set(labelled):
    """Rebuild the exact 80/20 split from training and check the saved model's score."""
    bundle = joblib.load(config.MODEL_FILE)
    cat, num = bundle["categorical"], bundle["numeric"]
    X = labelled[cat + num].copy()
    for c in cat:
        X[c] = X[c].fillna("Not recorded").astype(str)
    X[cat] = bundle["encoder"].transform(X[cat])
    X[num] = X[num].apply(pd.to_numeric, errors="coerce").fillna(0)
    y = labelled["resolution_band"].astype(str)
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    assert len(X_test) == 182_451
    accuracy = accuracy_score(y_test, bundle["model"].predict(X_test))
    baseline = (y_test == y_test.mode()[0]).mean()
    assert accuracy >= 0.58, f"accuracy dropped to {accuracy:.3f}"
    assert accuracy - baseline >= 0.20, "the model must clearly beat always guessing the commonest band"
