import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import ApplyLink from '../components/ApplyLink.jsx'
import ApplicationPanel from '../components/ApplicationPanel.jsx'
import InterviewPrepPanel from '../components/InterviewPrepPanel.jsx'
import MatchPanel from '../components/MatchPanel.jsx'

export default function JobDetail() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')
  const [analysing, setAnalysing] = useState(false)
  const [generating, setGenerating] = useState(null)

  const load = useCallback(async () => {
    try {
      setDetail(await api.getJob(jobId))
    } catch (err) {
      setError(err.message)
    }
  }, [jobId])

  useEffect(() => {
    load()
  }, [load])

  // Explicit, never automatic: each analysis is a paid API call.
  const analyse = async (refresh = false) => {
    setAnalysing(true)
    setError('')
    try {
      const match = await api.analyzeMatch(jobId, refresh)
      setDetail((d) => ({ ...d, match }))
    } catch (err) {
      setError(err.message)
    } finally {
      setAnalysing(false)
    }
  }

  const generate = async (kind) => {
    setGenerating(kind)
    setError('')
    try {
      const doc = await api.generateDocument(jobId, { kind })
      navigate(`/documents/${doc.id}`)
    } catch (err) {
      setError(err.message)
      setGenerating(null)
    }
  }

  // An exact copy of the master resume to edit for this job. No AI.
  const startFromMaster = async () => {
    setGenerating('master')
    setError('')
    try {
      const doc = await api.copyMasterResume(jobId)
      navigate(`/documents/${doc.id}`)
    } catch (err) {
      setError(err.message)
      setGenerating(null)
    }
  }

  if (error && !detail) {
    return (
      <main className="page">
        <div className="alert error">{error}</div>
        <Link className="btn" to="/jobs">
          ‹ Back to jobs
        </Link>
      </main>
    )
  }
  if (!detail) return <main className="page"><div className="empty">Loading…</div></main>

  const { job, match, documents } = detail

  return (
    <main className="page">
      <div className="page-header">
        <h1>{job.title}</h1>
        <button className="count-pill btn link" onClick={() => navigate(-1)}>
          ‹ Back
        </button>
      </div>

      <div className="card">
        <p className="job-company">
          <strong>{job.company.name}</strong>
          {job.location ? ` · ${job.location}` : ''}
        </p>
        {job.company.short_description && (
          <p className="job-blurb">{job.company.short_description}</p>
        )}
        <div className="job-meta">
          {job.salary_range && <span className="chip salary">{job.salary_range}</span>}
          {job.posted_date && <span className="chip">Posted {job.posted_date}</span>}
        </div>
        <div className="job-actions">
          <ApplyLink job={job} />
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      <ApplicationPanel
        key={detail.application?.id ?? 'new'}
        jobId={job.id}
        application={detail.application}
        onChange={(application) => setDetail((d) => ({ ...d, application }))}
      />

      {/* Only once there is an interview to prepare for. */}
      {detail.application?.status === 'interview' && (
        <InterviewPrepPanel application={detail.application} />
      )}

      {job.description ? (
        <>
          <MatchPanel
            match={match}
            analysing={analysing}
            onAnalyse={() => analyse(false)}
            onReanalyse={() => analyse(true)}
          />

          <h2 className="section-title">Tailored documents</h2>
          <div className="card">
            <p className="job-company" style={{ marginBottom: 12 }}>
              Tailor your master resume to this advert with AI, or start from an exact copy
              of your master resume and edit it yourself. Either way you review and edit
              before exporting — nothing is sent anywhere on your behalf, and your master
              resume is never changed.
            </p>
            <div className="job-actions" style={{ marginTop: 0 }}>
              <button
                className="btn primary"
                disabled={Boolean(generating)}
                onClick={() => generate('resume')}
              >
                {generating === 'resume' ? 'Tailoring…' : 'Tailor resume with AI'}
              </button>
              <button
                className="btn"
                disabled={Boolean(generating)}
                onClick={startFromMaster}
              >
                {generating === 'master' ? 'Copying…' : 'Start from master resume'}
              </button>
              <button
                className="btn primary"
                disabled={Boolean(generating)}
                onClick={() => generate('cover_letter')}
              >
                {generating === 'cover_letter' ? 'Writing…' : 'Generate cover letter'}
              </button>
            </div>

            {documents.length > 0 && (
              <div style={{ marginTop: 14 }}>
                {documents.map((doc) => (
                  <div className="list-row" key={doc.id}>
                    <div className="job-main">
                      <div className="job-title">
                        {doc.kind === 'resume' ? 'Resume' : 'Cover letter'}
                        {doc.edited_content && <span className="chip"> edited</span>}
                      </div>
                      <p className="job-company">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <Link className="btn" to={`/documents/${doc.id}`}>
                      Open
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="alert info">
          This job was logged by hand, so there is no advert to match your resume
          against or tailor documents to. Paste the advert on the Jobs page to use
          those features.
        </div>
      )}

      {job.description && (
        <>
          <h2 className="section-title">Original posting</h2>
          <div className="card job-description">{job.description}</div>
        </>
      )}
    </main>
  )
}
