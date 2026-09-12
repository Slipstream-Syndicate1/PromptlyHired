import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { DndContext, PointerSensor, useDraggable, useDroppable, useSensor, useSensors } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { api } from '../api/client'
import AddJobForm from '../components/AddJobForm.jsx'
import ApplyLink from '../components/ApplyLink.jsx'
import { exactDateTime, relativeTime } from '../lib/relativeTime.js'

// Order is the left-to-right column order on the board. Wishlist isn't a
// status - it's the existing Saved feature, shown here as the "not applied
// yet" bucket, so there's only ever one "interested in this job" mechanism.
const STAGES = [
  { key: 'wishlist', label: 'Wishlist', hint: 'Not applied yet' },
  { key: 'applied', label: 'Applied', hint: 'Waiting to hear back' },
  { key: 'interview', label: 'Interview', hint: 'In the process' },
  { key: 'offer', label: 'Offer', hint: 'Decision time' },
  { key: 'rejected', label: 'Rejected', hint: 'Closed out' },
]

function jobsInStage(jobs, stageKey) {
  return stageKey === 'wishlist'
    ? jobs.filter((j) => j.is_saved && !j.status)
    : jobs.filter((j) => j.status === stageKey)
}

// Sorts the whole board at once, then each column is a filtered slice - so
// ordering stays consistent whichever stage a card is in. Wishlist jobs have
// no status_updated_at/applied_at, so those fall back to 0 (epoch) rather
// than producing an unstable NaN comparison.
const SORTS = {
  recent: {
    label: 'Recently moved',
    compare: (a, b) => new Date(b.status_updated_at || 0) - new Date(a.status_updated_at || 0),
  },
  applied_desc: {
    label: 'Applied (newest first)',
    compare: (a, b) => new Date(b.applied_at || 0) - new Date(a.applied_at || 0),
  },
  applied_asc: {
    label: 'Applied (oldest first)',
    compare: (a, b) => new Date(a.applied_at || 0) - new Date(b.applied_at || 0),
  },
  company: {
    label: 'Company (A–Z)',
    compare: (a, b) => a.company.name.localeCompare(b.company.name),
  },
  title: {
    label: 'Job title (A–Z)',
    compare: (a, b) => a.title.localeCompare(b.title),
  },
}

const EVENT_TYPES = [
  { value: 'interview', label: 'Interview' },
  { value: 'deadline', label: 'Deadline' },
  { value: 'opens', label: 'Applications open' },
  { value: 'other', label: 'Other' },
]

// Chip colour per event type. Interview is the Interview column's blue so
// the word means one colour on this board; there's deliberately no legend -
// every chip carries its type in text, colour is only reinforcement.
const EVENT_COLORS = { interview: 'blue', deadline: 'gold', opens: 'green', other: 'slate' }

const eventColor = (type) => EVENT_COLORS[type] || 'slate'
const eventLabel = (type) => EVENT_TYPES.find((t) => t.value === type)?.label || 'Event'

function EventEditor({ job, onSave, onCancel }) {
  // Wishlist jobs default to "applications open" - an interview isn't the
  // likely next event for a job you haven't applied to yet.
  const [type, setType] = useState(job.next_event_type || (job.status ? 'interview' : 'opens'))
  const [date, setDate] = useState(job.next_event_at ? job.next_event_at.slice(0, 10) : '')
  const [note, setNote] = useState(job.next_event_note || '')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    if (!date) return
    setBusy(true)
    await onSave({
      next_event_at: new Date(`${date}T09:00:00`).toISOString(),
      next_event_type: type,
      next_event_note: note || null,
    })
    setBusy(false)
  }

  return (
    <form className="tracking-event-form" onSubmit={submit}>
      {/* Stacked, not the app-wide .filter-grid: that switches to 2 columns
          on viewport width, but a tracking column stays ~250px wide even on
          a full desktop screen - a viewport breakpoint doesn't know that. */}
      <label className="field">
        <span>Type</span>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {EVENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Date</span>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
      </label>
      <label className="field">
        <span>Note (optional)</span>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={300}
          placeholder="e.g. Final round with hiring manager"
        />
      </label>
      <div className="job-actions" style={{ marginTop: 0 }}>
        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save'}
        </button>
        {job.next_event_at && (
          <button
            className="btn"
            type="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true)
              await onSave({ next_event_at: null })
            }}
          >
            Clear
          </button>
        )}
        <button className="btn link" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

function TrackingCard({ job, onRemove, onSaveEvent }) {
  const [editingEvent, setEditingEvent] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: job.id,
  })

  useEffect(() => {
    if (!menuOpen) return
    const onClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [menuOpen])

  const saveEvent = async (payload) => {
    await onSaveEvent(job, payload)
    setEditingEvent(false)
  }

  return (
    <article
      ref={setNodeRef}
      className={`card tracking-card${isDragging ? ' dragging' : ''}`}
      style={{ transform: CSS.Translate.toString(transform) }}
    >
      {/* A dedicated handle, not the whole card, so the title link stays clickable. */}
      <button className="tracking-drag-handle" {...listeners} {...attributes} aria-label="Drag to move">
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <circle cx="9" cy="6" r="1.6" /><circle cx="15" cy="6" r="1.6" />
          <circle cx="9" cy="12" r="1.6" /><circle cx="15" cy="12" r="1.6" />
          <circle cx="9" cy="18" r="1.6" /><circle cx="15" cy="18" r="1.6" />
        </svg>
      </button>

      <h3 className="job-title">
        <Link to={`/jobs/${job.id}`}>{job.title}</Link>
      </h3>
      <p className="job-company">
        {job.company.name}
        {job.location ? ` · ${job.location}` : ''}
      </p>

      <div className="job-meta">
        {job.applied_at && (
          <span className="chip" title={exactDateTime(job.applied_at)}>
            Applied {relativeTime(job.applied_at)}
          </span>
        )}
        {/* Redundant with "Applied" on the Applied column itself - only
            useful once a card has actually moved somewhere further along. */}
        {job.status && job.status !== 'applied' && job.status_updated_at && (
          <span className="chip" title={exactDateTime(job.status_updated_at)}>
            Moved {relativeTime(job.status_updated_at)}
          </span>
        )}
        {job.match_percentage != null && <span className="chip">{job.match_percentage}% match</span>}
        {job.has_documents && <span className="chip analysed">📄 Documents</span>}
        {job.next_event_at && !editingEvent && (
          <button
            className={`chip event event-${eventColor(job.next_event_type)}${
              new Date(job.next_event_at).getTime() < Date.now() ? ' overdue' : ''
            }`}
            onClick={() => setEditingEvent(true)}
            title={`${eventLabel(job.next_event_type)} · ${exactDateTime(job.next_event_at)}`}
          >
            <i className="legend-dot" aria-hidden="true" />
            {eventLabel(job.next_event_type)} {relativeTime(job.next_event_at)}
            {job.next_event_note ? ` · ${job.next_event_note}` : ''}
          </button>
        )}
      </div>

      {editingEvent ? (
        <EventEditor job={job} onSave={saveEvent} onCancel={() => setEditingEvent(false)} />
      ) : (
        <div className="tracking-card-actions">
          <ApplyLink job={job} variant="view" />
          {/* Always the same icon in the same place, whatever's inside it -
              rather than icons popping in or out depending on card state.
              Moving between stages is drag-only, so nothing "move to X"
              lives here; un-saving is the one thing drag can't do. */}
          <div className="tracking-card-menu" ref={menuRef}>
            <button
              className="icon-btn"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label="More actions"
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              title="More actions"
            >
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <circle cx="12" cy="5" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="12" cy="19" r="2" />
              </svg>
            </button>
            {menuOpen && (
              <div className="tracking-card-menu-list" role="menu">
                <button
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false)
                    setEditingEvent(true)
                  }}
                >
                  {job.next_event_at ? 'Edit event' : 'Add event'}
                </button>
                <button
                  role="menuitem"
                  className="danger"
                  onClick={() => {
                    setMenuOpen(false)
                    onRemove(job)
                  }}
                >
                  Remove from tracking
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </article>
  )
}

function UpcomingSidebar({ jobs }) {
  const now = Date.now()
  const upcoming = jobs
    .filter((j) => j.next_event_at)
    .sort((a, b) => new Date(a.next_event_at) - new Date(b.next_event_at))

  return (
    <aside className="card tracking-upcoming">
      <div className="section-heading-row">
        <div>
          <span className="calendar-kicker">Stay on track</span>
          <h2>Coming up</h2>
        </div>
        <span>{upcoming.length}</span>
      </div>

      {upcoming.length === 0 ? (
        <p className="calendar-empty">
          Nothing coming up. Add an interview or deadline from any tracked job&rsquo;s menu.
        </p>
      ) : (
        <ul className="upcoming-list">
          {upcoming.map((job) => {
            const overdue = new Date(job.next_event_at).getTime() < now
            return (
              <li key={job.id} className={`upcoming-item${overdue ? ' overdue' : ''}`}>
                <Link to={`/jobs/${job.id}`} title={exactDateTime(job.next_event_at)}>
                  <i className={`legend-dot ${eventColor(job.next_event_type)}`} aria-hidden="true" />
                  <span className="upcoming-body">
                    <strong>{job.title}</strong>
                    <span className="upcoming-meta">
                      {job.company.name} · {relativeTime(job.next_event_at)}
                      {overdue ? ' · Overdue' : ''}
                    </span>
                    {job.next_event_note && <small>{job.next_event_note}</small>}
                  </span>
                  <span className="upcoming-type">{eventLabel(job.next_event_type)}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </aside>
  )
}

function ColumnAdd({ stage, onAdded }) {
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <div className="tracking-add-job-row">
        <button className="btn tracking-add-job" onClick={() => setOpen(true)}>
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" />
          </svg>
          <span>Add a job</span>
        </button>
      </div>
    )
  }

  return (
    <div className="tracking-add-job-form">
      <AddJobForm
        compact
        onAdded={async (job) => {
          await onAdded(job, stage.key)
          setOpen(false)
        }}
      />
      <button className="btn link" type="button" onClick={() => setOpen(false)}>
        Cancel
      </button>
    </div>
  )
}

function Column({ stage, jobs, onRemove, onSaveEvent, onAddJob }) {
  const { setNodeRef, isOver } = useDroppable({ id: stage.key })

  return (
    <section className={`tracking-column stage-${stage.key}${isOver ? ' over' : ''}`}>
      <div className="tracking-column-head">
        <div>
          <h2>{stage.label}</h2>
          <p>{stage.hint}</p>
        </div>
        <span className="tracking-count">{jobs.length}</span>
      </div>
      <ColumnAdd stage={stage} onAdded={onAddJob} />
      <div className="tracking-column-body" ref={setNodeRef}>
        {jobs.length === 0 && <p className="tracking-drop-hint">Drop a job here</p>}
        {jobs.map((job) => (
          <TrackingCard
            key={job.id}
            job={job}
            onRemove={onRemove}
            onSaveEvent={onSaveEvent}
          />
        ))}
      </div>
    </section>
  )
}

/**
 * A kanban board: Wishlist (saved, no status yet), then the application
 * pipeline. Nothing here is inferred - the app does not apply on the user's
 * behalf, so a job only reaches a status column when the user says so, and
 * only moves when they drag it or report what happened.
 */
export default function Tracking() {
  const [jobs, setJobs] = useState([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [sortKey, setSortKey] = useState('recent')
  // No activation constraint: drags start from a dedicated handle, so there
  // is no click-vs-drag ambiguity to disambiguate, and any distance/delay
  // threshold just reads as lag.
  const sensors = useSensors(useSensor(PointerSensor))

  const sortedJobs = useMemo(
    () => [...jobs].sort(SORTS[sortKey].compare),
    [jobs, sortKey],
  )

  useEffect(() => {
    api
      .tracking()
      .then(setJobs)
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false))
  }, [])

  // stageKey is one of STAGES' keys, including 'wishlist' (which clears
  // status rather than setting it, and ensures the job is saved first).
  const moveToStage = async (job, stageKey) => {
    const previous = jobs
    const nextStatus = stageKey === 'wishlist' ? null : stageKey
    setJobs((current) =>
      current.map((j) =>
        j.id === job.id ? { ...j, status: nextStatus, is_saved: j.is_saved || stageKey === 'wishlist' } : j,
      ),
    )
    try {
      if (stageKey === 'wishlist' && !job.is_saved) {
        await api.saveJob(job.id)
      }
      const updated = await api.setJobStatus(job.id, nextStatus)
      setJobs((current) => current.map((j) => (j.id === job.id ? updated : j)))
    } catch (err) {
      setJobs(previous)
      setError(err.message)
    }
  }

  // On every card's menu, regardless of column: clears status (if any) and
  // un-saves (if saved), so the job is fully off the board either way - not
  // just recycled back to Wishlist, which drag already covers.
  const removeFromBoard = async (job) => {
    const previous = jobs
    setJobs((current) => current.filter((j) => j.id !== job.id))
    try {
      if (job.status) await api.setJobStatus(job.id, null)
      if (job.is_saved) await api.unsaveJob(job.id)
    } catch (err) {
      setJobs(previous)
      setError(err.message)
    }
  }

  const onDragEnd = ({ active, over }) => {
    if (!over) return
    const job = jobs.find((j) => j.id === active.id)
    if (!job) return
    const currentStageKey = job.status || 'wishlist'
    if (currentStageKey === over.id) return
    moveToStage(job, over.id)
  }

  const saveEvent = async (job, payload) => {
    const previous = jobs
    setJobs((current) => current.map((j) => (j.id === job.id ? { ...j, ...payload } : j)))
    try {
      const updated = await api.setJobEvent(job.id, payload)
      setJobs((current) => current.map((j) => (j.id === job.id ? updated : j)))
    } catch (err) {
      setJobs(previous)
      setError(err.message)
    }
  }

  // A job pasted directly into any column: the same add-a-job flow as the
  // Jobs page, then immediately placed in whichever column it was added
  // from - Wishlist saves it, a status column sets that status right away
  // (useful for backfilling an application you forgot to log).
  const addJobToStage = async (job, stageKey) => {
    try {
      if (stageKey === 'wishlist') {
        await api.saveJob(job.id)
        setJobs((current) => [{ ...job, is_saved: true }, ...current])
      } else {
        const updated = await api.setJobStatus(job.id, stageKey)
        setJobs((current) => [updated, ...current])
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const inProgress = jobs.filter((j) => j.status === 'applied' || j.status === 'interview').length
  const offers = jobs.filter((j) => j.status === 'offer').length
  const upcomingCount = jobs.filter((j) => j.next_event_at).length

  return (
    <main className="page tracking-page">
      <div className="page-header tracking-header">
        <div>
          <h1>Tracking</h1>
          <p className="page-subtitle">Every application in one place, from wishlist to offer.</p>
        </div>
        <Link className="btn" to="/jobs">Add a job</Link>
      </div>

      {error && <div className="alert error">{error}</div>}
      {busy && <div className="empty">Loading…</div>}

      {!busy && (
        <>
          <section className="dashboard-stats tracking-stats" aria-label="Tracking overview">
            <div><strong>{jobs.length}</strong><span>Tracked</span></div>
            <div><strong>{inProgress}</strong><span>In progress</span></div>
            <div><strong>{offers}</strong><span>Offers</span></div>
            <div><strong>{upcomingCount}</strong><span>Upcoming events</span></div>
          </section>

          <div className="tracking-layout">
            <section className="tracking-board" aria-label="Application board">
              {/* Board-level controls live on the board, like the calendar's
                  month toolbar lives on the calendar - not up in the page
                  header where they read as page-level actions. */}
              <div className="tracking-toolbar">
                <label className="tracking-sort">
                  <span>Sort by</span>
                  <select
                    value={sortKey}
                    onChange={(e) => setSortKey(e.target.value)}
                    disabled={jobs.length === 0}
                  >
                    {Object.entries(SORTS).map(([key, { label }]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </label>
                <span className="tracking-toolbar-hint">Drag cards between columns to update their status</span>
              </div>
              <DndContext sensors={sensors} onDragEnd={onDragEnd}>
                <div className="tracking-columns">
                  {STAGES.map((stage) => (
                    <Column
                      key={stage.key}
                      stage={stage}
                      jobs={jobsInStage(sortedJobs, stage.key)}
                      onRemove={removeFromBoard}
                      onSaveEvent={saveEvent}
                      onAddJob={addJobToStage}
                    />
                  ))}
                </div>
              </DndContext>
            </section>

            <UpcomingSidebar jobs={jobs} />
          </div>
        </>
      )}
    </main>
  )
}
