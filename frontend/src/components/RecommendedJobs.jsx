import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import JobCard from './JobCard.jsx'
import './RecommendedJobs.css'

/**
 * "Recommended for you": jobs that fit the skills in the active resume.
 *
 * The list arrives ranked by the skills each job mentions, which costs nothing.
 * The top few are then AI-scored one at a time through the normal match
 * analysis, so each score is cached and reopening costs nothing. The free AI
 * tier allows about 20 requests a day per model, so only AI_SCORED jobs are
 * scored automatically, jobs that already have a score are skipped, and
 * scoring stops at the first quota error.
 */

const SHOWN_AT_FIRST = 6
const AI_SCORED = 5

function withMatch(item, match) {
  return {
    ...item,
    job: {
      ...item.job,
      match_percentage: match.match_percentage,
      requirements_met_count: match.requirements_met.length,
      requirements_missing_count: match.requirements_missing.length,
    },
  }
}

function basedOn(data) {
  if (!data.searched_titles.length) return ''
  const where = data.location ? ` in ${data.location}` : ''
  const remote = data.include_remote ? ', including remote' : ''
  return `Based on ${data.searched_titles.join(' and ')}${where}${remote}.`
}

export default function RecommendedJobs() {
  const [data, setData] = useState(null)
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [scoring, setScoring] = useState(null)
  const [scoreNote, setScoreNote] = useState('')

  useEffect(() => {
    // Stops React's development double-mount from scoring everything twice.
    let cancelled = false

    ;(async () => {
      let result
      try {
        result = await api.recommendedJobs()
      } catch (err) {
        if (!cancelled) setError(err.message)
        return
      }
      if (cancelled) return
      setData(result)
      setItems(result.jobs)

      const toScore = result.jobs
        .slice(0, AI_SCORED)
        .filter((item) => item.job.match_percentage == null && item.job.description)
      for (const [index, item] of toScore.entries()) {
        if (cancelled) return
        setScoring({ done: index, total: toScore.length })
        try {
          const match = await api.analyzeMatch(item.job.id)
          if (cancelled) return
          setItems((current) =>
            current.map((entry) => (entry.job.id === item.job.id ? withMatch(entry, match) : entry)),
          )
        } catch (err) {
          if (cancelled) return
          setScoreNote(
            err.status === 429
              ? 'The free AI quota is used up for now, so some top matches have no AI score yet. Open a job to try again later.'
              : `Some top matches could not be scored: ${err.message}`,
          )
          break
        }
      }
      if (!cancelled) setScoring(null)
    })()

    return () => {
      cancelled = true
    }
  }, [])

  const toggleSave = async (job) => {
    const next = !job.is_saved
    const mark = (value) =>
      setItems((current) =>
        current.map((entry) =>
          entry.job.id === job.id ? { ...entry, job: { ...entry.job, is_saved: value } } : entry,
        ),
      )
    mark(next)
    try {
      await (next ? api.saveJob(job.id) : api.unsaveJob(job.id))
    } catch (err) {
      mark(!next)
      setError(err.message)
    }
  }

  const heading = (
    <h2 className="section-title rec-title" id="recommended-title">
      Recommended for you
    </h2>
  )

  if (error && !data) {
    return (
      <section className="rec" aria-labelledby="recommended-title">
        {heading}
        <div className="alert error">{error}</div>
      </section>
    )
  }

  if (!data) {
    return (
      <section className="rec" aria-labelledby="recommended-title">
        {heading}
        <div className="empty" role="status">
          Finding jobs that fit your resume…
        </div>
      </section>
    )
  }

  const shown = showAll ? items : items.slice(0, SHOWN_AT_FIRST)

  return (
    <section className="rec" aria-labelledby="recommended-title">
      <div className="rec-head">
        {heading}
        {basedOn(data) && <p className="fine-print rec-based-on">{basedOn(data)}</p>}
      </div>

      {data.notice && <div className="alert info">{data.notice}</div>}
      {error && <div className="alert error">{error}</div>}
      {scoring && (
        <p className="fine-print" role="status">
          Scoring your top matches with AI… {scoring.done} of {scoring.total}
        </p>
      )}
      {scoreNote && <p className="fine-print">{scoreNote}</p>}

      {items.length === 0 && !data.notice && (
        <div className="empty">
          <p>
            No recommendations right now. Try adding job titles to your skill profile, or
            changing your preferred location, on the <Link to="/profile">Profile</Link> page.
          </p>
        </div>
      )}

      {shown.map((item) => (
        <div className="rec-item" key={item.job.id}>
          <p className="rec-reason">
            {item.matched_skills.length > 0 ? (
              <>
                Matches {item.matched_skills.length} of your skills:{' '}
                {item.matched_skills.slice(0, 5).join(', ')}
                {item.matched_skills.length > 5 ? '…' : ''}
              </>
            ) : (
              'Matches a role on your resume'
            )}
          </p>
          <JobCard job={item.job} onToggleSave={toggleSave} />
        </div>
      ))}

      {items.length > SHOWN_AT_FIRST && (
        <button className="btn block" type="button" onClick={() => setShowAll((value) => !value)}>
          {showAll ? 'Show fewer' : `Show ${items.length - SHOWN_AT_FIRST} more`}
        </button>
      )}
    </section>
  )
}
