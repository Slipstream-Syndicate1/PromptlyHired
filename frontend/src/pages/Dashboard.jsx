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
    description: 'Upload or update the resume JobTrail uses to score every opportunity.',
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
    to: '/history',
    title: 'Application history',
    description: 'Review the resumes and application documents you have generated.',
    icon: 'history',
    cta: 'View history',
  },
]

function ActionIcon({ name }) {
  const paths = {
    briefcase: 'M9 6V4h6v2h4a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4Zm2 0h2V5h-2v1Zm-6 5v6h14v-6h-5v2h-4v-2H5Zm7 0v-1h-1v1h1Z',
    document: 'M6 2h8l5 5v15H6V2Zm8 2.5V8h3.5L14 4.5ZM8 12v2h8v-2H8Zm0 4v2h8v-2H8Z',
    heart: 'M12 20.3 10.6 19C6 14.9 3.5 12.6 3.5 9.8 3.5 7.5 5.3 5.8 7.5 5.8c1.3 0 2.5.6 3.3 1.5l1.2 1.4 1.2-1.4a4.4 4.4 0 0 1 3.3-1.5c2.2 0 4 1.7 4 4 0 2.8-2.5 5.1-7.1 9.2L12 20.3Z',
    history: 'M13 3a9 9 0 1 0 8.9 10.4l-2-.3A7 7 0 1 1 13 5v3l4.5-4L13 0v3Zm-1 5v5.4l4.2 2.5 1-1.7-3.2-1.9V8h-2Z',
  }
  return <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d={paths[name]} /></svg>
}

export default function Dashboard() {
  const { user } = useAuth()
  const [jobs, setJobs] = useState([])
  const [resume, setResume] = useState(null)

  useEffect(() => {
    Promise.all([api.listJobs(), api.getActiveResume()])
      .then(([jobList, activeResume]) => {
        setJobs(jobList)
        setResume(activeResume)
      })
      .catch(() => {})
  }, [])

  const firstName = user?.name?.trim()?.split(/\s+/)[0]
  const savedCount = jobs.filter((job) => job.is_saved).length

  return (
    <main className="page dashboard-page">
      <section className="dashboard-hero">
        <div className="dashboard-eyebrow">JOBTRAIL</div>
        <h1>{firstName ? `Welcome back, ${firstName}.` : 'Welcome back.'}</h1>
        <p>Keep your job search moving. Choose where you want to pick up today.</p>
        <Link className="btn primary dashboard-primary" to="/jobs">Add or match a job →</Link>
      </section>

      <section className="dashboard-stats" aria-label="Job search overview">
        <div><strong>{jobs.length}</strong><span>Jobs</span></div>
        <div><strong>{savedCount}</strong><span>Saved</span></div>
        <div><strong>{resume ? 'Ready' : 'Missing'}</strong><span>Resume</span></div>
      </section>

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
            <p>Upload one before matching jobs so JobTrail can give you useful scores and tailored documents.</p>
          </div>
          <Link className="btn" to="/profile">Upload resume</Link>
        </section>
      )}
    </main>
  )
}
