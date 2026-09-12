import { useState } from 'react'
import ApplyLink from './ApplyLink.jsx'
import CompanyLogo from './CompanyLogo.jsx'
import JobModal from './JobModal.jsx'
import { matchBand } from '../lib/matchBand.js'
import './JobCard.css'

/**
 * A job in a list: company, role, match, the skills you have and are missing,
 * and the link to the posting. Clicking the card opens the full job in a
 * dialog over the page.
 *
 * The match figures come from a cached analysis and stay blank until the job is
 * opened. Scoring is one AI request per job and the free tier allows only a few
 * a minute, so a whole list is never scored at once.
 *
 * The card owns its dialog, so every page that lists jobs gets it unchanged.
 */
export default function JobCard({ job: listedJob, onToggleSave }) {
  const [open, setOpen] = useState(false)
  // Results from the dialog (a new match, a generated document) show on the
  // card straight away, without the page refetching its list.
  const [updates, setUpdates] = useState({})
  const job = { ...listedJob, ...updates }

  const analysed = job.match_percentage !== null && job.match_percentage !== undefined
  const band = analysed ? matchBand(job.match_percentage) : null

  const openFromCard = (event) => {
    // The Apply link and the title button handle their own clicks.
    if (event.target.closest('a, button')) return
    setOpen(true)
  }

  return (
    <>
      <article className="card jc-card" onClick={openFromCard}>
        <div className="jc-top">
          <CompanyLogo company={job.company} />
          <div className="jc-main">
            <p className="jc-company">{job.company.name}</p>
            <h3 className="jc-title">
              <button
                type="button"
                className="jc-open"
                aria-haspopup="dialog"
                onClick={() => setOpen(true)}
              >
                {job.title}
              </button>
            </h3>
          </div>
          <div className="jc-score" data-band={band?.key}>
            {analysed ? (
              <>
                <span className="jc-score-value">{job.match_percentage}%</span>
                <span className="jc-score-label">match</span>
              </>
            ) : (
              <span className="jc-score-label">Open to see your match</span>
            )}
          </div>
        </div>

        <dl className="jc-skills">
          <div>
            <dt>Skills you have</dt>
            <dd data-tone={analysed ? 'met' : undefined}>
              {analysed ? `✓ ${job.requirements_met_count}` : '—'}
            </dd>
          </div>
          <div>
            <dt>Skills missing</dt>
            <dd data-tone={analysed ? 'missing' : undefined}>
              {analysed ? `△ ${job.requirements_missing_count}` : '—'}
            </dd>
          </div>
        </dl>

        <div className="jc-footer">
          <ApplyLink job={job} />
          {job.is_saved && <span className="chip">♥ Saved</span>}
        </div>
      </article>

      {open && (
        <JobModal
          job={job}
          onClose={() => setOpen(false)}
          onToggleSave={onToggleSave}
          onJobUpdate={(changes) => setUpdates((current) => ({ ...current, ...changes }))}
        />
      )}
    </>
  )
}
