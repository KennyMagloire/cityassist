# CityAssist

CityAssist is a chat assistant for City of Cape Town residents. It does two things:

1. **Answers questions** about City services (water, electricity, refuse, roads, tariffs and by-laws) from 17 official City documents and 6 reporting guides, and shows the document and page it used.
2. **Helps prepare a service request.** When a resident describes a problem, it works out the request type, asks for the location if it is missing, finds the department that handles it, estimates how long similar requests usually took, and saves a **draft**.

> CityAssist is a student prototype built for the CPUT AIE580S / DSE580S group assignment (2026). It is **not** an official City of Cape Town service. Nothing is sent to the City: residents still log requests officially on 0860 103 089 or at www.capetown.gov.za/servicerequests.

Live demo: https://cityassist-8sax.onrender.com (free hosting, so the first visit after a quiet period takes about a minute to wake up).

**Group:** Liam (Kenny Magloire Ango), Keo, Ziyanda.

---

## How it works

```
Resident (web page or WhatsApp)
        |
   FastAPI app  ── rate limit, personal details removed, recording notice
        |
   Understand the message (Groq, openai/gpt-oss-20b)
        |
   ├─ Question ─> search the City documents (Gemini embeddings, cosine similarity)
   |              ─> write a short answer citing [1], [2]... (Groq; Gemini 2.5 Flash as backup)
   |              ─> check citations, add "Sources" with document titles and pages
   |
   └─ Report  ─> match request type (455 City types) and suburb (775 official names)
                  ─> department lookup + resolution-time model (2020 City data)
                  ─> save draft in SQLite, show it to the resident
```

| Part | What it uses |
|---|---|
| Web chat | Gradio page mounted at `/chat` inside FastAPI |
| WhatsApp | Meta WhatsApp Cloud API webhook at `/whatsapp` (built and tested; see *Status* below) |
| Document search | `gemini-embedding-001`, 768 numbers per piece, 1,476 pieces, top 5, minimum score 0.60 |
| Replies | Groq `openai/gpt-oss-20b` (temperature 0.1); Gemini 2.5 Flash if Groq fails |
| Resolution time | scikit-learn HistGradientBoosting trained on 912,253 labelled 2020 requests (58.7% accuracy vs 35.6% baseline; 83.2% within one band) |
| Storage | SQLite (`data/conversations.db`): messages and drafts |
| Hosting | Render free tier (Frankfurt), Python 3.11 |

### Safeguards

- Every conversation starts with a **recording notice**.
- **Personal details are removed** before anything is stored or sent to an AI service: SA ID numbers, email addresses, phone numbers and long account numbers.
- **Emergency line:** messages that mention fire, flooding, live wires and similar get the City emergency number first.
- **Grounded answers only:** if no document piece is close enough, the assistant says it could not find the answer instead of guessing. A reply that cites a passage it was not given is rejected.
- **No invented suburbs:** a suburb is only used if the resident actually wrote it (small typos such as "Claremon" are allowed).
- **Rate limit:** 6 messages a minute per person, on both channels.
- **WhatsApp:** every incoming request is checked with Meta's signature (HMAC-SHA256), repeated deliveries are ignored, and phone numbers are stored only as a one-way hash.
- **Drafts only:** the assistant never submits anything to the City. A person stays in control.

---

## Running it on your own computer

You need **Python 3.11**, **Git**, and two free API keys:
- a **Gemini** key from https://aistudio.google.com/apikey
- a **Groq** key from https://console.groq.com/keys

### 1. Get the code

```bash
git clone https://github.com/KennyMagloire/cityassist.git
cd cityassist
```

### 2. Create a virtual environment and install

Windows (Git Bash):
```bash
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
```

macOS / Linux:
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Add your keys

Create a file called `.env` in the project folder:

```
GEMINI_API_KEY=your-gemini-key
GROQ_API_KEY=your-groq-key
```

The WhatsApp keys are optional. Without them the WhatsApp route is switched off and the web chat works normally:

```
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_ID=...
WHATSAPP_APP_SECRET=...
WHATSAPP_VERIFY_TOKEN=...
```

`.env` is listed in `.gitignore`. Never commit it.

### 4. Start the app

```bash
python -m app.main
```

Open http://127.0.0.1:8000. It opens the chat page. A health check is at http://127.0.0.1:8000/health.

Things to try:
- `How do I report a water leak?` (answer with sources)
- `There is a big pothole in the road`, then `Main Road, Claremont` (draft request)
- `Who won the rugby last night?` (politely declined)

An internet connection is needed: the document search and the replies use the Gemini and Groq services.

---

## Testing

`tests/test_utterances.csv` holds 160 test messages written by the group: reports with and without a location, questions, out-of-scope questions, greetings, misspellings, Afrikaans and isiXhosa. Each row has the expected intent, request type, department and behaviour.

```bash
python scripts/run_evaluation.py
```

Every message goes through the real assistant, and the reply, what it understood and the time taken are saved in `tests/evaluation_results.csv`. The script pauses 15 seconds between messages to stay inside the free limits, so a full run takes about 45 minutes. If it stops, run it again: it continues where it left off.

If the free daily quota runs out during a run, the affected rows get the fallback reply. Remove them and run again later:

```bash
python scripts/drop_failed_rows.py
python scripts/run_evaluation.py
```

Results from the run after our fixes (160 messages):

| Measure | Result |
|---|---|
| Intent (question or report) | 145/160 (90.6%) |
| Right department | 97/120 (80.8%) |
| Exact request type | 71/120 (59.2%) |
| Right behaviour (draft, ask for location, answer, decline) | 130/160 (81.3%) |
| Median reply time | 1.2 s |

`tests/evaluation_results_before_fixes.csv` keeps the first run for comparison.

To look at saved conversations: `python scripts/show_messages.py`, or open `data/conversations.db` with DB Browser for SQLite.

---

## Rebuilding the data files

The files the app needs are already in the repository (`data/vectors/`, `models/`), so this is only needed if the documents or the training data change.

| Step | Command | What it does |
|---|---|---|
| 1 | `python scripts/extract_chunks.py` | Splits the PDFs in `docs/pdfs/` and the guides in `docs/guides/` into pieces |
| 2 | `python scripts/build_vectors.py` | Embeds every piece (paces itself; resumes if the daily limit is reached) |
| 2b | `python scripts/add_vectors.py` | Re-embeds only new or changed pieces |
| 3 | `python scripts/check_noise.py` | Shows which pieces are ignored as layout noise (contents pages, empty tables) |
| 4 | `python scripts/build_type_vectors.py` | Embeds the 455 City request-type names |
| 5 | `python scripts/build_code_groups.py` | Saves the group of each request type |
| 6 | `python scripts/train_bands.py` | Trains the resolution-time model |

Step 6 needs the cleaned City service-request data at `data/processed/sr_hex_clean.csv.gz`. It is not in the repository because of its size: download the City's open service-request data and clean it as described in Part C of the report.

Every document is listed in `docs/sources.csv` with its title, source address and date.

---

## Deploying on Render

1. New **Web Service** from this repository.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add `GEMINI_API_KEY` and `GROQ_API_KEY` (and the WhatsApp keys, if used) under **Environment**.

On the free tier the service sleeps after 15 minutes without visitors, and its disk is reset, so saved conversations are lost on restart.

---

## Project layout

```
app/        the application: main.py (routes), assistant.py (decides what to do),
            search.py, llm.py, report.py, classifier.py, suburbs.py, redact.py,
            noise.py, database.py, web_chat.py, whatsapp.py, config.py
docs/       pdfs/ (17 City documents), guides/ (6 reporting guides), sources.csv
prompts/    system_prompt.txt, recording_notice.txt
data/       vectors/ (document embeddings); conversations.db is created at run time
models/     resolution-time model, department lookup, request-type vectors
scripts/    building the data, training, evaluation, checking
tests/      test messages and evaluation results
```

---

## Status and known limitations

- **WhatsApp is built and tested, but Meta blocks delivery** (error 131031, business account locked) until the business is verified. A student group cannot do this; the City would use its own verified account.
- **Data use by the AI services:** messages are cleaned of personal details first, but Gemini's free tier may use content to improve Google's products. A real deployment would use paid tiers or a locally hosted model.
- **Free-tier limits:** the daily quota of both services can run out under heavy use. The assistant then gives a fallback message with the City's phone number instead of failing.
- **Suburb names:** only the City's 775 official names are recognised, so common names like Kuils River or Goodwood are not always matched.
- **Citation check:** it confirms that a cited passage exists, not that the passage supports the claim. In testing, one out-of-scope question (renewing a vehicle licence disc) got a wrong answer with a citation.
- **Resolution-time estimates** come from 2020 data and are an indication, not a promise.
- Conversations are lost when the free Render service restarts; a real deployment needs a hosted database.
