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

/** "today" / "yesterday" / "3 days ago" / "in 2 weeks" for a date-only
 * value (YYYY-MM-DD). Day granularity on purpose: a date has no time, so
 * "7 hours ago" would be inventing precision it doesn't have. */
export function relativeDay(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number)
  const target = new Date(y, m - 1, d)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const days = Math.round((target - today) / (24 * 60 * 60 * 1000))
  if (Math.abs(days) >= 14) {
    for (const { unit, ms } of UNITS) {
      if (unit === 'hour' || unit === 'minute') break
      if (Math.abs(days) * 24 * 60 * 60 * 1000 >= ms) {
        return rtf.format(Math.round((days * 24 * 60 * 60 * 1000) / ms), unit)
      }
    }
  }
  return rtf.format(days, 'day')
}

/** relativeDay for the start of a phrase or a standalone figure: "Tomorrow",
 * "In 3 days". Mid-sentence uses ("Applied today") keep the lowercase form. */
export function relativeDayCap(isoDate) {
  const text = relativeDay(isoDate)
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** The exact date/time, for a title/tooltip next to the relative text above -
 * relative time is easier to scan but loses precision, so pair the two. */
export function exactDateTime(input) {
  return new Date(input).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}
