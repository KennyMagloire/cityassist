import re

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
