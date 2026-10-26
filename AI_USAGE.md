# AI_USAGE.md

How AI tools were used to build this assessment — what they contributed, where they got
things wrong, and what evidence exists for token usage.

## Tools used

| Tool | What it is | When |
| --- | --- | --- |
| **ZCode** (coding agent) | Autonomous coding agent, model `GLM-5.3-Flash` (Z.ai), running the user's `zai-start-plan` subscription | Built the application in one working session on 2026-10-26 |
| **Impeccable** (design skill, v4.5.2) + in-repo frontend engineering skill | Design/QA skill plugins invoked by the user mid-session | UI design pass, mechanical detector, browser screenshot verification |

Everything in this repository (backend, frontend, tests, sample data, docs) was written by
the ZCode agent under the user's direction; no code was copied from another human project.

## What the AI did

- Read `TASK.md` and implemented the full application end to end: FastAPI backend
  (CSV/PDF parsing, rule engine, summarizer), React + Vite frontend, pytest suite,
  sample data, documentation.
- Wrote and ran the 99-test pytest suite, fixed the failures it found, built the frontend
  bundle, started the real server, and verified the running system end to end
  (HTTP-level and with a headless Chromium driving the actual UI: load sample →
  review → correct a category → summary updates; desktop + mobile screenshots,
  zero console errors).
- Generated the sample PDF programmatically from the sample CSV so the two stay in sync.
- Kept the interview-style design decisions documented in `DESIGN.md`.

## Where the AI got things wrong (all caught by the test suite or review, then fixed)

1. **CSV delimiter computed but never used** — the parser sniffed `;`/tab delimiters and
   then still read with the default comma. Caught by the semicolon-delimiter test.
2. **Amount parser mishandled currency symbols around parentheses** — `$ (1,000.00)`
   failed because the open-parenthesis check ran before `$`/comma stripping. Caught by
   the amount tests.
3. **Forgot the `APPLE.COM/BILL` merchant rule** — "Apple purchases go to Software" was
   planned but the rule was never added, so those rows fell through to the ambiguous
   bucket. Caught by the normalization test.
4. **Initial UI used the generic "AI aesthetic"** — indigo-accent palette and a grid of
   four identical metric cards. The user redirected the session to run the Impeccable +
   frontend-engineering skills; the mechanical detector and a skill-based design pass
   replaced it with the ledger system (paper/ink/green, one summary strip) now in
   `styles.css`, and the refund/transfer row markers were redrawn after the design rules
   flagged them as decorative border bars.
5. **Test expectation error** — asserted `03/14/26 → 2026-03-26` before checking
   Python's `%y` two-digit-year mapping; the implementation was right, the expectation
   was wrong.
6. **Sample data typo** — an UBER row was written with a split description
   (four CSV fields); caught immediately on write and fixed before running tests.
7. **Design-time catch (before any test):** Zelle was shortlisted as a *transfer* keyword;
   looking at the sample row `ZELLE PAYMENT FROM <client>` showed that would misfile
   client income as a transfer, so the keyword was dropped rather than special-cased.
8. **First real-world feedback broke the parser** — the user's own bank exports were
   rejected with "Every amount in this file is positive". The initial version only
   understood the documented signed format and Debit/Credit column pairs. The fix
   (driven by this user feedback) added support for Chase-style `Type` columns,
   headerless Wells Fargo-style exports, an explicit "Charges are positive" option for
   Amex-style conventions, and a warning (instead of silence) for files that look
   inverted. The catch: format-accurate fixtures of major bank layouts
   (`backend/tests/fixtures/realworld/`, synthetic data) are now part of the test suite,
   plus browser end-to-end proofs (`docs/screenshots/realworld-*.png`).

## Token usage

Usage figures below were read from the ZCode desktop app's session details by the
repository owner (the agent harness itself cannot see token counters, which is why they
are reported here rather than by the agent during the session).

| Metric | Value |
| --- | --- |
| Platform | ZCode |
| Model | GLM 5.3 Flash (Z.ai) |
| Tokens consumed | 8M |
| Cache (cached input reads) | 7.7M |
| Output tokens | 170k |

**Context consumption** (peak context window use, 155.9K of 1M — 15.6%):

| Context slice | Share |
| --- | --- |
| Messages | 79.2% |
| System tools | 15% |
| MCP tools | 3.5% |
| Skills | 1.2% |
| System prompt | 1.1% |

Session date: 2026-10-26. Numbers above are the owner-provided session figures; the raw
session log lives in the ZCode app and was not committed (it can contain unrelated
workspace context).

## Data hygiene

- No real bank statements, personal information, keys, tokens or passwords were used or
  committed anywhere in this repository. All sample data is invented.
- All statement rows in `sample-statements/` reference fake people/businesses
  ("Jamie Rivera", "ACME CORP", fake bank "WESTBANK").
