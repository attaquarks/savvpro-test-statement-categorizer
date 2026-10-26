# AI_USAGE.md — How I used AI to build this app

This file tells the full story of how AI helped me build this statement categorizer:
which tools I used, how we worked together phase by phase, where the AI got things
wrong, and exactly how many tokens it cost. I have written it in plain language so
anyone can follow the journey.

**The most important thing first:** the "brain" that decides transaction categories is
my own deterministic code (ordered keyword rules) plus a small classical machine-learning
model (scikit-learn) that is trained *locally, inside the app, in under a second*. The AI
assistant **wrote code for me** — it never classified a single transaction, and no
external AI API is called at runtime. That is the one big rule of this task, and the
whole workflow below was built around respecting it.

## Tools I used

| Tool | What it is | How I used it |
| --- | --- | --- |
| **ZCode** (coding agent) | An autonomous coding agent, powered by the **GLM 5.3 Flash** model (Z.ai) | The main worker. I gave it the task description, it read the repo, wrote the backend + frontend + tests + docs, ran the test suite, used git, and fixed bugs across the whole session (2026-10-26) |
| **Pytest** | Python test framework (used by the agent) | The safety net. Every change had to pass the full suite before it counted as done |
| **Headless Chromium** (local browser automation) | A scriptable real browser | To open the real running app, click through the UI like a user, and take screenshot proof that things work |
| **Web search / page fetch (Firecrawl MCP)** | Web tools available inside ZCode | To look at the public Kaggle dataset pages my sample CSVs came from, to understand their column layouts |
| **Context7 MCP (docs lookup)** | Re-fetches up-to-date library docs | For library API details while writing parser and frontend code |
| **Impeccable + frontend skills** | Design/QA skill plugins in ZCode, invoked on my instruction | A dedicated UI-quality pass: spacing, contrast, states, and batched screenshot verification of the interface |

Everything in this repository was written by the ZCode agent under my direction. No code
was copied from another human project, and no real bank statements or personal data were
ever used (see [Data hygiene](#data-hygiene) at the bottom).

## How I worked with the agent

My basic loop, repeated through the whole session:

1. **I describe what should happen or what is broken, in plain words.** Sometimes with a
   file or a screenshot or an error message I saw myself.
2. **The agent inspects the code and acts** — writes code, adds tests, runs the full
   pytest suite, and reports honestly what passed and what it changed.
3. **I check the real app in my browser myself.** I upload my own files, click through
   the UI, and report back anything that looks wrong.
4. **We fix what I found, with evidence** — a failing behavior becomes a failing test
   first, then a fix, then the test suite grows and the behavior is locked in.

This matters because the agent is not trusted on its own word: every claim ("the app
supports Type-column exports", "the ML tier is safe") had to have a test or a
screenshot behind it.

---

## Phase 1 — The one-shot build

I started with essentially one prompt: the full task description (`TASK.md`
+"build a complete working app, FastAPI backend, React frontend, deterministic rules
engine, refunds are not income, transfers excluded, uncertain → Needs Review, add
tests, use fake data, write README/DESIGN/AI_USAGE docs").

In that first working pass, the agent produced:

- **A complete FastAPI backend**: CSV and PDF parsers that turn messy bank exports into
  clean rows (money as integer cents so totals never drift), the ordered rule engine
  (fees → transfers → income → merchant rules → ambiguous marketplaces → refund wording
  → fallback), the summarizer, the upload API with real error handling.
- **A React + Vite frontend**: drag-and-drop upload, the transactions table with a
  reason for every row, a category dropdown to fix Needs-Review rows, a live summary
  panel, filters and search.
- **A pytest suite** (99 tests at that point) and it ran it itself: **4 tests failed on
  the first run**, all real bugs the AI had just written — see the mistakes list below.
  It fixed them and got the suite green.
- **Fake sample data**: a 37-row synthetic statement with an invented bank ("WESTBANK")
  and invented people, plus a script that generates a matching PDF so the samples stay
  in sync.
- **The first version of all three documentation files**, and a git history with clean
  commits pushed to my fork, with a pull request opened to the original repo.

So the first "one shot" gave me a working, tested, end-to-end product. What it did *not*
have was resistance to real-world bank formats — that is what the next phases were about.

## Phase 2 — I tested the real app in the browser, and found the gaps

This is where my own testing changed the project. I downloaded the app, ran it, and
tried to upload whatever CSVs and PDFs I had on hand. **Almost everything got rejected**
with the same error: *"Every amount in this file is positive."*

The cause: the first version assumed bank statements list expenses as negative numbers.
Many real banks don't — they export charges as positive numbers, or put the sign in a
separate column. I sent the agent the error and my files' column layouts, and told it to
adapt the app to real users.

What the AI built in response, each piece followed by tests:

- **Type-column support**: lines like `Db` / `Cr` / `DEPOSIT` / `WITHDRAWAL` in a "Type"
  or "Details" column now decide the sign (with a deliberate rule that ambiguous wording
  like `CHECK` is never guessed).
- **A "charges are positive" upload option**: for banks like American Express that list
  all charges positive, I can tell the app the convention instead of it guessing.
- **A headerless layout fallback** (Wells Fargo-style `Date, Amount, …, Description`
  with no header row).
- **Secondary description columns** (Remarks / Narration / Particulars / Mode) used when
  the main description is empty.
- **A smarter rejection guard**: truly ambiguous all-positive files are rejected with a
  helpful message, mixed-sign inverted files parse with a clear warning instead of
  silently miscategorizing money.

While fixing this, the agent also found and fixed a bug where a Chase "Details" column
could steal the Description column's place. The suite grew to **128 tests**, and the
agent verified each supported layout end-to-end with synthetic replicas of the real
formats (never my actual files — those stay on my machine) plus headless-browser
screenshot proof saved into `docs/screenshots/`.

## Phase 3 — Sample data from the internet, second round of weak areas

Next I tested with sample bank-statement datasets downloaded from the internet (Kaggle).
The agent used web tools to check the datasets' published column layouts, and we found
more weak areas:

- **Indian-bank `DrCr` exports**: a sign column containing `Dr`/`Cr`, lowercase dates
  and quoted amounts. The parser now reads the DrCr column for sign and falls back to
  the "mode" column when the description column is empty.
- **Banking-channel lines versus merchant descriptions**: rows like `ATM`, `NEFT`, `IMPS`,
  `RTGS` are money movement, not spending — the engine now books them as **Transfers**.
  Payment platforms (PhonePe, Flipkart, Google Pay) are deliberately **ambiguous
  marketplace rows** that go to Needs Review rather than being guessed.
- **"Why does everything go to Needs Review?"** — a fair question I asked after seeing
  the Kaggle file's results. The agent explained (and then I confirmed by reading the
  engine myself): those datasets have *anonymized* merchant names and channel-only
  descriptions, so no exact keyword can match. The engine refusing to guess is the
  intended, safe behavior — and it is exactly the gap Phase 4 attacks.

I also asked where the bundled sample statement came from, because that matters for
trusting the demo: the agent verified with git history that `sample-statements/` was
**generated for this project, not present in the original repository** — the CSV was
hand-authored from the task's example, the PDF is produced by a script from that CSV.

## Phase 4 — The ML layer (built on a separate branch, then merged)

After Phase 3, one honest limitation remained: the engine only understands wording that
contains an exact keyword (~120 rules worth). A line like `DELTA AIRLINES TKT 016441`
goes to Needs Review just because the rules only know `DELTA AIR`. So I asked for a
**lightweight, local, traditional machine-learning classifier** — with hard
requirements: never let an LLM or external AI decide categories, keep all
transaction-semantics rules (transfers/refunds/card payments) untouched, train **only on
genuine hand-labeled data** (never on the rule engine's own predictions, never on the
unlabeled Kaggle files), use conservative confidence gates, and **do it on a new branch**
so the main work stays safe.

What the agent did:

- Created branch `candidate-attaquarks-ml` from my submission branch.
- Built the classifier: TF-IDF word n-grams (1–2) + character n-grams (`char_wb`, 3–5)
  combined features → logistic regression, trained in-process in under a second on
  ~100 hand-labeled examples (the hand-written merchant keyword contracts plus ~50
  hand-written noisy variants).
- **Validated instead of guessed**: a small cross-validation sweep script showed the
  default regularization made the tier *dead* (0 of 75 held-out rows passing the 0.65
  score gate), while a looser setting let wrong predictions reach 0.74. The chosen
  middle setting (C=3.0) keeps every wrong held-out prediction below the gate while
  still firing confidently on realistic wording — the numbers are recorded in
  `DESIGN.md` and the sweep script is committed at
  `backend/scripts/validate_ml.py`.
- Added 12 focused tests (suite went 128 → 141), including: known merchants unchanged,
  noisy descriptions categorized without exact matches, weak predictions stay in
  review, transfers/refunds/card payments keep their treatment, empty descriptions
  don't crash, and a missing scikit-learn falls back safely to rules-only.
- Tested on my custom dataset and the downloaded sample CSVs and reported honest
  counts (33/33 correct auto-categorizations on the labeled sample; the ML tier adds
  zero changes to what the rules already got right, and stays silent on files with no
  trustworthy signal).
- The very act of testing those downloaded files exposed two more parser gaps
  (a misspelled `Withdrawls` column header, and files that fill both debit and credit
  columns with `00.00`), which were fixed with regression tests.

The final step: the ML branch was **merged back into `candidate-attaquarks`** with a
fast-forward merge, so the submitted pull request contains the whole journey and the
repo keeps a single clean line of work.

## Where the AI got things wrong (all caught by tests or by me, then fixed)

1. **First test run, 4 failures** — the CSV delimiter was detected but never passed to
   the reader; amounts like `$ (1,000.00)` were misparsed; a merchant rule
   (`APPLE.COM`) was missing; one test expectation about 2-digit years was itself wrong
   (the code was right).
2. **Chase "Details" column** could shadow the real Description column — fixed with
   exact-name-first header matching.
3. **All-positive real files were rejected** — the single biggest miss of the first
   build; the whole Phase 2 list exists because the one-shot version only knew
   "expenses are negative".
4. **Amex mixed-sign files**: the agent first assumed they should be rejected; on
   review that was wrong (a mixed-sign inverted file can't be auto-detected), so it
   now parses them with a pointed warning.
5. **The first ML pipeline was confidently useless**: with default settings the model
   was so regularized that no row ever cleared the confidence gate — the tier would
   have silently done nothing. Only the validation sweep caught this; it was invisible
   to happy-path tests.
6. **Occasional corrupted lines while writing large files** — a few stray tokens and
   one placeholder left inside test files by the agent. Each was caught immediately
   (pytest or a grep) and fixed before committing. This is exactly why the loop is
   "small edit → run tests", never "write everything, hope".
7. **One over-broad cleanup command** during development killed *all* Python processes
   on my machine instead of just the dev server. Harmless, but noted as a real-mess
   moment.

## Where I see this app going next

There is one thing about the app today that I keep noticing when I use it: every time I
fix a row in Needs Review — I tell the app "this JOES CAFE place is Meals", "this
SUNNY DESIGN STUDIO invoice is my Professional Services expense" — that teaching moment
disappears the second I close the tab, because the app is deliberately stateless. Next
month, on my next statement, I am the same stranger to it, and I fix the same rows all
over again.

That is the gap I want the ML layer to close in a future version. The idea in my head:

- when I pick a category in a review row, the app would **save that correction** —
  description, my chosen category, what the engine had guessed — as a small local
  record, instead of letting it evaporate;
- a **retrain script** would periodically merge those saved corrections into the local
  scikit-learn model, using the same validation gates it already uses today, so the
  model only gets promoted if it is genuinely better;
- and then the next statement classifies itself: the cafes, gyms, software and client
  invoices *I* personally labeled come back pre-categorized, and my review pile shrinks
  every month until only genuinely new merchants are left in it.

In other words: the app would stop being generic. It would grow into *my* categorizer —
learning the specific patterns, wording and recurring merchants of the one person who
uses it, which is exactly the knowledge that no fixed rule table (and no general
training set) can ever contain.

I did not build this in this session, and that is a deliberate call I made with the
agent rather than a shortcut we forgot: real learning needs real data collection and
retraining happening together, over weeks of my actual statements and corrections.
Inside the 12-hour build limit there was no usage history to train on, and a
simulated learning loop trained on invented corrections would have been dishonest
theater. The architecture sketch for exactly how this plugs into the existing engine,
API and ML tier is written up in `DESIGN.md`, section 9.

## Token usage and cost

Full-session figures for the ZCode agent (model GLM 5.3 Flash), as reported by the
ZCode app on 2026-10-26:

| Direction | Tokens |
| --- | --- |
| Input | 26.5M |
| — served from prompt cache | 25M |
| Completions / output | 170K |

- For context: `total = input + output`. Since ~25M of the 26.5M input tokens were
  cache hits, only a fraction of the input was actually processed fresh — that is why
  the cost stayed tiny. (Input up to the first ~5M tokens ran on the ZCode starter
  plan; the rest ran through the River AI provider.)

**Estimated total cost: ~$0.662.**

Context-window consumption across the session:

- **Peak**: 234.7K of 1M (23.5%) — Messages 79.2%, System tools 15%, MCP tools 3.5%,
  Skills 1.2%, System prompt 1.1%.
- **After compaction** (the agent's long context was summarized before the ML phase):
  dropped to 12.2K — this is how long sessions keep going without losing the plan.
- **Final window** (end of the ML phase + merge): 134.7K of 1M (13.5%) — Messages
  43.7%, MCP tools 29.3%, System tools 23.2%, Skills 1.9%, System prompt 1.7%.

Evidence note: these numbers are the owner-provided session figures read from the
ZCode app itself. The raw session logs were not committed to this repository, because
they can contain unrelated workspace context, and no screenshot could prove them
better than the app's own report.

## Data hygiene

- No real bank statements, no personal information, no keys, tokens or passwords were
  used or committed anywhere in this repository. All sample data is invented.
- All statement rows in `sample-statements/` reference fake people/businesses
  ("Jamie Rivera", "ACME CORP", the fake bank "WESTBANK").
- My own downloaded statement files (Kaggle datasets and samples in my Downloads
  folder) were used for local testing only, on my machine, and were **never committed**
  — the repository's test fixtures are synthetic files that replicate the same
  *formats*, which is the evidence standard this project follows.
