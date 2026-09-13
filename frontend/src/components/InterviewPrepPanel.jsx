import { useEffect, useState } from 'react'
import { api } from '../api/client'
import './InterviewPrep.css'

/**
 * Interview prep for one application, shown once it reaches the interview stage.
 *
 * The plan is written once and saved, so opening this page again is free. The
 * free AI tier allows about 20 requests a day, so nothing is generated until the
 * user asks, and "Write it again" warns that it spends another one.
 */

function List({ items, className = '' }) {
  return (
    <ul className={className}>
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  )
}

export default function InterviewPrepPanel({ application }) {
  const [prep, setPrep] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    api
      .interviewPrep(application.id)
      .then((saved) => {
        if (!cancelled) setPrep(saved)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [application.id])

  const plan = async (refresh) => {
    setBusy(true)
    setError('')
    try {
      setPrep(await api.planInterview(application.id, refresh))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const content = prep?.content

  return (
    <>
      <h2 className="section-title">Interview prep</h2>
      <div className="card prep-card">
        {error && <div className="alert error">{error}</div>}

        {loading ? (
          <div className="empty" role="status">
            Loading…
          </div>
        ) : !content ? (
          <>
            <p className="job-company" style={{ marginBottom: 12 }}>
              You have an interview for this job. PromptlyHired can plan it from the advert
              and your resume: what to prepare, what they are likely to ask, and what to ask
              them.
            </p>
            <button className="btn primary" disabled={busy} onClick={() => plan(false)}>
              {busy ? 'Planning…' : 'Plan my interview'}
            </button>
            <p className="fine-print">
              Uses one AI request, then it is saved, so coming back here is free.
            </p>
          </>
        ) : (
          <>
            {content.summary && <p className="prep-summary">{content.summary}</p>}

            {content.focus_areas.length > 0 && (
              <section className="prep-section">
                <h3>What to prepare</h3>
                {content.focus_areas.map((area, i) => (
                  <div className="prep-focus" key={i}>
                    <strong>{area.topic}</strong>
                    {area.why && <p className="job-company">{area.why}</p>}
                    {area.actions.length > 0 && <List items={area.actions} />}
                  </div>
                ))}
              </section>
            )}

            {content.likely_questions.length > 0 && (
              <section className="prep-section">
                <h3>They are likely to ask</h3>
                {content.likely_questions.map((item, i) => (
                  <div className="prep-question" key={i}>
                    <strong>{item.question}</strong>
                    {item.how_to_answer && <p className="job-company">{item.how_to_answer}</p>}
                  </div>
                ))}
              </section>
            )}

            {content.questions_to_ask.length > 0 && (
              <section className="prep-section">
                <h3>Ask them</h3>
                <List items={content.questions_to_ask} />
              </section>
            )}

            {content.watch_outs.length > 0 && (
              <section className="prep-section">
                <h3>Be ready for</h3>
                <List items={content.watch_outs} />
              </section>
            )}

            <div className="job-actions">
              <button
                className="btn"
                disabled={busy}
                onClick={() => {
                  const confirmed = window.confirm(
                    'Write a new plan? This replaces the current one and uses another AI request.',
                  )
                  if (confirmed) plan(true)
                }}
              >
                {busy ? 'Writing…' : 'Write it again'}
              </button>
            </div>
            <p className="fine-print">
              Written by AI from this advert and your resume on{' '}
              {new Date(prep.generated_at).toLocaleDateString()}. Check it against what you
              actually know — it is preparation, not a prediction of how the interview will go.
            </p>
          </>
        )}
      </div>
    </>
  )
}
