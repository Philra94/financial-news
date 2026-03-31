const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export function formatReadableDate(iso: string): string {
  const [yearStr, monthStr, dayStr] = iso.split('-')
  const day = Number(dayStr)
  const month = MONTHS[Number(monthStr) - 1]
  return `${day}. ${month} ${yearStr}`
}
