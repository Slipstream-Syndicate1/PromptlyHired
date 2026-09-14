import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import ApplyLink from '../components/ApplyLink.jsx'
import { statusLabel } from '../lib/applicationStatus.js'

/**
 * The record of work done: every job you applied to, and every job you
 * generated a resume or cover letter for.
 *
 * Both come from the same rows the board and the job page use, so a job
 * applied to without generating anything is still logged here.
 */

function formatDate(value) {
  if (!value) return ''
  const date = value.length === 10 ? new Date(`${value}T12:00:00`) : new Date(value)
  return date.toLocaleDateString()
}

export default function History() {
  const [entries, setEntries] = useState([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .history()
      .then(setEntries)
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false))
  }, [])

  const applied = entries.filter((entry) => entry.application).length

  return (
    <main className="page">
      <div className="page-header">
        <h1>History</h1>
        <span className="count-pill">
          {entries.length} logged{applied > 0 ? ` · ${applied} applied` : ''}
        </span>
      </div>

      {error && <div className="alert error">{error}</div>}
      {busy && <div className="empty">Loading…</div>}

      {!busy && entries.length === 0 && (
        <div className="empty">
          <h2>Nothing logged yet</h2>
          <p>
            Mark a job as applied, or generate a resume or cover letter for one, and it
            will be kept here.
          </p>
          <Link className="btn primary" to="/jobs">Browse jobs</Link>
        </div>
      )}

      {entries.map((entry) => (
        <article className="card" key={entry.job.id}>
          <div className="job-top">
            <div className="job-main">
              <h3 className="job-title">
                <Link to={`/jobs/${entry.job.id}`}>{entry.job.title}</Link>
              </h3>
              <p className="job-company">
                {entry.job.company.name}
                {entry.job.location ? ` · ${entry.job.location}` : ''}
              </p>
            </div>
          </div>

          <div className="job-meta">
            {entry.application && (
              <span className="chip met">
                {statusLabel(entry.application.status)}
                {entry.application.applied_date
                  ? ` · applied ${formatDate(entry.application.applied_date)}`
                  : ''}
              </span>
            )}
            {entry.last_generated_at && (
              <span className="chip">Prepared {formatDate(entry.last_generated_at)}</span>
            )}
            {entry.documents.map((doc) => (
              <Link className="chip analysed" key={doc.id} to={`/documents/${doc.id}`}>
                {doc.kind === 'resume' ? '📄 Resume' : '✉ Cover letter'}
                {doc.edited_content ? ' (edited)' : ''}
              </Link>
            ))}
            {entry.application?.needs_follow_up && <span className="chip">Needs follow-up</span>}
          </div>

          {/* Still the only route to actually applying. */}
          <div className="job-actions">
            <ApplyLink job={entry.job} variant="view" />
            {!entry.documents.length && (
              <Link className="btn" to={`/jobs/${entry.job.id}`}>
                Prepare documents
              </Link>
            )}
          </div>
        </article>
      ))}
    </main>
  )
}
