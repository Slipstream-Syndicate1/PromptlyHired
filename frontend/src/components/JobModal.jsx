import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import ApplyLink from './ApplyLink.jsx'
import CompanyLogo from './CompanyLogo.jsx'
import MatchPanel from './MatchPanel.jsx'
import './JobCard.css'

/**
 * The full job, opened from a card, over a dimmed page.
 *
 * Opening a job is what triggers its match analysis. Only jobs the user
 * actually looks at spend an AI request, and the result is cached, so reopening
 * is free. The dialog traps focus, closes on Escape or a click on the dim
 * background, and hands focus back to whatever opened it.
 */

const JOB_TYPE_LABELS = {
  full_time: 'Full-time',
  part_time: 'Part-time',
  contract: 'Contract',
  remote: 'Remote',
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'

function formatDate(isoDate) {
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function JobModal({ job, onClose, onToggleSave, onJobUpdate }) {
  const navigate = useNavigate()
  const dialogRef = useRef(null)
  const closeButtonRef = useRef(null)
  const [detail, setDetail] = useState(null)
  const [match, setMatch] = useState(null)
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [analysing, setAnalysing] = useState(false)
  const [matchError, setMatchError] = useState('')
  const [generating, setGenerating] = useState(null)
  const [error, setError] = useState('')

  // Callbacks from the card are recreated every render; refs keep the effects
  // below from re-running (and re-fetching) because of that.
  const onCloseRef = useRef(onClose)
  const onJobUpdateRef = useRef(onJobUpdate)
  useEffect(() => {
    onCloseRef.current = onClose
    onJobUpdateRef.current = onJobUpdate
  })

  const analyse = useCallback(
    async (refresh = false) => {
      setAnalysing(true)
      setMatchError('')
      try {
        const result = await api.analyzeMatch(job.id, refresh)
        setMatch(result)
        onJobUpdateRef.current?.({
          match_percentage: result.match_percentage,
          requirements_met_count: result.requirements_met.length,
          requirements_missing_count: result.requirements_missing.length,
        })
      } catch (err) {
        setMatchError(err.message)
      } finally {
        setAnalysing(false)
      }
    },
    [job.id],
  )

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const loaded = await api.getJob(job.id)
        // Also stops React's development double-mount from analysing twice.
        if (cancelled) return
        setDetail(loaded)
        setMatch(loaded.match)
        setDocuments(loaded.documents)
        setLoading(false)
        if (!loaded.match && loaded.job.description) analyse(false)
      } catch (err) {
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [job.id, analyse])

  // Focus, Escape, focus trap and background scroll lock.
  useEffect(() => {
    const previouslyFocused = document.activeElement
    closeButtonRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab' || !dialogRef.current) return
      const items = [...dialogRef.current.querySelectorAll(FOCUSABLE)].filter(
        (el) => el.offsetParent !== null,
      )
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      previouslyFocused?.focus?.()
    }
  }, [])

  const generate = async (kind) => {
    setGenerating(kind)
    setError('')
    try {
      const doc = await api.generateDocument(job.id, { kind })
      onJobUpdateRef.current?.({ has_documents: true })
      navigate(`/documents/${doc.id}`)
    } catch (err) {
      setError(err.message)
      setGenerating(null)
    }
  }

  const current = detail?.job ?? job
  const hasAdvert = Boolean(current.description)
  const needsResume = /resume/i.test(matchError)
  const titleId = `job-dialog-title-${job.id}`

  return createPortal(
    // Portal events still bubble to the card in React, so they stop here.
    <div
      className="jm-scrim"
      onClick={(event) => {
        event.stopPropagation()
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className="jm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        ref={dialogRef}
      >
        <header className="jm-header">
          <CompanyLogo company={current.company} size="lg" />
          <div className="jm-heading">
            <p className="jc-company">{current.company.name}</p>
            <h2 id={titleId} className="jm-title">
              {current.title}
            </h2>
            <div className="job-meta">
              {current.location && <span className="chip">{current.location}</span>}
              {current.job_type && (
                <span className="chip">{JOB_TYPE_LABELS[current.job_type]}</span>
              )}
              {current.salary_range && <span className="chip salary">{current.salary_range}</span>}
              {current.posted_date && (
                <span className="chip">Posted {formatDate(current.posted_date)}</span>
              )}
              {current.source_publisher && (
                <span className="chip">via {current.source_publisher}</span>
              )}
            </div>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="jm-close"
            onClick={onClose}
            aria-label="Close job details"
          >
            ×
          </button>
        </header>

        <div className="jm-body">
          <div className="jm-actions">
            <ApplyLink job={current} />
            {onToggleSave && (
              <button
                type="button"
                className={job.is_saved ? 'btn on' : 'btn'}
                aria-pressed={job.is_saved}
                onClick={() => onToggleSave(job)}
              >
                {job.is_saved ? '♥ Saved' : '♡ Save job'}
              </button>
            )}
            {hasAdvert && (
              <>
                <button
                  type="button"
                  className="btn primary"
                  disabled={Boolean(generating)}
                  onClick={() => generate('resume')}
                >
                  {generating === 'resume' ? 'Writing resume…' : 'Create resume'}
                </button>
                <button
                  type="button"
                  className="btn primary"
                  disabled={Boolean(generating)}
                  onClick={() => generate('cover_letter')}
                >
                  {generating === 'cover_letter' ? 'Writing cover letter…' : 'Create cover letter'}
                </button>
              </>
            )}
          </div>
          {generating && (
            <p className="fine-print" role="status">
              Tailoring it to this job. This can take up to a minute.
            </p>
          )}
          {error && <div className="alert error">{error}</div>}

          {loading ? (
            <div className="empty" role="status">
              Loading job…
            </div>
          ) : hasAdvert ? (
            matchError && !analysing ? (
              <>
                <h2 className="section-title">Your match</h2>
                <div className="alert info">
                  {matchError}{' '}
                  {needsResume && (
                    <Link to="/profile" onClick={onClose}>
                      Upload your resume →
                    </Link>
                  )}
                </div>
                {!needsResume && (
                  <button type="button" className="btn" onClick={() => analyse(false)}>
                    Try again
                  </button>
                )}
              </>
            ) : analysing && !match ? (
              <>
                <h2 className="section-title">Your match</h2>
                <div className="card jm-analysing" role="status">
                  Comparing this job with your resume…
                </div>
              </>
            ) : (
              <MatchPanel
                match={match}
                analysing={analysing}
                onAnalyse={() => analyse(false)}
                onReanalyse={() => analyse(true)}
              />
            )
          ) : (
            <div className="alert info">
              This job was logged by hand, so there is no job description to match your
              resume against or to tailor documents to.
            </div>
          )}

          {documents.length > 0 && (
            <>
              <h2 className="section-title">Your documents for this job</h2>
              {documents.map((doc) => (
                <div className="list-row" key={doc.id}>
                  <div className="job-main">
                    <div className="job-title">
                      {doc.kind === 'resume' ? 'Resume' : 'Cover letter'}
                    </div>
                    <p className="job-company">{new Date(doc.created_at).toLocaleDateString()}</p>
                  </div>
                  <Link className="btn" to={`/documents/${doc.id}`} onClick={onClose}>
                    Open
                  </Link>
                </div>
              ))}
            </>
          )}

          {hasAdvert && (
            <>
              <h2 className="section-title">Job description</h2>
              <div className="card job-description jm-description">{current.description}</div>
            </>
          )}

          <p className="fine-print">
            <Link to={`/jobs/${job.id}`} onClick={onClose}>
              Open the full page
            </Link>{' '}
            to track your application for this job.
          </p>
        </div>
      </div>
    </div>,
    document.body,
  )
}
