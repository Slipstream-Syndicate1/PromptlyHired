import { useState } from 'react'
import { api } from '../api/client'
import { APPLICATION_STATUSES, statusLabel } from '../lib/applicationStatus.js'

/**
 * Tracking for one job, on its detail page: mark it applied, move it between
 * stages, and set the next step.
 *
 * A stage change can carry a note ("Invited to interview by email"). That note
 * is stored on the status-change event, which is how employer responses are
 * recorded over time.
 */

// The local calendar date. toISOString() alone is UTC, which is already
// tomorrow for anyone west of Greenwich in the evening.
export function localToday() {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  return now.toISOString().slice(0, 10)
}

function formatDate(isoDate) {
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString()
}

function StageSelect({ value, onChange, label }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {APPLICATION_STATUSES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function ApplicationPanel({ jobId, application, onChange }) {
  const [status, setStatus] = useState(application?.status ?? 'applied')
  const [appliedDate, setAppliedDate] = useState(localToday())
  const [note, setNote] = useState('')
  const [nextAction, setNextAction] = useState(application?.next_action ?? '')
  const [nextActionDate, setNextActionDate] = useState(application?.next_action_date ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = async (action) => {
    setBusy(true)
    setError('')
    try {
      onChange(await action())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!application) {
    return (
      <>
        <h2 className="section-title">Application</h2>
        <div className="card">
          <p className="job-company" style={{ marginBottom: 12 }}>
            Applied to this job? Track it to follow its progress and record what the
            employer says.
          </p>
          {error && <div className="alert error">{error}</div>}
          <div className="filter-grid">
            <StageSelect label="Stage" value={status} onChange={setStatus} />
            <label className="field">
              <span>Date applied</span>
              <input
                type="date"
                value={appliedDate}
                max={localToday()}
                onChange={(e) => setAppliedDate(e.target.value)}
                required
              />
            </label>
          </div>
          <button
            className="btn primary"
            disabled={busy || !appliedDate}
            onClick={() =>
              run(() =>
                api.createApplication({ job_id: jobId, status, applied_date: appliedDate }),
              )
            }
          >
            {busy ? 'Saving…' : 'Mark as applied'}
          </button>
        </div>
      </>
    )
  }

  const stageChanged = status !== application.status
  const nextStepChanged =
    nextAction !== (application.next_action ?? '') ||
    nextActionDate !== (application.next_action_date ?? '')
  const updatedLabel =
    application.days_since_update === 0
      ? 'Updated today'
      : `Updated ${application.days_since_update} day${application.days_since_update === 1 ? '' : 's'} ago`

  return (
    <>
      <h2 className="section-title">Application</h2>
      <div className="card">
        <div className="row-between">
          <p className="job-company">
            <strong>{statusLabel(application.status)}</strong> · applied{' '}
            {formatDate(application.applied_date)}
          </p>
          <span className="chip">{updatedLabel}</span>
        </div>

        {application.needs_follow_up && (
          <div className="alert info">
            <strong>Time to follow up.</strong>{' '}
            {application.next_action ||
              'No update for a while. A short, polite check-in email is reasonable.'}
          </div>
        )}

        {error && <div className="alert error">{error}</div>}

        <StageSelect label="Update stage" value={status} onChange={setStatus} />
        {stageChanged && (
          <>
            <label className="field">
              <span>What happened? (optional)</span>
              <input
                value={note}
                maxLength={2000}
                placeholder="e.g. Invited to interview by email"
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
            <div className="job-actions" style={{ marginTop: 0 }}>
              <button
                className="btn primary"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const updated = await api.updateApplication(application.id, {
                      status,
                      note: note.trim() || undefined,
                    })
                    setNote('')
                    return updated
                  })
                }
              >
                {busy ? 'Saving…' : `Move to ${statusLabel(status)}`}
              </button>
              <button className="btn" disabled={busy} onClick={() => setStatus(application.status)}>
                Cancel
              </button>
            </div>
          </>
        )}

        <div className="filter-grid" style={{ marginTop: 14 }}>
          <label className="field">
            <span>Next step</span>
            <input
              value={nextAction}
              maxLength={255}
              placeholder="e.g. Send a thank-you note"
              onChange={(e) => setNextAction(e.target.value)}
            />
          </label>
          <label className="field">
            <span>By</span>
            <input
              type="date"
              value={nextActionDate}
              onChange={(e) => setNextActionDate(e.target.value)}
            />
          </label>
        </div>

        <div className="job-actions" style={{ marginTop: 0 }}>
          <button
            className="btn"
            disabled={busy || !nextStepChanged}
            onClick={() =>
              run(() =>
                api.updateApplication(application.id, {
                  next_action: nextAction.trim() || null,
                  next_action_date: nextActionDate || null,
                }),
              )
            }
          >
            Save next step
          </button>
          <button
            className="btn link"
            disabled={busy}
            onClick={() => {
              const confirmed = window.confirm(
                'Stop tracking this application? Its stage history and logged communications will be deleted.',
              )
              if (confirmed) {
                run(async () => {
                  await api.deleteApplication(application.id)
                  return null
                })
              }
            }}
          >
            Stop tracking
          </button>
        </div>

        {application.communications_count > 0 && (
          <p className="fine-print">
            {application.communications_count} communication
            {application.communications_count === 1 ? '' : 's'} logged with this employer.
          </p>
        )}
      </div>
    </>
  )
}
