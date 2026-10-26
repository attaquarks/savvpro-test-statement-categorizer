import { useRef, useState } from 'react'

export default function UploadPanel({ loading, error, onFile, onSample }) {
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)

  return (
    <main className="page__main">
      <section
        className={`dropzone${dragOver ? ' dropzone--over' : ''}`}
        role="button"
        tabIndex={0}
        aria-label="Upload a statement file"
        onClick={() => !loading && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !loading) {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          if (!loading) setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (loading) return
          const file = e.dataTransfer.files?.[0]
          if (file) onFile(file)
        }}
      >
        {loading ? (
          <>
            <div className="spinner" aria-hidden="true" />
            <p className="dropzone__title">Reading your statement…</p>
            <p className="dropzone__sub">Parsing rows and running the categorization rules.</p>
          </>
        ) : (
          <>
            <p className="dropzone__title">Drop a statement here</p>
            <p className="dropzone__sub">CSV or text-based PDF, up to 5 MB. Nothing leaves your machine.</p>
            <button
              type="button"
              className="btn btn--primary"
              onClick={(e) => {
                e.stopPropagation()
                inputRef.current?.click()
              }}
            >
              Choose file
            </button>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.pdf"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onFile(file)
            e.target.value = ''
          }}
        />
      </section>

      {error && (
        <div className="banner banner--error" role="alert">
          <strong>Upload failed.</strong> {error}
        </div>
      )}

      <div className="samples">
        <span>No statement handy?</span>
        <button type="button" className="btn btn--ghost" disabled={loading} onClick={() => onSample('csv')}>
          Load sample CSV
        </button>
        <button type="button" className="btn btn--ghost" disabled={loading} onClick={() => onSample('pdf')}>
          Load sample PDF
        </button>
      </div>

      <details className="format-help">
        <summary>Which statement format does this support?</summary>
        <div className="format-help__body">
          <p>
            <strong>CSV</strong> — a header row with <code>Date</code>, <code>Description</code>{' '}
            and a signed <code>Amount</code> column (expenses negative, credits positive).
            Separate <code>Debit</code>/<code>Credit</code> columns, a preamble above the header,
            extra columns, <code>$</code>/<code>,</code> formatting and <code>(1,000.00)</code>{' '}
            negatives are all handled. Rows that cannot be parsed are reported, not silently
            dropped.
          </p>
          <pre>{`Date,Description,Amount
2026-03-02,ADOBE CREATIVE CLOUD,-54.99
2026-03-02,INVOICE PAYMENT ACME CORP,2400.00`}</pre>
          <p>
            <strong>PDF</strong> — text-based exports with one transaction per line in the form{' '}
            <code>YYYY-MM-DD DESCRIPTION AMOUNT</code>. Scanned/image PDFs are not supported and
            will be rejected with a clear message.
          </p>
        </div>
      </details>
    </main>
  )
}
