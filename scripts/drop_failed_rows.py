"""Remove evaluation rows where Groq and Gemini were both out of quota, so
run_evaluation.py tests those messages again on its next run."""
import csv
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "tests" / "evaluation_results.csv"
FAILED = "Sorry, I can't answer right now"

with open(RESULTS, encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    columns = reader.fieldnames
    rows = list(reader)

kept = [row for row in rows if not any(FAILED in (value or "") for value in row.values())]

with open(RESULTS, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    writer.writerows(kept)

print(f"Kept {len(kept)} rows, removed {len(rows) - len(kept)} failed rows.")