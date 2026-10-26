const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

// Amounts travel through the API as integer cents to avoid float drift.
export function money(cents) {
  return usd.format(cents / 100)
}
