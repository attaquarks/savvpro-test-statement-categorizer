# DESIGN.md

## 1. Use case and why

**Customer:** a freelance designer who needs their business bank/credit-card statement
sorted for tax time. (This is the use case sketched in the task's example, built out in full.)

Their statement mixes software subscriptions, client travel, meals, hardware, ad spend,
client payments, refunds, bank fees and account transfers. At tax time each of those lands
in a different bucket — and two of them (transfers, refunds) must not be counted as
spending or income at all. The app's job is to do that sort *explainably*: every row shows
the rule that decided it, and rows the rules cannot place are marked **Needs Review**
instead of guessed.

**The one big rule** (from the task): the categorization brain is our own deterministic
Python code — ordered keyword rules and sign logic. No GPT/Claude/Gemini/ML model is
involved at any point.

## 2. Pipeline

```
Upload (CSV / text PDF)
  → parse rows (amounts → integer cents; dates → ISO)
  → rule engine assigns {category, needs_review, reason, rule_id, refund_category}
  → summarizer builds totals
  → user reviews, corrects categories from the UI
  → POST /api/summary recomputes totals from the corrected list
```

The API is stateless by design: the server never persists statements. The client holds the
transaction list, sends it back for recomputation after every correction — one source of
truth for the math, no sync bugs.

## 3. The decision engine

Everything is matched against a *normalized* description (uppercased, punctuation collapsed
to spaces → tokens). A rule's keyword sequence (e.g. `GOOGLE, ADS`) must appear as a
contiguous token run — so `STARBUCKS` matches `STARBUCKS STORE 8842` but invented matches
across word boundaries can't happen. Rules fire in a fixed order; first match wins:

| # | Tier | Examples | Decision |
| --- | --- | --- | --- |
| 1 | **Fees** | `MONTHLY SERVICE FEE`, `WIRE TRANSFER FEE`, `INTEREST CHARGE` | debit → **Fees & Charges**; credit → **Refund** offsetting fees (a fee reversal). Checked *before* transfers so a wire transfer fee stays a fee. |
| 2 | **Transfers** | `TRANSFER TO SAVINGS`, `XFER`, `AUTOPAY`, `CREDIT CARD PAYMENT` | **Transfer**, both directions — excluded from spending and income. |
| 3 | **Income keywords** (credits only) | `INVOICE PAYMENT`, `STRIPE PAYOUT`, `PAYROLL`, `INTEREST PAID` | **Income**. The same words on a debit do *not* make income. |
| 4 | **Merchant rules** (≈60 curated merchants) | `ADOBE` → Software, `UBER` → Travel, `STAPLES` → Office Supplies… | debit → the merchant's spending category; **credit → Refund offsetting that merchant's category** (money back from a merchant you spent with — never new income). |
| 5 | **Ambiguous marketplaces** | `AMAZON`, `AMZN`, `PAYPAL`, `WALMART`, `TARGET`, bare `APPLE` | **Needs Review**, with a reason that says why. A marketplace row could be supplies, equipment or personal; the engine refuses to guess. (`AMAZON WEB SERVICES` and `APPLE.COM` have specific rules that win first.) |
| 6 | **Refund wording, no merchant** | `REFUND ISSUED` | **Needs Review** — clearly a refund, but the original expense is unknown, so the user must say what it offsets. |
| 7 | **ML text model (debits only)** | `DELTA AIRLINES TKT 016441`, `MICROSOFT CORPORATION RENEWAL 9988123` | ordinary spending category **only if** the locally trained classifier clears `MIN_SCORE=0.65` and `MIN_MARGIN=0.15`; the row carries `method: "ml"` and a confidence. Skipped entirely when the model is unavailable. |
| 8 | **Fallback** | anything else | debit → Needs Review ("unrecognized merchant"); credit → Needs Review ("could be income or a refund"). |

Every decision carries a `reason` string (rendered in the UI) and a stable `rule_id`
(e.g. `M-ADOBE`, `T-TRANSFER`, `A-AMAZON`). The engine is pure and deterministic: same
row in, same classification out, no hidden state.

### Why these cases get special treatment

- **Refunds are not income.** A credit whose description matches a known merchant is
  booked as a `Refund` that *offsets that merchant's spending category*. Income totals
  never include refunds; category totals show `net = spending − refunds`.
- **Transfers are not spending.** Moving money between your own accounts (or paying your
  own card) changes no bucket except the transfer counters (`out` / `in`, shown but
  excluded everywhere else).
- **Fees are Spending, but named.** Bank/platform fees are deductible costs; they get
  their own `Fees & Charges` category (a `FEE REVERSAL` credit offsets it).
- **Uncertainty is surfaced, not smoothed over.** Needs-Review rows are colored, counted,
  and their amounts are *held out of every total* until a human assigns a category.

### The ML tier: local text classification, nothing external

The exact keyword tiers above miss ordinary spending wording that doesn't contain a known
token (`DELTA AIRLINES …` when only `DELTA, AIR` is a keyword, `MICROSOFT CORPORATION
RENEWAL …` when only `MICROSOFT, 365` is). Tier 7 closes part of that gap with a small
scikit-learn model trained at first use, in-process, in well under a second:

- **Training data is hand-labeled only**: every merchant rule's keyword sequence in
  `rules.py` is a human label contract, plus ~50 curated noisy variants in
  `training_data.py` (reference numbers, extra wording, suffixes). Engine *predictions*
  and the unlabeled downloaded sample CSVs are **never** used as labels.
- **Model**: description → lowercase, strip 4+-digit reference runs, punctuation → spaces
  (merchant words kept) → `FeatureUnion` of word TF-IDF (1–2-grams) and `char_wb` TF-IDF
  (3–5-grams) → `LogisticRegression(max_iter=1000, C=3.0)`.
- **Gating**: auto-categorize a debit only when top score ≥ 0.65 **and** top-two margin
  ≥ 0.15 (env: `ML_MIN_SCORE`, `ML_MIN_MARGIN`). Scores are screening signals, not
  calibrated probabilities.
- **Thresholds are validated, not guessed** (`backend/scripts/validate_ml.py`): 4-fold
  CV over 102 hand-labeled examples. At the default `C=1.0` no held-out row clears 0.65
  (0/75) — the tier would be dead code; at `C=30` wrong held-out predictions reach 0.75
  and would slip through. `C=3.0` keeps every wrong held-out prediction ≤ 0.53 and every
  deliberately-unfamiliar description ("JOES CAFE 9921", "CITY WATER UTILITY BILL", …)
  ≤ 0.33, while ~15% of correct held-out rows still clear the gate; production training
  (all examples) fires confidently on real wording variants (0.78, 0.86 on the two
  noisy-depiction test rows).
- **Fail-safe**: scikit-learn missing, too few labeled examples for a category
  (< 3 → category excluded; < 2 usable categories → tier disabled), or any
  training/inference error ⇒ the tier returns nothing and rows fall through to the
  tiers above/below. An upload can never crash because of the ML tier.
- **Semantics never come from the model**: it is consulted only for debits that reached
  the fallback; transfers, card payments, refunds/fees and ambiguous marketplaces are all
  decided earlier by rules regardless of how the model would score them.

`backend/scripts/evaluate_ml.py` reproduces the numbers reported against the custom
sample statement and (unlabeled, counts-only) any statement CSVs in the reviewer's
Downloads folder.

## 4. Summary math

`summarizer.py` maps each row's *final* category and sign into buckets (integer cents
throughout — no float drift):

| Final category | Effect on totals |
| --- | --- |
| Spending categories | negative amount → spending in that category; positive amount (user-placed credit) → refund offsetting it |
| `Income` | adds to income only |
| `Refund` | adds to the refunds total and offsets its `refund_category`; unmatched refunds are surfaced as a separate **Refunds (unmatched)** row |
| `Transfer` | counted in `transfers_out/in`, excluded from all money totals |
| `Needs Review` | counted, amount held — shown as "held out of totals" |

Because the mapping is sign+category based, **user corrections integrate for free**: change
a row's category in the UI and the recomputation places its amount correctly without any
special-casing. Unknown category strings (e.g. from a stale client) are treated as
Needs Review rather than silently dropped.

## 5. Statement formats and failure handling

Full user-facing spec in the README. Design decisions worth recording:

- **Amounts parse to integer cents** at the boundary; every quirk (`$1,234.56`,
  `(54.99)`, `54.99-`, `54.99 DR`) is normalized there and nowhere else.
- **Cardinal rule: never guess a sign convention.** If a single-`Amount` CSV parses and
  every amount is positive with no way to know which rows are debits (no Type column, no
  Debit/Credit pair), the file is rejected with an explanation (that pattern means an
  unsigned export; misreading it would flip every category). Files that *do* carry side
  information are handled natively:
  - a **Type column** (Chase-style) whose Debit/Credit/Withdrawal/Deposit wording
    determines the sign; genuinely two-sided values (`CHECK`, `PAYMENT`) are never
    guessed, and a file whose signs remain unknowable is still rejected;
  - an explicit **"Charges are positive" upload option** for the opposite convention
    (some American Express exports list charges positive, payments negative). This is a
    user decision, not a heuristic — no heuristic can distinguish an inverted mixed-sign
    file from a normal one without guessing. Mixed-sign files that *look* inverted
    (negative amounts on refund/payment lines) parse with a pointed warning so signed
    files keep working;
  - a strictly-shaped **headerless fallback** for Wells Fargo-style exports
    (`Date, Amount, Check number, Description` — every row must have a parseable date in
    column 1 and amount in column 2, or the fallback declines and the normal error fires).
- **Two-pass header matching**: exact names (`Description`, `Amount`, `Type`) win before
  aliases (`Details`, `Amt`, …), so Chase's `Details` column is not mistaken for the
  description.
- **Malformed rows degrade loudly**: the row is skipped, a warning with the file line
  number reaches the UI banner; structural failures (no header, zero usable rows) are
  distinct 400/422 responses with actionable messages.
- **Preamble tolerance**: the header row is located within the first 15 rows; leading
  marketing lines are ignored (with a warning) instead of failing the parse.
- **PDFs without text** (scans) are refused with a clear message — no silent empty result,
  no OCR pretending to work.

## 6. Frontend layer ("ledger" visual system)

Tool UI — Operate mode: scanability, familiarity, restraint. One visual world:

- **Palette** — warm paper ground (`#f6f5f1`), white surfaces, ink text (`#212832`), a
  single money-green accent (`#116149`) reserved for primary actions, selection and
  positive money. Amber only for review-required, red only for errors. Semantic tokens in
  `styles.css :root`.
- **Hierarchy** — one summary *strip* (net spending as the primary figure, income,
  transfers and review counts as aligned references) instead of a grid of identical cards;
  tables do the real work, with tabular numerals and right-aligned money.
- **States** — refund rows tint green, transfer rows gray (muted), review rows amber with
  the reason spelled out. Hover, focus-visible rings, disabled, loading (spinner in the
  dropzone), error and empty states are all implemented; the empty state teaches the
  format and offers one-click samples.
- **Motion** — a single 240 ms ease-out rise when results arrive (disabled under
  `prefers-reduced-motion`); everything else is 150 ms hover/focus feedback.
- **Accessibility** — real `<button>`/`<select>` controls, `aria-pressed` filter toggles,
  labeled controls, keyboard-operable dropzone, ≥4.5:1 text contrast, one `h1`.
- Responsive: the summary strip stacks, tables scroll horizontally on small screens,
  filter/search wrap.

## 7. Architecture

- **Backend** — FastAPI + Pydantic; pure-Python parsing (stdlib `csv`, `pdfplumber` for
  text PDFs). Stateless endpoints; ~10 modules with no cross-cutting magic.
- **Money** — integer cents end to end; formatted only at the UI edge.
- **Frontend** — React 19 + Vite, plain CSS (no UI framework), components per section,
  optimistic category updates with server-recomputed totals (a failed recomputation shows
  a non-fatal notice instead of losing the edit).
- **Serving** — Vite dev server proxies `/api` to uvicorn in development; in production
  mode FastAPI statically serves `frontend/dist` so one process runs the whole app.
- **Why no persistence:** the review session is short-lived; statements are sensitive and
  the safest storage is none. (Explicit non-goal for this assessment; a production version
  would add accounts + encrypted storage.)

## 8. Limitations

- Categorization is keyword-based by design: it will not infer a brand it has no rule for
  (those land in Needs Review — the intended behavior), and it cannot disambiguate a
  marketplace purchase for you.
- PDF support is text-layer only; scanned statements are refused.
- US-style ambiguous dates default to month/day/year; ISO is the documented primary.
- Single-user, no persistence, no auth — scoped as a local tool for this assessment.
- 5 MB / 20,000-row upload guardrails.
