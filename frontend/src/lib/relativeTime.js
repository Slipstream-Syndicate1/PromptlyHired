const UNITS = [
  { unit: 'year', ms: 365 * 24 * 60 * 60 * 1000 },
  { unit: 'month', ms: 30 * 24 * 60 * 60 * 1000 },
  { unit: 'week', ms: 7 * 24 * 60 * 60 * 1000 },
  { unit: 'day', ms: 24 * 60 * 60 * 1000 },
  { unit: 'hour', ms: 60 * 60 * 1000 },
  { unit: 'minute', ms: 60 * 1000 },
]

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

/** "3 days ago" / "in 2 days" / "yesterday" - works for past or future dates. */
export function relativeTime(input) {
  const date = new Date(input)
  const diffMs = date.getTime() - Date.now()

  if (Math.abs(diffMs) < 45_000) return diffMs < 0 ? 'just now' : 'in a moment'

  for (const { unit, ms } of UNITS) {
    if (Math.abs(diffMs) >= ms) return rtf.format(Math.round(diffMs / ms), unit)
  }
  return rtf.format(Math.round(diffMs / 60_000), 'minute')
}

/** The exact date/time, for a title/tooltip next to the relative text above -
 * relative time is easier to scan but loses precision, so pair the two. */
export function exactDateTime(input) {
  return new Date(input).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}
