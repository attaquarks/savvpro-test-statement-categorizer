import { money } from '../format.js'
import { REFUNDS_UNMATCHED } from '../categories.js'

export default function CategoryTable({ summary }) {
  const rows = summary.by_category
  if (rows.length === 0) {
    return (
      <section className="panel">
        <h2 className="panel__title">Totals by category</h2>
        <p className="empty-note">No categorized spending yet.</p>
      </section>
    )
  }

  const maxNet = Math.max(...rows.map((row) => Math.max(row.net_cents, 0)), 1)

  return (
    <section className="panel">
      <h2 className="panel__title">Totals by category</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th className="num">Txns</th>
              <th className="num">Spending</th>
              <th className="num">Refunds</th>
              <th className="num">Net</th>
              <th className="bar-col" aria-label="Share of spending" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.category}>
                <td>
                  {row.category === REFUNDS_UNMATCHED ? (
                    <em className="muted">{row.category}</em>
                  ) : (
                    row.category
                  )}
                </td>
                <td className="num">{row.transaction_count}</td>
                <td className="num">{row.spending_cents ? money(row.spending_cents) : '—'}</td>
                <td className="num">
                  {row.refunds_cents ? (
                    <span className="positive">−{money(row.refunds_cents)}</span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="num strong">{money(row.net_cents)}</td>
                <td className="bar-col">
                  {row.net_cents > 0 && (
                    <div className="bar">
                      <div
                        className="bar__fill"
                        style={{ width: `${Math.round((row.net_cents / maxNet) * 100)}%` }}
                      />
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>Total</td>
              <td className="num">{summary.transaction_count}</td>
              <td className="num">{money(summary.total_spending_cents)}</td>
              <td className="num">−{money(summary.total_refunds_cents)}</td>
              <td className="num strong">{money(summary.net_spending_cents)}</td>
              <td className="bar-col" />
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="panel__note">
        Net = spending − refunds matched to that category. Transfers are excluded everywhere, and
        rows still under review are held out of these totals.
      </p>
    </section>
  )
}
