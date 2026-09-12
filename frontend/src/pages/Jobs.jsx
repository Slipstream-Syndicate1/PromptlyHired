import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import AddJobForm from '../components/AddJobForm.jsx'
import JobCard from '../components/JobCard.jsx'

/**
 * The main page. There is no job feed: every job-board API is paid,
 * partner-only or retired, and bulk-scraping them is against their terms. So
 * jobs enter one at a time, by the user pasting a link to one they found.
 */
export default function Jobs() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState([])
  const [resume, setResume] = useState(null)
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

  const markApplied = async (job) => {
    const previous = jobs
    setJobs((c) => c.map((j) => (j.id === job.id ? { ...j, status: 'applied' } : j)))
    try {
      const updated = await api.setJobStatus(job.id, 'applied')
      setJobs((c) => c.map((j) => (j.id === job.id ? updated : j)))
    } catch (err) {
      setJobs(previous)
      setError(err.message)
    }
  }

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

      <AddJobForm onAdded={onAdded} />

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
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} onToggleSave={toggleSave} onMarkApplied={markApplied} />
      ))}
    </main>
  )
}
