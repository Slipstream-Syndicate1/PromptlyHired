import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'

export default function JobInterviewAction({ job, onUpdate }) {
  const [status, setStatus] = useState(job.status || '')
  const [events, setEvents] = useState([])
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    api.listCalendarEvents().then((items) => { if (active) setEvents(items) })
      .catch((err) => { if (active) setError(err.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [job.id])
  async function change(next) {
    setBusy(true)
    setError('')
    try {
      const updated = await api.setJobStatus(job.id, next || null)
      setStatus(updated.status || '')
      onUpdate(updated)
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  const interviews = events.filter((event) => event.job_id === job.id && event.type === 'interview'
    && event.starts_at && new Date(event.starts_at) > new Date())
    .sort((a,b) => a.starts_at.localeCompare(b.starts_at))
  return <section className="card" aria-label="Application tracking">
    <label className="field"><span>Application status</span>
      <select value={status} disabled={busy} onChange={(event) => change(event.target.value)}>
        <option value="">Not applied</option><option value="applied">Applied</option>
        <option value="interview">Interview</option><option value="offer">Offer</option>
        <option value="rejected">Rejected</option>
      </select>
    </label>
    {error && <p role="alert" className="alert error">{error}</p>}
    {status === 'interview' && <div aria-live="polite">
      <p>Prepare for your interview with a checklist tailored to this job and your available time.</p>
      {loading ? <p role="status">Checking scheduled interviews…</p> : interviews.length
        ? interviews.map((event) => <Link key={event.id} className="btn primary" to={`/interviews/${event.id}/prep`}>Prepare with AI</Link>)
        : <Link className="btn primary" to={`/calendar?job=${job.id}`}>Schedule interview</Link>}
    </div>}
  </section>
}
