const STORAGE_KEY = 'jobtrail.calendar_events'

export const EVENT_TYPES = [
  { value: 'deadline', label: 'Application deadline' },
  { value: 'interview', label: 'Interview' },
  { value: 'offer', label: 'Offer acceptance deadline' },
  { value: 'other', label: 'Other' },
]

export function loadCalendarEvents() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(stored) ? stored : []
  } catch {
    return []
  }
}

export function saveCalendarEvents(events) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(events))
  } catch {
    // Keep the current session usable in private browsing mode.
  }
}

export function eventTypeLabel(type) {
  return EVENT_TYPES.find((item) => item.value === type)?.label || 'Other'
}

export function eventTypeShortLabel(type) {
  return {
    deadline: 'Deadline',
    interview: 'Interview',
    offer: 'Offer',
    other: 'Event',
  }[type] || 'Event'
}

export function formatEventDate(date) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(`${date}T12:00:00`))
}
