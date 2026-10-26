// Category values mirror backend/app/categories.py. The API is the source
// of truth for categorization; this list only feeds the correction dropdown.
export const SPENDING_CATEGORIES = [
  'Software & Subscriptions',
  'Travel',
  'Meals & Entertainment',
  'Office Supplies',
  'Hardware & Equipment',
  'Advertising & Marketing',
  'Professional Services',
  'Education & Training',
  'Fees & Charges',
]

export const SPECIAL_CATEGORIES = ['Income', 'Refund', 'Transfer', 'Needs Review']

export const ALL_CATEGORIES = [...SPENDING_CATEGORIES, ...SPECIAL_CATEGORIES]

export const REFUNDS_UNMATCHED = 'Refunds (unmatched)'
