import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import JobCard from './JobCard.jsx'
import './RecommendedJobs.css'

/**
 * "Recommended for you": the best few jobs for the skills in the active resume.
 *
 * The list arrives ranked by the skills each job mentions, which costs nothing.
 * The top AI_SCORED of those are then AI-scored one at a time through the normal
 * match analysis, and only the SHOWN with the highest match % are displayed.
 *
 * Each score is cached, so reopening costs nothing. The free AI tier allows
 * about 20 requests a day per model, so jobs that already have a score are
 * skipped and scoring stops at the first quota error.
 */

const AI_SCORED = 6
const SHOWN = 3

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

/** Highest match % first; jobs without a score yet keep their skill-fit order after them. */
function bestFirst(items) {
  return [...items].sort((a, b) => {
    const left = a.job.match_percentage
    const right = b.job.match_percentage
    if (left != null && right != null) return right - left
    if (left != null) return -1
    if (right != null) return 1
    return 0
  })
}

function basedOn(data) {
  if (!data.searched_titles.length) return ''
  const where = data.location ? ` in ${data.location}` : ''
  const remote = data.include_remote ? ', including remote' : ''
  return `Based on ${data.searched_titles.join(' and ')}${where}${remote}.`
}

export default function RecommendedJobs() {
  const [data, setData] = useState(null)
  // The AI_SCORED candidates; only the SHOWN best are displayed.
  const [candidates, setCandidates] = useState([])
  const [error, setError] = useState('')
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

      // Only jobs with an advert can be scored.
      const top = result.jobs.filter((item) => item.job.description).slice(0, AI_SCORED)
      setData(result)
      setCandidates(top)

      const toScore = top.filter((item) => item.job.match_percentage == null)
      for (const [index, item] of toScore.entries()) {
        if (cancelled) return
        setScoring({ done: index, total: toScore.length })
        try {
          const match = await api.analyzeMatch(item.job.id)
          if (cancelled) return
          setCandidates((current) =>
            current.map((entry) => (entry.job.id === item.job.id ? withMatch(entry, match) : entry)),
          )
        } catch (err) {
          if (cancelled) return
          setScoreNote(
            err.status === 429
              ? 'The free AI quota is used up for now, so not every job could be scored. These are the best matches so far.'
              : `Some matches could not be scored: ${err.message}`,
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
      setCandidates((current) =>
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

  const shown = bestFirst(candidates).slice(0, SHOWN)

  return (
    <section className="rec" aria-labelledby="recommended-title">
      <div className="rec-head">
        {heading}
        {basedOn(data) && <p className="fine-print rec-based-on">{basedOn(data)}</p>}
      </div>

      {data.notice && <div className="alert info">{data.notice}</div>}
      {error && <div className="alert error">{error}</div>}
      {scoring ? (
        <p className="fine-print" role="status">
          Checking your top {candidates.length} matches with AI… {scoring.done} of {scoring.total}.
          The order may change until every score is in.
        </p>
      ) : (
        candidates.length > SHOWN &&
        !scoreNote && (
          <p className="fine-print">
            Your {SHOWN} best matches out of the {candidates.length} jobs checked.
          </p>
        )
      )}
      {scoreNote && <p className="fine-print">{scoreNote}</p>}

      {candidates.length === 0 && !data.notice && (
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
    </section>
  )
}
