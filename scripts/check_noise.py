"""Find chunks that are layout noise rather than content. Run to check the rules."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
meta = json.loads((ROOT / "data" / "vectors" / "meta.json").read_text(encoding="utf-8"))


def noise_reason(text):
    """Return why a chunk is noise, or None if it is real content."""
    if text.count(".") / max(len(text), 1) > 0.25:
        return "contents page"

    cleaned = re.sub(r"\.{4,}", " ", text)
    cleaned = re.sub(r"[|\s]+", " ", cleaned).strip()
    words = cleaned.split()

    real_words = [w for w in words if len(w) >= 3 and w.isalpha()]
    if len(real_words) >= 25:
        return None                      # enough real text to be worth keeping

    if len(cleaned) < 80:
        return "too little text"
    single = sum(len(w) == 1 for w in words) / max(len(words), 1)
    if single > 0.4:
        return "garbled"
    return None


flagged = [(noise_reason(m["text"]), m) for m in meta]
flagged = [(r, m) for r, m in flagged if r]

print(f"{len(flagged)} of {len(meta)} chunks flagged as noise\n")
for reason in ("contents page", "too little text", "garbled"):
    group = [m for r, m in flagged if r == reason]
    print(f"{reason}: {len(group)}")
    for m in group[:3]:
        print(f"    {m['document']} p.{m['page']}: {m['text'][:90]!r}")
    print()

tariff = [m for m in meta if "R5.91" in m["text"]]
print("tariff chunk with R5.91 kept:", all(noise_reason(m["text"]) is None for m in tariff))

print("\nFlagged per document:")
from collections import Counter
total = Counter(m["document"] for m in meta)
hit = Counter(m["document"] for _, m in flagged)
for doc, n in hit.most_common():
    print(f"  {n:3d} of {total[doc]:3d}  {doc}")