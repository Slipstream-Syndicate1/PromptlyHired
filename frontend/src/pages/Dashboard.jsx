import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'

const ACTIONS = [
  {
    to: '/jobs',
    title: 'Jobs',
    description: 'Add a posting, compare it with your resume, and build a tailored application.',
    icon: 'briefcase',
    cta: 'View jobs',
  },
  {
    to: '/profile',
    title: 'Resume',
    description: 'Upload or update the resume PromptlyHired uses to score every opportunity.',
    icon: 'document',
    cta: 'Manage resume',
  },
  {
    to: '/saved',
    title: 'Saved jobs',
    description: 'Come back to the opportunities you shortlisted and want to focus on.',
    icon: 'heart',
    cta: 'View saved',
  },
  {
    to: '/tracking',
    title: 'Tracking',
    description: 'See every application on a kanban board, from Applied through to Offer.',
    icon: 'tracking',
    cta: 'View tracking',
  },
]

// Order matters here: it is the left-to-right progression through the pipeline.
const STAGES = [
  { key: 'applied', label: 'Applied' },
  { key: 'interview', label: 'Interview' },
  { key: 'offer', label: 'Offer' },
  { key: 'rejected', label: 'Rejected' },
]

function ActionIcon({ name }) {
  const paths = {
    briefcase: 'M9 6V4h6v2h4a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4Zm2 0h2V5h-2v1Zm-6 5v6h14v-6h-5v2h-4v-2H5Zm7 0v-1h-1v1h1Z',
    document: 'M6 2h8l5 5v15H6V2Zm8 2.5V8h3.5L14 4.5ZM8 12v2h8v-2H8Zm0 4v2h8v-2H8Z',
    heart: 'M12 20.3 10.6 19C6 14.9 3.5 12.6 3.5 9.8 3.5 7.5 5.3 5.8 7.5 5.8c1.3 0 2.5.6 3.3 1.5l1.2 1.4 1.2-1.4a4.4 4.4 0 0 1 3.3-1.5c2.2 0 4 1.7 4 4 0 2.8-2.5 5.1-7.1 9.2L12 20.3Z',
    tracking: 'M3 4h5v16H3V4ZM10.5 9h5v11h-5V9ZM17 6h5v14h-5V6Z',
  }
  return <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d={paths[name]} /></svg>
}

export default function Dashboard() {
  const { user } = useAuth()
  const [jobs, setJobs] = useState([])
  const [resume, setResume] = useState(null)
  const [tracked, setTracked] = useState([])

  useEffect(() => {
    Promise.all([api.listJobs(), api.getActiveResume(), api.tracking()])
      .then(([jobList, activeResume, trackedJobs]) => {
        setJobs(jobList)
        setResume(activeResume)
        setTracked(trackedJobs)
      })
      .catch(() => {})
  }, [])

  const firstName = user?.name?.trim()?.split(/\s+/)[0]
  const savedCount = jobs.filter((job) => job.is_saved).length

  return (
    <main className="page dashboard-page">
      <section className="dashboard-hero">
        <div className="dashboard-eyebrow">PROMPTLYHIRED</div>
        <h1>{firstName ? `Welcome back, ${firstName}.` : 'Welcome back.'}</h1>
        <p>Keep your job search moving. Choose where you want to pick up today.</p>
        <Link className="btn primary dashboard-primary" to="/jobs">Add or match a job →</Link>
      </section>

      <section className="dashboard-stats" aria-label="Job search overview">
        <div><strong>{jobs.length}</strong><span>Jobs</span></div>
        <div><strong>{savedCount}</strong><span>Saved</span></div>
        <div><strong>{resume ? 'Ready' : 'Missing'}</strong><span>Resume</span></div>
      </section>

      {tracked.length > 0 && (
        <>
          <div className="dashboard-section-head">
            <div>
              <h2>Application pipeline</h2>
              <p>Where your tracked applications stand right now.</p>
            </div>
            <Link className="btn" to="/tracking">Open board →</Link>
          </div>

          <section className="dashboard-stats dashboard-pipeline" aria-label="Application pipeline">
            {STAGES.map((stage) => (
              <div key={stage.key}>
                <strong>{tracked.filter((job) => job.status === stage.key).length}</strong>
                <span>{stage.label}</span>
              </div>
            ))}
          </section>
        </>
      )}

      <div className="dashboard-section-head">
        <div>
          <h2>What would you like to do?</h2>
          <p>Everything you need for your next application is one click away.</p>
        </div>
      </div>

      <section className="dashboard-grid">
        {ACTIONS.map((action) => (
          <Link className="dashboard-action" to={action.to} key={action.title}>
            <div className="dashboard-action-icon"><ActionIcon name={action.icon} /></div>
            <div className="dashboard-action-copy">
              <h3>{action.title}</h3>
              <p>{action.description}</p>
              <span>{action.cta} →</span>
            </div>
          </Link>
        ))}
      </section>

      {!resume && (
        <section className="dashboard-tip">
          <div>
            <strong>Start with your resume</strong>
            <p>Upload one before matching jobs so PromptlyHired can give you useful scores and tailored documents.</p>
          </div>
          <Link className="btn" to="/profile">Upload resume</Link>
        </section>
      )}
    </main>
  )
}
