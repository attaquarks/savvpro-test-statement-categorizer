import { money } from '../format.js'

// A single ledger-style strip instead of a grid of identical cards: the
// net figure is the primary reading, the rest are aligned references.
export default function SummaryPanel({ summary }) {
  const reviewPending = summary.needs_review_count > 0

  return (
    <section className="summary" aria-label="Summary">
      <div className="summary__primary">
        <h2 className="summary__label">Net spending</h2>
        <p className={`summary__value${reviewPending ? ' summary__value--warning' : ''}`}>
          {money(summary.net_spending_cents)}
        </p>
        <p className="summary__sub">
          {money(summary.total_spending_cents)} gross − {money(summary.total_refunds_cents)} in
          refunds
        </p>
      </div>

      <div className="summary__rest">
        <div className="summary__item">
          <h3 className="summary__label">Income</h3>
          <p className="summary__item-value summary__item-value--positive">
            {money(summary.total_income_cents)}
          </p>
          <p className="summary__sub">Refunds are not counted as income</p>
        </div>

        <div className="summary__item">
          <h3 className="summary__label">Transfers</h3>
          <p className="summary__item-value">{money(summary.transfers_out_cents)}</p>
          <p className="summary__sub">
            out · {money(summary.transfers_in_cents)} in · {summary.transfers_count} excluded
          </p>
        </div>

        <div className="summary__item">
          <h3 className="summary__label">Needs review</h3>
          <p className={`summary__item-value${reviewPending ? ' summary__item-value--amber' : ''}`}>
            {reviewPending && <span className="summary__dot" aria-hidden="true" />}
            {summary.needs_review_count}
          </p>
          <p className="summary__sub">{money(summary.needs_review_amount_cents)} held out of totals</p>
        </div>
      </div>
    </section>
  )
}
