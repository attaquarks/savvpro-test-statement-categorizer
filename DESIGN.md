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
| 7 | **Fallback** | anything else | debit → Needs Review ("unrecognized merchant"); credit → Needs Review ("could be income or a refund"). |

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
  every amount is positive, the file is rejected with an explanation (that pattern means
  an unsigned export; misreading it would flip every category). Two-column
  `Debit`/`Credit` exports are the supported alternative.
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
