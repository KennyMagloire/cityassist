"""Department and expected resolution-time band for a reported problem."""
import json
from datetime import datetime

import joblib
import pandas as pd

from app import config

_bundle = joblib.load(config.MODEL_FILE)
_model = _bundle["model"]
_encoder = _bundle["encoder"]
_categorical = _bundle["categorical"]
_numeric = _bundle["numeric"]

_departments = json.loads(config.LOOKUP_FILE.read_text(encoding="utf-8"))
_groups = json.loads(config.GROUPS_FILE.read_text(encoding="utf-8"))

VALID_TYPES = sorted(_departments)
SUBURBS = sorted(s for s in _encoder.categories_[_categorical.index("official_suburb")]
                 if s != "Not recorded")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def department_for(code):
    """The department that usually handles this request type, or None if unknown."""
    entry = _departments.get(code)
    return entry["department"] if entry else None

def predict_band(code, suburb, when=None):
    """Predict the resolution-time band, building the inputs exactly as in training."""
    when = when or datetime.now(config.CAPE_TOWN_TIME)
    row = {
        "code": code,
        "code_group": _groups.get(code, "Not recorded"),
        "official_suburb": suburb or "Not recorded",
        "day_of_week": DAYS[when.weekday()],
        "month": when.month,
        "is_weekend": int(when.weekday() >= 5),
    }
    X = pd.DataFrame([row])[_categorical + _numeric]
    X[_categorical] = _encoder.transform(X[_categorical])
    return _model.predict(X)[0]