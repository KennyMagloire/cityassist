"""Run every test message through the assistant, save the replies, and score them."""
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.assistant import ASK_LOCATION, ASK_PROBLEM, FALLBACK, NOT_FOUND, answer_with_details
from app.suburbs import match_suburb

TESTS = ROOT / "tests" / "test_utterances.csv"
RESULTS = ROOT / "tests" / "evaluation_results.csv"
PAUSE = 15  # seconds between messages, to stay inside Groq's free limits


def behaviour_of(reply):
    """Turn a reply into one of the expected_behaviour labels."""
    if "draft request number" in reply:
        return "draft"
    if reply == ASK_LOCATION or reply.startswith("I couldn't find \""):
        return "ask_location"
    if reply == ASK_PROBLEM:
        return "ask_problem"
    if reply == NOT_FOUND or "couldn't find that" in reply:
        return "not_covered"
    if reply == FALLBACK:
        return "fallback"
    if "Sources:" in reply or "Based on:" in reply:
        return "answer_with_sources"
    return "other"


def already_done():
    if not RESULTS.exists():
        return set()
    with open(RESULTS, encoding="utf-8", newline="") as f:
        return {row["utterance_id"] for row in csv.DictReader(f)}


def main():
    with open(TESTS, encoding="utf-8-sig", newline="") as f:
        tests = list(csv.DictReader(f))
    done = already_done()
    fields = ["utterance_id", "utterance", "expected_intent", "got_intent", "expected_code",
              "got_code", "expected_behaviour", "got_behaviour", "matched_suburb", "seconds",
              "reply", "correct_manual"]
    new_file = not RESULTS.exists()
    with open(RESULTS, "a", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        if new_file:
            writer.writeheader()
        for t in tests:
            if t["utterance_id"] in done:
                continue
            start = time.time()
            result = answer_with_details(t["utterance"], [], "eval-" + t["utterance_id"], "eval")
            if isinstance(result, str):
                result = {"reply": result, "intent": "", "request_type": None, "suburb": ""}
            writer.writerow({
                "utterance_id": t["utterance_id"], "utterance": t["utterance"],
                "expected_intent": t["expected_intent"], "got_intent": result["intent"],
                "expected_code": t["expected_code"], "got_code": result["request_type"] or "",
                "expected_behaviour": t["expected_behaviour"],
                "got_behaviour": behaviour_of(result["reply"]),
                "matched_suburb": match_suburb(result["suburb"]) or "",
                "seconds": round(time.time() - start, 1), "reply": result["reply"],
                "correct_manual": "",
            })
            out.flush()
            print(t["utterance_id"], behaviour_of(result["reply"]))
            time.sleep(PAUSE)


if __name__ == "__main__":
    main()