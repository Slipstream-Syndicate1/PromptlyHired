import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import AddJobForm from '../components/AddJobForm.jsx'
import JobFeed from '../components/JobFeed.jsx'
import JobCard from '../components/JobCard.jsx'
import LogApplication from '../components/LogApplication.jsx'

/**
 * The main page. There is no job feed: every job-board API is paid,
 * partner-only or retired, and bulk-scraping them is against their terms. So
 * jobs enter one at a time, by the user pasting a link to one they found.
 */
export default function Jobs() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState([])
  const [resume, setResume] = useState(null)
  // What is typed in the feed search box also filters the jobs you added.
  const [search, setSearch] = useState('')
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.listJobs(), api.getActiveResume()])
      .then(([j, r]) => {
        setJobs(j)
        setResume(r)
      })
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false))
  }, [])

  const onAdded = (job) => {
    setJobs((current) => [job, ...current.filter((j) => j.id !== job.id)])
    navigate(`/jobs/${job.id}`)
  }

  const toggleSave = async (job) => {
    const next = !job.is_saved
    setJobs((c) => c.map((j) => (j.id === job.id ? { ...j, is_saved: next } : j)))
    try {
      await (next ? api.saveJob(job.id) : api.unsaveJob(job.id))
    } catch (err) {
      setJobs((c) => c.map((j) => (j.id === job.id ? { ...j, is_saved: !next } : j)))
      setError(err.message)
    }
  }

  const needle = search.trim().toLowerCase()
  const shownJobs = needle
    ? jobs.filter((job) =>
        `${job.title} ${job.company.name} ${job.location || ''}`.toLowerCase().includes(needle),
      )
    : jobs

  return (
    <main className="page">
      <div className="page-header">
        <h1>Jobs</h1>
      </div>

      {!busy && !resume && (
        <div className="alert info">
          <strong>Upload your resume first.</strong> Matching and document
          generation are both built on it. <Link to="/profile">Go to Profile →</Link>
        </div>
      )}

      <JobFeed onSearchChange={setSearch} />

      <AddJobForm onAdded={onAdded} />
      <LogApplication />

      {error && <div className="alert error">{error}</div>}
      {busy && <div className="empty">Loading…</div>}

      {!busy && jobs.length === 0 && (
        <div className="empty">
          <h2>No jobs yet</h2>
          <p>
            Found a role you like? Paste its link above and we’ll score it against
            your resume and write you a tailored application.
          </p>
        </div>
      )}

      {jobs.length > 0 && <h2 className="section-title">Your jobs</h2>}
      {jobs.length > 0 && shownJobs.length === 0 && (
        <p className="fine-print">None of the jobs you added match “{search.trim()}”.</p>
      )}
      {shownJobs.map((job) => (
        <JobCard key={job.id} job={job} onToggleSave={toggleSave} />
      ))}
    </main>
  )
}
