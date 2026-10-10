# CityAssist
  ![Unit tests](https://github.com/KennyMagloire/cityassist/actions/workflows/tests.yml/badge.svg)

CityAssist is a chat assistant for City of Cape Town residents. It does two jobs:

1. **Answers questions** about City services (water, electricity, refuse, roads, tariffs and by-laws) using 17 official City documents and 6 short reporting guides, and shows the document and page each answer came from.
2. **Helps prepare a service request.** When a resident describes a problem ("there's sewage in my yard"), it works out the type of problem, asks where it is if that is missing, finds the department that handles it, estimates how long similar requests usually took, and saves a **draft**.

> CityAssist is a student prototype built for the CPUT AIE580S / DSE580S group assignment (2026). It is **not** an official City of Cape Town service and nothing is sent to the City. Residents still log requests officially on **0860 103 089** or at **www.capetown.gov.za/servicerequests**.

| | |
|---|---|
| **Live chatbot** | https://cityassist-8sax.onrender.com (free hosting: the first visit after 15 quiet minutes takes about a minute) |
| **Health check** | https://cityassist-8sax.onrender.com/health |
| **System prompt** | [`prompts/system_prompt.txt`](prompts/system_prompt.txt) |
| **Dataset** | City of Cape Town service requests, 2020: https://github.com/cityofcapetown/ds_code_challenge |
| **Group** | Kenny, Keo, Ziyanda |

---

## Contents

1. [How it works](#how-it-works)
2. [Technology stack and why we chose it](#technology-stack-and-why-we-chose-it)
3. [Project structure](#project-structure)
4. [Security and privacy](#security-and-privacy)
5. [Running it on your own computer](#running-it-on-your-own-computer)
6. [Testing and results](#testing-and-results)
7. [Rebuilding the data files](#rebuilding-the-data-files)
8. [Deploying on Render](#deploying-on-render)
9. [Data sources](#data-sources)
10. [Limitations and future work](#limitations-and-future-work)
11. [Credits and licence](#credits-and-licence)

---

## How it works

### The two main pieces: FastAPI and Gradio

The application is **one Python program** with two parts that do different jobs:

- **FastAPI is the web server**, the "front door". It receives every request that arrives from the internet and decides where it goes:
  - `/chat` → the chat page
  - `/whatsapp` → messages forwarded by Meta from WhatsApp
  - `/health` → a quick "I'm alive" check for the hosting service
  - `/` → redirects to `/chat`
- **Gradio is only the chat page**: the text box, the Send button and the conversation bubbles. It is placed *inside* FastAPI at `/chat` (`gr.mount_gradio_app`).

Why both? Gradio on its own can show a chat page, but it cannot give WhatsApp an address to deliver messages to. FastAPI can. Putting the Gradio page inside FastAPI means **both channels use the same assistant code**, so a question gets the same answer on the web and on WhatsApp.

```
 Resident on the web page          Resident on WhatsApp
          │                                 │ (Meta forwards the message)
          ▼                                 ▼
 ┌──────────────────────── FastAPI (one program on Render) ────────────────────────┐
 │   /chat  (Gradio page)                 /whatsapp  (signature + duplicate check)   │
 │          └──────────── rate limit: 6 messages a minute per person ───────────┘    │
 │                                       ▼                                           │
 │                           assistant.py  (the decision maker)                      │
 │        remove personal details → greeting? → question or report?                  │
 │              │                                         │                          │
 │        QUESTION                                    REPORT                         │
 │   search.py: find the 5 closest passages     report.py: request type, suburb      │
 │   llm.py: Groq writes a short answer         classifier.py: department + time     │
 │   check the citations, add the sources       database.py: save the draft          │
 │                                       ▼                                           │
 │              emergency number first if urgent · save the exchange · reply         │
 └───────────────────────────────────────────────────────────────────────────────────┘
          │                         │                              │
   Gemini (embeddings,       Groq (understands and          SQLite file
   backup writer)            writes replies)                (messages, drafts)
```

### What happens to one message

1. **Rate limit.** More than 6 messages in a minute from the same person get "please wait a minute".
2. **Personal details removed** (ID numbers, phone numbers, emails, account numbers).
3. **Greeting or thanks?** A short friendly reply, with no AI call at all.
4. **Turn the message into numbers** (an *embedding*: 768 numbers that capture its meaning) with Gemini. Done once per message and reused.
5. **Question or report?** Groq reads the message (and the last few messages) and answers in a fixed JSON format: the intent, the request type (chosen only from the 8 closest of the City's 455 types), the suburb and the street.
6. **If it is a question:**
   - compare the message's numbers with the numbers of all 1,476 document passages and keep the 5 closest, but only those that score at least 0.60;
   - if none is close enough, say "I couldn't find that" and give the official contact details (no AI call, so nothing can be invented);
   - otherwise Groq writes a short answer from those passages only, citing them as [1], [2]...;
   - the code checks that every citation points to a passage it was actually given, then adds the document titles and page numbers.
7. **If it is a report:**
   - no clear request type → ask what the problem is;
   - no suburb, or a suburb that is not one of the City's 775 official names → ask where it is;
   - otherwise look up the department, predict the resolution-time band with the trained model, save a draft and show it.
8. **Emergency words** (fire, flood, live wire, sparking...) → the City's emergency number is put first.
9. **Save** the exchange (with personal details removed) and reply.

---

## Technology stack and why we chose it

Two rules shaped every choice: it had to be **free** (the group has no budget), and it had to run at a **public address** that the lecturer can open. We also built two prototypes and compared them on the same documents.

| Layer | What we use | Why this, and not the alternatives |
|---|---|---|
| Language | **Python 3.11** | All the AI, data and web libraries we need are in Python; 3.11 is supported by every one of them. |
| Web server | **FastAPI** + Uvicorn | Gives WhatsApp an address to send messages to, and serves the chat page. Flask could do it too; FastAPI is quicker to write and checks inputs for us. |
| Chat page | **Gradio** (inside FastAPI) | A ready-made chat page in about 50 lines; it came from our first prototype. Streamlit cannot receive WhatsApp messages. |
| Reading PDFs | **pdfplumber** | Keeps tariff tables readable. The first prototype's loader only read .txt files and skipped all 17 PDFs without an error. |
| Embeddings | **Gemini `gemini-embedding-001`** (768 numbers) | Free and good quality. A model on our own server needs about 1 GB of memory; the free host has 512 MB. OpenAI is paid. |
| Search | **numpy** (one matrix of 1,476 × 768 numbers) | At this size one multiplication finds the closest passages in milliseconds. A vector database (ChromaDB, FAISS) would add an install and a storage folder for no gain. |
| Writing replies | **Groq `openai/gpt-oss-20b`**, temperature 0.1 | Free, fast (about 1 second), and Groq does not keep request content by default. Low temperature keeps answers close to the documents. |
| Backup writer | **Gemini 2.5 Flash** | If Groq fails or runs out of quota, the reply still gets written. |
| Resolution-time model | **scikit-learn HistGradientBoosting** | Best of four models we compared on 912,253 records of 2020 data: 58.7% exact band against a 35.6% baseline. |
| Storage | **SQLite** | Built into Python: one file, no server to run. Free PostgreSQL tiers expire. |
| WhatsApp | **Meta WhatsApp Cloud API** | Official and free for a test number; no second company (like Twilio) between the resident and us. |
| Pipeline | **Our own code** (no LangChain) | In the first prototype two faults were hidden inside LangChain. With our own small steps, each one can be tested and explained. |
| Code and hosting | **GitHub** + **Render** (free tier) | Render rebuilds the app every time `main` changes. Hugging Face Spaces and Railway now need paid plans for this use. |

---

## Project structure

```
cityassist/
├── app/                  the application itself
├── docs/
│   ├── pdfs/             17 City of Cape Town documents (by-laws, tariffs, policies)
│   ├── guides/           6 short reporting guides written by the group
│   └── sources.csv       title, publisher, date and origin of every document
├── prompts/
│   ├── system_prompt.txt the instructions given to the AI on every reply
│   └── recording_notice.txt  the first message of every conversation
├── data/vectors/         the documents turned into numbers (vectors.npy) + their text (meta.json)
├── models/               trained time model, department lookup, the 455 request types as numbers
├── scripts/              build the data files, train the model, run the evaluation
├── tests/                160 test messages and the evaluation results
├── requirements.txt      exact library versions (so Render installs the same ones)
└── .python-version       tells Render to use Python 3.11
```

### Inside `app/`: what each file does

| File | In plain words |
|---|---|
| `main.py` | **The front door.** Creates the FastAPI app, defines the addresses (`/`, `/chat`, `/whatsapp`, `/health`), creates the database tables and puts the Gradio page inside. |
| `web_chat.py` | **The chat page.** Builds the Gradio page (title, chat window, text box, examples, footer). For each message: checks the rate limit, calls the assistant, saves both sides of the exchange. |
| `whatsapp.py` | **The WhatsApp door.** Checks that a message really comes from Meta, ignores repeats, applies the rate limit, gets the answer from the assistant and sends it back through Meta. |
| `assistant.py` | **The brain, or decision maker.** Takes one message and decides what to do: greeting, question or report. Calls the other files in the right order and applies every safety check (personal details, invented suburbs, citations, emergency line). Both channels call this same file. |
| `search.py` | **The librarian.** Turns a question into numbers and finds the 5 most similar passages in the documents, ignoring any below the 0.60 threshold. |
| `llm.py` | **The writer.** Sends instructions and passages to Groq and returns its reply; if Groq fails, asks Gemini instead. |
| `report.py` | **The listener for reports.** Asks Groq whether the message is a report, which of the 8 closest request types it is, and what suburb and street were mentioned. |
| `classifier.py` | **The department and time estimate.** Looks up which department handles a request type, and predicts the resolution-time band with the trained model. |
| `suburbs.py` | **The suburb checker.** Matches what the resident typed ("Rondebosh") to one of the 775 official suburb names ("RONDEBOSCH"). |
| `redact.py` | **The privacy filter.** Replaces ID numbers, phone numbers, emails and long account numbers with labels such as `[phone number removed]`. |
| `noise.py` | **The cleaner.** Recognises useless passages (contents pages full of dots, empty tables) so they are never used as answers. |
| `database.py` | **The record keeper.** Creates and writes the two SQLite tables, `messages` and `drafts`. |
| `config.py` | **The settings.** File locations, model names, limits (top 5, threshold 0.60, 1,000 characters) and the API keys read from `.env`. |

---

## Security and privacy

A prompt asks the AI to behave; it cannot force it. So every rule that must **always** hold is written in code, not just in the prompt.

| Feature | What it does | Why we added it |
|---|---|---|
| **Recording notice** | The first message of every conversation says this is an automated student prototype, that the conversation is recorded, and not to share ID or bank numbers. | Residents must know who they are talking to and that it is recorded (POPIA: openness). |
| **Personal details removed** (`redact.py`) | ID numbers (13 digits), SA phone numbers, emails and 9–12 digit account numbers are replaced **before** anything is saved or sent to Groq or Gemini. | Residents often type these anyway. This way they never leave our server and never sit in our database. |
| **Rate limiting** | At most **6 messages per minute per person**, on the web page (per internet address) and on WhatsApp (per phone number). Extra messages get "please wait a minute". | Every message costs two AI calls from a free daily quota that everyone shares. In testing, about 80 messages used up a whole day's quota. Without a limit, one person or a script could make the assistant useless for everyone, or flood the server. |
| **WhatsApp signature check** | Meta signs every message with a secret only Meta and we know (HMAC-SHA256). Messages without a valid signature are rejected (403). | Anyone can find the `/whatsapp` address. Without this check, anyone could send fake messages that look like they come from residents. |
| **Duplicate protection (idempotence)** | The last 500 WhatsApp message IDs are remembered; a message that arrives twice is answered once. | Meta re-sends a message if it does not get a quick "OK". Without this, the resident would get two replies and two drafts. |
| **Answer later, acknowledge now** | `/whatsapp` replies "received" immediately and works on the answer in the background. | Meta expects an answer within seconds, or it retries. |
| **Phone numbers hashed** | On WhatsApp the conversation ID is a one-way hash of the phone number. | We can follow a conversation without ever storing the number itself. |
| **Grounding threshold** | If no passage scores at least 0.60, the AI is not called; the resident is told the documents don't cover it. | The AI cannot answer from general knowledge if it is never asked. |
| **Citation check** | A reply that cites a passage it was not given is thrown away. Sources are added by the code, not the AI. No sources are shown when the reply says it has no answer. | Residents can check every answer, and fake citations are caught. |
| **Valid request types only** | The AI picks from a numbered list of the 8 closest of 455 real City types; it cannot make one up. | The department and time estimate depend on a real type. |
| **No invented suburbs** | A suburb is only used if the resident actually wrote it (small typos like "Claremon" are allowed) and it is one of the 775 official names. | In testing the AI sometimes "filled in" a suburb the resident never mentioned. |
| **Emergency line** | Messages about fire, flooding, live wires, sparking or sewage inside a house get the City's emergency number first. | Safety comes before any process. |
| **Parameterised SQL** | Database writes use `?` placeholders, never text pasted into a query. | Prevents SQL injection. |
| **Secrets stay secret** | API keys and the WhatsApp token live only in `.env` (ignored by Git) and in Render's settings. The database and raw data are also ignored by Git. | Nothing secret or personal is ever pushed to GitHub. |
| **Message length limit** | Messages over 1,000 characters are refused politely. | Protects the quota and stops very long inputs. |
| **Human in the loop** | Reports become **drafts** with status `draft`. Nothing is submitted to the City. | A person stays responsible for what reaches the City. |
| **Protected `main` branch** | Changes reach `main` through reviewed pull requests (CODEOWNERS). | `main` is what Render deploys, so it must always work. |

---

## Running it on your own computer

You need **Python 3.11**, **Git**, an internet connection, and two free API keys:

- **Gemini**: https://aistudio.google.com/apikey
- **Groq**: https://console.groq.com/keys

### 1. Get the code

```bash
git clone https://github.com/KennyMagloire/cityassist.git
cd cityassist
```

### 2. Create a virtual environment and install the libraries

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

Create a file called `.env` in the `cityassist` folder:

```
GEMINI_API_KEY=your-gemini-key
GROQ_API_KEY=your-groq-key
```

The app stops at start-up with a clear message if either key is missing.

The WhatsApp keys are optional. Without them `/whatsapp` is switched off and the web chat works normally:

```
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_ID=...
WHATSAPP_APP_SECRET=...
WHATSAPP_VERIFY_TOKEN=...
```

`.env` is listed in `.gitignore`: **never commit it.**

### 4. Start the app

```bash
python -m app.main
```

Open http://127.0.0.1:8000. It goes straight to the chat page.

Things to try:

| Type this | You should see |
|---|---|
| `hi` | A short greeting |
| `How do I report a water leak?` | An answer with a **Sources** list |
| `There is a big pothole in the road`, then `Main Road, Claremon` | A question about the location, then a **draft** |
| `Who won the rugby last night?` | A polite "I couldn't find that" |
| the same short message 7 times within a minute | "You're sending messages quickly..." |

Conversations are saved in `data/conversations.db`. Look at them with `python scripts/show_messages.py`, or open the file in **DB Browser for SQLite**.

---

## Testing and results

`tests/test_utterances.csv` holds **160 test messages written by the group**: complete reports, reports without a location, vague reports, questions the documents answer, questions they don't, greetings, misspellings, unofficial suburb names, and one message each in Afrikaans and isiXhosa. Each row has the expected intent, request type, department and behaviour.

```bash
python scripts/run_evaluation.py
```

Every message goes through the real assistant. What it understood, the reply and the time taken are saved in `tests/evaluation_results.csv`. The script waits 15 seconds between messages to stay inside the free limits, so a full run takes about 45 minutes. If it stops, run it again: it continues where it left off.

If the daily quota runs out during a run, the affected rows get the fallback reply. Remove them and run again later:

```bash
python scripts/drop_failed_rows.py
python scripts/run_evaluation.py
```

### Results (160 messages)

| Measure | Before fixes | After fixes |
|---|---|---|
| Intent (question, report, greeting) | 144/160 (90.0%) | **145/160 (90.6%)** |
| Right department | 94/120 (78.3%) | **97/120 (80.8%)** |
| Exact request type (out of 455) | 71/120 (59.2%) | 71/120 (59.2%) |
| Right next step (draft, ask location, answer, decline, greet) | 126/160 (78.8%) | **131/160 (81.9%)** |
| Complete reports turned into a draft | 22/23 | **23/23** |
| In-scope questions answered correctly (read by us) | 6/15 | **10/15** |
| Out-of-scope questions safely declined (read by us) | 12/15 | **13/15** |
| Median reply time | 1.2 s | 1.2 s |

`tests/evaluation_results_before_fixes.csv` keeps the first run for comparison.

---

## Rebuilding the data files

The files the app needs are already in the repository (`data/vectors/`, `models/`). You only need this if the documents or the training data change.

| Step | Command | What it does |
|---|---|---|
| 1 | `python scripts/extract_chunks.py` | Splits the PDFs and guides into passages of about 770 characters |
| 2 | `python scripts/build_vectors.py` | Turns every passage into numbers (paces itself; resumes if the daily limit is reached) |
| 2b | `python scripts/add_vectors.py` | Only re-does passages that are new or changed |
| 3 | `python scripts/check_noise.py` | Shows which passages are ignored as noise |
| 4 | `python scripts/build_type_vectors.py` | Turns the 455 request-type names into numbers |
| 5 | `python scripts/build_code_groups.py` | Saves the group of each request type |
| 6 | `python scripts/train_bands.py` | Trains the resolution-time model |

Step 6 needs the cleaned service-request data at `data/processed/sr_hex_clean.csv.gz`. It is not in the repository because of its size; see [Data sources](#data-sources).

---

## Deploying on Render

1. **New → Web Service**, connected to this repository, branch `main`.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Under **Environment**, add `GEMINI_API_KEY` and `GROQ_API_KEY` (and the WhatsApp keys if used).
5. Optional: set the health check path to `/health`.

Render rebuilds automatically after every push to `main`. On the free tier the service sleeps after 15 minutes without visitors and its disk is reset, so saved conversations are lost on restart.

---

## Data sources

- **Service requests 2020:** published by the City of Cape Town's Data Science unit under the MIT licence: https://github.com/cityofcapetown/ds_code_challenge (file `sr_hex.csv.gz`, 941,634 requests). Used to train the time model and build the department lookup.
- **City documents:** 17 PDFs from the City of Cape Town website and Open By-laws, listed with publisher and date in `docs/sources.csv`. They remain the property of the City of Cape Town.
- **Reporting guides:** 6 short guides written by the group from the City's contact pages (`docs/guides/`).
- **Suburb names:** the 775 official names in the City's data.

---

## Limitations and future work

| Limitation now | What we would do next |
|---|---|
| WhatsApp replies are blocked by Meta (error 131031) until the business is verified, which a student group cannot do. | Run WhatsApp under a verified organisation account, ideally the City's own. |
| Messages (without personal details) are processed abroad; Gemini's free tier may use content to improve Google's products. | Paid tiers with data-processing agreements, or a model hosted in South Africa; a POPIA impact assessment. |
| Free hosting: slow first reply, database wiped on restart, one instance, a daily AI quota. | Paid always-on hosting, a hosted PostgreSQL database, and a load balancer across several instances as traffic grows. |
| The rate limit is kept in memory: it resets on restart, and people on the same network share it. | Keep it in a shared store such as Redis. |
| The citation check cannot prove that a passage supports the claim (one invented answer in testing). | A second check of each cited sentence, and a filter that sends provincial or national topics to the right authority. |
| Only official suburb names; no map. | A list of common names (Kuils River, Goodwood, CBD) and WhatsApp location sharing. |
| The time estimate uses 2020 data. | Retrain on recent years with bulk closures cleaned. |
| Text only, mainly English. | Photos, voice notes, Afrikaans and isiXhosa, each with its own tests. |
| Drafts are not sent to the City. | Connect approved drafts to the City's service-request system. |

---

## Credits and licence

**Group:** Kenny, Keo and Ziyanda (CPUT, AIE580S / DSE580S, 2026).

- **Keo** built the first prototype: the Gradio chat page, the six reporting guides, the system prompt, the department lookup and the cleaned dataset.
- **Ziyanda** wrote test messages, worked on the spreadsheets and data files, and rewrote report text.
- **Kenny** built the backend, the document pipeline, the time model, WhatsApp and the deployment, and merged the two prototypes.

The **code** is released under the [MIT licence](LICENSE). The City documents in `docs/pdfs/` and the service-request data belong to the City of Cape Town and are used here for study only.
