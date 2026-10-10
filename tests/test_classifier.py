"""The department lookup and the repair-time model."""
from datetime import datetime

from app import config
from app.classifier import department_for, predict_band

BANDS = {"Same day (under 1 day)", "1–3 days", "4–14 days", "Over 14 days"}


def test_known_request_type_gets_its_department():
    assert department_for("Pothole&Defect Road Foot Bic Way/Kerbs") == "Roads Infrastructure Management"
    assert department_for("Sewer: Blocked/Overflow") == "Distribution Services"


def test_unknown_request_type_gets_no_department():
    assert department_for("Not a real request type") is None


def test_model_returns_one_of_the_four_bands():
    when = datetime(2026, 10, 5, 9, 0, tzinfo=config.CAPE_TOWN_TIME)
    band = predict_band("Sewer: Blocked/Overflow", "GUGULETHU", when)
    assert band in BANDS


def test_model_works_without_a_suburb():
    when = datetime(2026, 10, 10, 9, 0, tzinfo=config.CAPE_TOWN_TIME)   # a Saturday
    assert predict_band("No Power", None, when) in BANDS
