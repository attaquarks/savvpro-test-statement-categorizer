import { useMemo, useState } from 'react'
import { recomputeSummary, SAMPLE_CSV_URL, SAMPLE_PDF_URL, uploadStatement } from './api'
import { SPENDING_CATEGORIES } from './categories'
import CategoryTable from './components/CategoryTable.jsx'
import TransactionsTable from './components/TransactionsTable.jsx'
import UploadPanel from './components/UploadPanel.jsx'
import WarningsBanner from './components/WarningsBanner.jsx'
import SummaryPanel from './components/SummaryPanel.jsx'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'needs-review', label: 'Needs review' },
  { id: 'transfers', label: 'Transfers' },
  { id: 'refunds', label: 'Refunds' },
  { id: 'income', label: 'Income' },
]

export default function App() {
  const [phase, setPhase] = useState('idle') // idle | loading | ready | error
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [updatingSummary, setUpdatingSummary] = useState(false)
  const [chargeSign, setChargeSign] = useState('negative')
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')

  async function processFile(file) {
    const extension = file.name.toLowerCase().split('.').pop()
    if (!['csv', 'pdf'].includes(extension)) {
      setError('Unsupported file type. Upload a .csv or .pdf statement (see the format guide below).')
      setPhase('error')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('This file is larger than the 5 MB upload limit.')
      setPhase('error')
      return
    }
    setPhase('loading')
    setError('')
    setNotice('')
    try {
      const result = await uploadStatement(file, chargeSign)
      setData(result)
      setFilter('all')
      setSearch('')
      setPhase('ready')
    } catch (err) {
      setError(err.message)
      setPhase('error')
    }
  }

  async function loadSample(kind) {
    const url = kind === 'pdf' ? SAMPLE_PDF_URL : SAMPLE_CSV_URL
    const name = kind === 'pdf' ? 'sample_statement.pdf' : 'sample_statement.csv'
    setPhase('loading')
    setError('')
    setNotice('')
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error('Could not load the sample statement from the API.')
      const blob = await res.blob()
      await processFile(new File([blob], name, { type: blob.type }))
    } catch (err) {
      setError(err.message)
      setPhase('error')
    }
  }

  async function handleCategoryChange(txnId, newCategory) {
    if (!data) return
    const updated = data.transactions.map((txn) => {
      if (txn.id !== txnId) return txn
      const patch = {
        ...txn,
        category: newCategory,
        source: 'user',
        needs_review: false,
        reason: 'Reclassified by user.',
      }
      if (newCategory === 'Refund') {
        // A manual refund offsets the category the row previously sat in,
        // when that category is a spending category.
        patch.refund_category = SPENDING_CATEGORIES.includes(txn.category) ? txn.category : null
      }
      return patch
    })
    setData((prev) => (prev ? { ...prev, transactions: updated } : prev))
    setUpdatingSummary(true)
    setNotice('')
    try {
      const { summary } = await recomputeSummary(updated)
      setData((prev) => (prev ? { ...prev, summary } : prev))
    } catch (err) {
      setNotice(`Could not refresh totals: ${err.message}`)
    } finally {
      setUpdatingSummary(false)
    }
  }

  function reset() {
    setPhase('idle')
    setData(null)
    setError('')
    setNotice('')
  }

  const counts = useMemo(() => {
    const result = { all: data?.transactions.length ?? 0 }
    for (const f of FILTERS.slice(1)) result[f.id] = 0
    for (const txn of data?.transactions ?? []) {
      if (txn.category === 'Needs Review') result['needs-review'] += 1
      if (txn.category === 'Transfer') result.transfers += 1
      if (txn.category === 'Refund') result.refunds += 1
      if (txn.category === 'Income') result.income += 1
    }
    return result
  }, [data])

  const visibleTransactions = useMemo(() => {
    let rows = data?.transactions ?? []
    if (filter === 'needs-review') rows = rows.filter((t) => t.category === 'Needs Review')
    else if (filter === 'transfers') rows = rows.filter((t) => t.category === 'Transfer')
    else if (filter === 'refunds') rows = rows.filter((t) => t.category === 'Refund')
    else if (filter === 'income') rows = rows.filter((t) => t.category === 'Income')
    const query = search.trim().toLowerCase()
    if (query) {
      rows = rows.filter(
        (t) => t.description.toLowerCase().includes(query) || t.date.includes(query),
      )
    }
    return rows
  }, [data, filter, search])

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1>Statement Categorizer</h1>
          <p className="page__subtitle">
            Upload a freelance business statement, see every transaction categorized for tax
            time, and fix the rows the rules were not sure about.
          </p>
        </div>
        {phase === 'ready' && (
          <button type="button" className="btn btn--ghost" onClick={reset}>
            Upload another statement
          </button>
        )}
      </header>

      {phase !== 'ready' && (
        <UploadPanel
          loading={phase === 'loading'}
          error={error}
          onFile={processFile}
          onSample={loadSample}
          chargeSign={chargeSign}
          onChargeSignChange={setChargeSign}
        />
      )}

      {phase === 'ready' && data && (
        <main className="page__main page__main--results">
          <WarningsBanner warnings={data.warnings} />
          {notice && (
            <div className="banner banner--error" role="alert">
              {notice}
            </div>
          )}

          <SummaryPanel summary={data.summary} />
          <CategoryTable summary={data.summary} />
          <TransactionsTable
            transactions={visibleTransactions}
            counts={counts}
            filter={filter}
            onFilterChange={setFilter}
            search={search}
            onSearchChange={setSearch}
            onCategoryChange={handleCategoryChange}
            updatingSummary={updatingSummary}
            fileName={data.filename}
          />
        </main>
      )}

      <footer className="page__footer">
        All sample data is fake. The app runs entirely locally — statements are parsed in memory
        and never stored. Categorization is deterministic rule code, not an AI model.
      </footer>
    </div>
  )
}
