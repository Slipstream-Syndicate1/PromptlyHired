import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { APPLICATION_STATUSES } from '../lib/applicationStatus.js'
import { localToday } from './ApplicationPanel.jsx'

/**
 * Record an application sent somewhere this app never saw - a careers portal,
 * a referral, an email. Only company and position are needed; the rest can be
 * filled in later from the job page.
 */

const blank = () => ({
  company: '',
  position: '',
  url: '',
  location: '',
  status: 'applied',
  applied_date: localToday(),
  next_action: '',
  next_action_date: '',
  notes: '',
})

export default function LogApplication() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(blank)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      // Blank optional fields are left out rather than sent as empty strings.
      const payload = Object.fromEntries(
        Object.entries(form).filter(([, value]) => value.trim() !== ''),
      )
      const application = await api.createApplication(payload)
      setForm(blank())
      setOpen(false)
      navigate(`/jobs/${application.job.id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <div className="card row-between">
        <p className="job-company">
          <strong>Applied somewhere else?</strong> Log it here to track it with the rest.
        </p>
        <button className="btn" type="button" onClick={() => setOpen(true)}>
          Log an application
        </button>
      </div>
    )
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2 className="section-title" style={{ marginTop: 0 }}>
        Log an application
      </h2>

      {error && <div className="alert error">{error}</div>}

      <div className="filter-grid">
        <label className="field">
          <span>Company</span>
          <input value={form.company} onChange={set('company')} maxLength={200} required />
        </label>
        <label className="field">
          <span>Position</span>
          <input value={form.position} onChange={set('position')} maxLength={300} required />
        </label>
        <label className="field">
          <span>Stage</span>
          <select value={form.status} onChange={set('status')}>
            {APPLICATION_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Date applied</span>
          <input
            type="date"
            value={form.applied_date}
            max={localToday()}
            onChange={set('applied_date')}
            required
          />
        </label>
        <label className="field">
          <span>Link to the posting (optional)</span>
          <input type="url" value={form.url} onChange={set('url')} placeholder="https://…" />
        </label>
        <label className="field">
          <span>Location (optional)</span>
          <input value={form.location} onChange={set('location')} maxLength={255} />
        </label>
        <label className="field">
          <span>Next step (optional)</span>
          <input
            value={form.next_action}
            onChange={set('next_action')}
            maxLength={255}
            placeholder="e.g. Follow up with the recruiter"
          />
        </label>
        <label className="field">
          <span>By (optional)</span>
          <input type="date" value={form.next_action_date} onChange={set('next_action_date')} />
        </label>
      </div>

      <label className="field">
        <span>Notes (optional)</span>
        <textarea rows={3} value={form.notes} onChange={set('notes')} maxLength={10000} />
      </label>

      <div className="job-actions" style={{ marginTop: 0 }}>
        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save application'}
        </button>
        <button className="btn" type="button" disabled={busy} onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  )
}
