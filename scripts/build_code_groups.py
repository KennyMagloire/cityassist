"""Save the code group of each request type, so the app can build the model's inputs."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "processed" / "sr_hex_clean.csv.gz"
OUT = ROOT / "models" / "code_groups.json"

df = pd.read_csv(DATA, usecols=["code", "code_group"])

groups = df.groupby("code")["code_group"].agg(lambda s: s.mode().iloc[0])
in_several = (df.groupby("code")["code_group"].nunique() > 1).sum()

print(len(groups), "request types")
print(in_several, "request types appear under more than one group")

OUT.write_text(json.dumps(groups.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
print("saved", OUT)