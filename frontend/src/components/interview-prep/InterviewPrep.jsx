import { useRef, useState } from 'react'
import PrepSetup from './PrepSetup.jsx'
import PrepChecklist from './PrepChecklist.jsx'
import PrepChat from './PrepChat.jsx'
import './interview-prep.css'

/** The calendar route supplies trusted context and persistence actions.
 * Mount with key={`${userId}:${interviewId}`} to isolate interview/account state.
 * See docs/interview-prep-integration.md for the boundary contract.
 */
export default function InterviewPrep({ context, initialPlan = null, actions }) {
  const [plan, setPlan] = useState(initialPlan)
  const [type, setType] = useState(context.interviewType || 'not_sure')
  const initialMinutes = initialPlan?.dailyMinutes
  const [budget, setBudget] = useState(initialMinutes
    ? [30, 60, 120].includes(initialMinutes) ? String(initialMinutes) : 'custom' : '')
  const [custom, setCustom] = useState(initialMinutes ? String(initialMinutes) : '')
  const [available, setAvailable] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saveError, setSaveError] = useState('')
  const [pending, setPending] = useState(new Set())
  const generation = useRef(null)
  const generating = useRef(false)
  const saving = useRef(new Set())
  const minutes = Number(budget === 'custom' ? custom : budget)
  const date = new Date(context.startsAt)
  const validDate = Boolean(context.startsAt) && Number.isFinite(date.getTime())
  const now = new Date()
  const expired = validDate && date <= now
  const dayFormat = new Intl.DateTimeFormat('en-CA', { timeZone: context.timezone })
  const sameDay = validDate && dayFormat.format(date) === dayFormat.format(now)
  const sameDayMinutes = Number(available)
  const valid = validDate && !expired && Number.isInteger(minutes) && minutes >= 15 && minutes <= 480
    && (!sameDay || (Number.isInteger(sameDayMinutes) && sameDayMinutes > 0
      && sameDayMinutes <= minutes && sameDayMinutes <= Math.floor((date - now) / 60000)))

  async function generate(event) {
    event.preventDefault()
    if (!valid || generating.current || saving.current.size) return
    generating.current = true
    setBusy(true)
    setError('')
    const payload = { daily_minutes: minutes, interview_type: type, regenerate: Boolean(plan),
      ...(sameDay ? { same_day_minutes: sameDayMinutes } : {}) }
    const fingerprint = JSON.stringify(payload)
    if (generation.current?.fingerprint !== fingerprint) {
      generation.current = { fingerprint, id: crypto.randomUUID() }
    }
    try {
      setPlan(await actions.generate({ ...payload, client_request_id: generation.current.id }))
      generation.current = null
      setSaveError('')
    } catch (err) {
      setError(err.message || 'Could not create your checklist. Try again.')
    } finally {
      generating.current = false
      setBusy(false)
    }
  }

  async function toggle(task) {
    if (saving.current.has(task.id) || generating.current) return
    saving.current.add(task.id)
    setPending(new Set(saving.current))
    setSaveError('')
    const completed = !task.completed
    setPlan((current) => ({ ...current, tasks: current.tasks.map((item) =>
      item.id === task.id ? { ...item, completed } : item) }))
    try {
      await actions.setCompleted(plan.id, task.id, completed)
    } catch (err) {
      setPlan((current) => ({ ...current, tasks: current.tasks.map((item) =>
        item.id === task.id ? { ...item, completed: task.completed } : item) }))
      setSaveError(err.message || 'Could not save progress. Please try again.')
    } finally {
      saving.current.delete(task.id)
      setPending(new Set(saving.current))
    }
  }

  return <div className="prep-workspace">
    <header className="prep-hero">
      <span className="prep-eyebrow">YOUR NEXT CONVERSATION</span>
      <h1>Go in with a plan.</h1>
      <p>{context.title} · {context.company}</p>
      {validDate && <p><time dateTime={context.startsAt}>{new Intl.DateTimeFormat(undefined, {
        dateStyle: 'full', timeStyle: 'short', timeZone: context.timezone,
      }).format(date)}</time> · {context.timezone}</p>}
    </header>
    {!validDate && <p className="alert info">Schedule your interview in the calendar before creating a plan.</p>}
    {expired && <p className="alert info">This interview time has passed. Your saved preparation is still available.</p>}
    {!context.hasResume && <p className="alert info">This plan will use the job description. Add a resume to personalize it with your experience.</p>}
    {plan?.outdated && <p className="alert info">Your interview details have changed. Update your plan when you’re ready; your previous version stays saved.</p>}
    {plan?.summary && <p>{plan.summary}</p>}
    {plan?.hasMoreDays && <p className="alert info">This checklist covers only the dates shown, up to 14 preparation days. Return after this window and update your plan for the remaining time.</p>}
    {error && <p className="alert error" role="alert">{error}</p>}
    <PrepSetup type={type} setType={setType} budget={budget} setBudget={setBudget}
      custom={custom} setCustom={setCustom} sameDay={sameDay} available={available}
      setAvailable={setAvailable} sameDayLimit={Math.max(0, Math.min(minutes || 480, Math.floor((date - now) / 60000)))} valid={valid && pending.size === 0} busy={busy}
      hasPlan={Boolean(plan)} onSubmit={generate} />
    {busy && <p role="status">Prioritizing topics within your available time…</p>}
    {plan && <div className="prep-columns">
      <PrepChecklist tasks={plan.tasks} pending={pending} onToggle={toggle} error={saveError} />
      <PrepChat key={plan.id} planId={plan.id} initialMessages={plan.messages}
        sendMessage={actions.sendMessage} disabled={busy} />
    </div>}
  </div>
}
