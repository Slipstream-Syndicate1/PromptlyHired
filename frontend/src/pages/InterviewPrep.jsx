import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../api/client'
import InterviewPrep from '../components/interview-prep/InterviewPrep.jsx'

function PreparationLoader({ interviewId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let cancelled = false
    setError('')
    api.getInterviewPrep(interviewId).then((result) => {
      if (!cancelled) setData(result)
    }).catch((err) => { if (!cancelled) setError(err.message) })
    return () => { cancelled = true }
  }, [interviewId, attempt])

  return <main className="page" style={{ maxWidth: 1280 }}>
    <Link to="/calendar">← Back to calendar</Link>
    {error && <><p className="alert error" role="alert">{error}</p>
      <button className="btn" onClick={() => setAttempt((value) => value + 1)}>Retry</button></>}
    {!data && !error && <p role="status">Loading interview preparation…</p>}
    {data && <InterviewPrep context={data.context} initialPlan={data.plan} actions={{
      generate: (payload) => api.generateInterviewPrep(interviewId, payload),
      setCompleted: api.setPrepTaskCompleted,
      sendMessage: api.sendPrepMessage,
    }} />}
  </main>
}

export default function InterviewPrepPage() {
  const { interviewId } = useParams()
  const { user } = useAuth()
  return <PreparationLoader key={`${user.id}:${interviewId}`} interviewId={interviewId} />
}
