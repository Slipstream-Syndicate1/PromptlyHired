/**
 * Shared names for application stages and communications.
 *
 * History, the Dashboard, the Calendar and Job detail all show these, and they
 * must read the same everywhere. Values match the backend enums exactly.
 */

export const APPLICATION_STATUSES = [
  { value: 'applied', label: 'Applied' },
  { value: 'online_assessment', label: 'Online assessment' },
  { value: 'interview', label: 'Interview' },
  { value: 'offer', label: 'Offer' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'withdrawn', label: 'Withdrawn' },
]

// Still waiting on the employer: the stages where following up makes sense.
export const OPEN_STATUSES = new Set(['applied', 'online_assessment', 'interview'])

export function statusLabel(value) {
  return APPLICATION_STATUSES.find((s) => s.value === value)?.label ?? value
}

export const COMMUNICATION_KINDS = [
  { value: 'email', label: 'Email' },
  { value: 'call', label: 'Call' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'message', label: 'Message' },
  { value: 'other', label: 'Other' },
]

export const COMMUNICATION_DIRECTIONS = [
  { value: 'received', label: 'Received' },
  { value: 'sent', label: 'Sent' },
]
