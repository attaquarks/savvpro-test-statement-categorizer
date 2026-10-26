import { ALL_CATEGORIES } from '../categories.js'
import { money } from '../format.js'

const FILTER_LABELS = {
  all: 'All',
  'needs-review': 'Needs review',
  transfers: 'Transfers',
  refunds: 'Refunds',
  income: 'Income',
}

export default function TransactionsTable({
  transactions,
  counts,
  filter,
  onFilterChange,
  search,
  onSearchChange,
  onCategoryChange,
  updatingSummary,
  fileName,
}) {
  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Transactions</h2>
        <span className="muted">
          {fileName} · {counts.all} rows
          {updatingSummary && <span className="chip chip--busy">updating totals…</span>}
        </span>
      </div>

      <div className="toolbar">
        <div className="tabs">
          {Object.entries(FILTER_LABELS).map(([id, label]) => (
            <button
              key={id}
              type="button"
              aria-pressed={filter === id}
              className={`tab${filter === id ? ' tab--active' : ''}`}
              onClick={() => onFilterChange(id)}
            >
              {label}
              <span className="tab__count">{counts[id]}</span>
            </button>
          ))}
        </div>
        <input
          type="search"
          className="search"
          placeholder="Search description or date…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

      {transactions.length === 0 ? (
        <div className="empty-note" role="status">
          <p style={{ margin: '0 0 0.5rem' }}>
            No transactions match this filter. Clear the search or pick another tab.
          </p>
          <button
            type="button"
            className="btn"
            onClick={() => {
              onSearchChange('')
              onFilterChange('all')
            }}
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th className="num">Amount</th>
                <th>Category</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((txn) => (
                <tr
                  key={txn.id}
                  className={
                    txn.category === 'Needs Review'
                      ? 'row--review'
                      : txn.category === 'Refund'
                        ? 'row--refund'
                        : txn.category === 'Transfer'
                          ? 'row--transfer'
                          : ''
                  }
                >
                  <td className="nowrap">{txn.date}</td>
                  <td>
                    {txn.description}
                    {txn.source === 'user' && <span className="chip">edited</span>}
                  </td>
                  <td className={`num nowrap ${txn.amount_cents > 0 ? 'positive' : ''}`}>
                    {money(txn.amount_cents)}
                  </td>
                  <td>
                    <select
                      className={`category-select${
                        txn.category === 'Needs Review' ? ' category-select--review' : ''
                      }`}
                      value={txn.category}
                      onChange={(e) => onCategoryChange(txn.id, e.target.value)}
                      aria-label={`Category for ${txn.description}`}
                    >
                      {!ALL_CATEGORIES.includes(txn.category) && (
                        <option value={txn.category}>{txn.category}</option>
                      )}
                      {ALL_CATEGORIES.map((category) => (
                        <option key={category} value={category}>
                          {category}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="reason">{txn.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
