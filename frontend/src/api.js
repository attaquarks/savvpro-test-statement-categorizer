async function handleResponse(res) {
  if (res.ok) return res.json()
  let message = `Request failed (${res.status})`
  try {
    const body = await res.json()
    if (body && body.detail) message = body.detail
  } catch {
    // keep the generic message
  }
  throw new Error(message)
}

export async function uploadStatement(file, chargeSign = 'negative') {
  const form = new FormData()
  form.append('file', file)
  form.append('charge_sign', chargeSign)
  const res = await fetch('/api/upload', { method: 'POST', body: form })
  return handleResponse(res)
}

export async function recomputeSummary(transactions) {
  const res = await fetch('/api/summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transactions }),
  })
  return handleResponse(res)
}

export const SAMPLE_CSV_URL = '/api/sample/csv'
export const SAMPLE_PDF_URL = '/api/sample/pdf'
