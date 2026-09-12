import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  EVENT_TYPES,
  eventTypeLabel,
  eventTypeShortLabel,
  formatEventDate,
  loadCalendarEvents,
  clearLegacyCalendarEvents,
} from "../lib/calendarStore.js";

import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

function useCalendar() {
  const { user } = useAuth();
  const [state, setState] = useState({ account: null, events: [], loading: true, error: "" });
  useEffect(() => {
    let active = true;
    setState({ account: user?.id, events: [], loading: true, error: "" });
    if (!user) return;
    api.listCalendarEvents().then(events => {
      if (active) setState({ account: user.id, events, loading: false, error: "" });
    }).catch(err => { if (active) setState({ account: user.id, events: [], loading: false, error: err.message }); });
    return () => { active = false; };
  }, [user?.id]);
  const setEvents = update => setState(current => ({...current, events: typeof update === "function" ? update(current.events) : update }));
  return { ...state, events: state.account === user?.id ? state.events : [], setEvents };
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const TYPE_COLORS = {
  deadline: "gold",
  interview: "green",
  offer: "blue",
  other: "slate",
};

function monthStart(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function monthLabel(date) {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    year: "numeric",
  }).format(date);
}

function dateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function calendarDays(month) {
  const start = monthStart(month);
  const firstDay = start.getDay();
  const daysInMonth = new Date(
    month.getFullYear(),
    month.getMonth() + 1,
    0,
  ).getDate();
  const total = Math.ceil((firstDay + daysInMonth) / 7) * 7;
  return Array.from({ length: total }, (_, index) => {
    const date = new Date(
      month.getFullYear(),
      month.getMonth(),
      index - firstDay + 1,
    );
    return { date, currentMonth: date.getMonth() === month.getMonth() };
  });
}

function EventPill({ event }) {
  return (
    <div
      className={`calendar-event calendar-event-${TYPE_COLORS[event.type] || "slate"}`}
    >
      <span className="calendar-event-dot" />
      <span>{event.title}</span>
    </div>
  );
}

export function CalendarPreview() {
  const [month] = useState(() => monthStart(new Date()));
  const { events, setEvents, loading, error: loadError } = useCalendar();
  const days = useMemo(() => calendarDays(month), [month]);
  const upcoming = [...events]
    .filter((event) => event.date >= dateKey(new Date()))
    .sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`))
    .slice(0, 3);


  return (
    <section className="dashboard-calendar card" aria-label="Upcoming calendar">
      <div className="dashboard-calendar-heading">
        <div>
          <span className="calendar-kicker">Stay on track</span>
          <h2>{monthLabel(month)}</h2>
        </div>
        <Link to="/calendar" className="text-link">
          View calendar →
        </Link>
      </div>
      <div className="calendar-preview-weekdays">
        {WEEKDAYS.map((day) => (
          <span key={day}>{day.slice(0, 1)}</span>
        ))}
      </div>
      <div className="calendar-preview-grid">
        {days.map(({ date, currentMonth }) => {
          const key = dateKey(date);
          const dayEvents = events.filter((event) => event.date === key);
          return (
            <div
              className={`calendar-preview-day ${currentMonth ? "" : "is-muted"} ${key === dateKey(new Date()) ? "is-today" : ""}`}
              key={key}
            >
              <span>{date.getDate()}</span>
              {dayEvents.length > 0 && (
                <i
                  className={`legend-dot ${TYPE_COLORS[dayEvents[0].type] || "slate"}`}
                />
              )}
            </div>
          );
        })}
      </div>
      <div className="dashboard-upcoming">
        {loading && <p>Loading calendar…</p>}
        {loadError && <p role="alert">{loadError}</p>}
        {loading || loadError ? null : upcoming.length === 0 ? (
          <p>No upcoming deadlines or interviews.</p>
        ) : (
          upcoming.map((event) => (
            <div key={event.id}>
              <i
                className={`legend-dot ${TYPE_COLORS[event.type] || "slate"}`}
              />
              <span>{event.title}</span>
              <time>{formatEventDate(event.date)}</time>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function EventForm({ onAdd, initial, onCancel, jobs, saving }) {
  const [form, setForm] = useState(initial || {
    title: "",
    date: dateKey(new Date()),
    time: "",
    type: "deadline",
    notes: "",
    job_id: "",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  });

  const submit = async (event) => {
    event.preventDefault();
    if (!form.title.trim() || !form.date) return;
    const saved = await onAdd({ title: form.title.trim(), date: form.date, time: form.time || null,
      type: form.type, notes: form.notes || "", timezone: form.timezone,
      job_id: form.type === "interview" && form.job_id ? Number(form.job_id) : null });
    if (saved && !initial) setForm(current => ({...current, title: "", time: "", notes: ""}));
  };

  const update = (field) => (event) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  return (
    <form className="calendar-form card" onSubmit={submit}>
      <div className="calendar-form-heading">
        <div>
          <span className="calendar-kicker">Plan ahead</span>
          <h2>{initial ? "Edit event" : "Add an event"}</h2>
        </div>
        <div className="calendar-form-icon" aria-hidden="true">
          +
        </div>
      </div>
      <label className="field">
        <span>Event name</span>
        <input
          value={form.title}
          onChange={update("title")}
          placeholder="e.g. Final interview"
          maxLength={120}
          required
        />
      </label>
      <div className="filter-grid">
        <label className="field">
          <span>Date</span>
          <input
            type="date"
            value={form.date}
            onChange={update("date")}
            required
          />
        </label>
        <label className="field">
          <span>{form.type === "interview" ? "Time" : "Time (optional)"}</span>
          <input type="time" value={form.time} onChange={update("time")} required={form.type === "interview"} />
        </label>
      </div>
      <label className="field">
        <span>Type</span>
        <select value={form.type} onChange={update("type")}>
          {EVENT_TYPES.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
      </label>
      <p className="muted">Timezone: {form.timezone}</p>
      {form.type === "interview" && <label className="field">
        <span>Linked job</span>
        <select value={form.job_id || ""} onChange={update("job_id")} required>
          <option value="">Select a job</option>
          {jobs.map(job => <option key={job.id} value={job.id}>{job.title} · {job.company}</option>)}
        </select>
      </label>}
      <label className="field">
        <span>Notes (optional)</span>
        <textarea
          rows="3"
          value={form.notes}
          onChange={update("notes")}
          placeholder="Add a useful reminder…"
          maxLength={500}
        />
      </label>
      <button className="btn primary block" type="submit" disabled={saving}>
        {saving ? "Saving…" : initial ? "Save event" : "Add to calendar"}
      </button>
      {initial && <button type="button" className="btn" onClick={onCancel}>Cancel edit</button>}
    </form>
  );
}

export default function Calendar() {
  const [month, setMonth] = useState(() => monthStart(new Date()));
  const { events, setEvents, loading, error: loadError } = useCalendar();

  const { user } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [legacy, setLegacy] = useState(loadCalendarEvents);
  useEffect(() => {
    let active = true;
    setJobs([]); setEditing(null); setError("");
    api.listJobs().then(items => { if (active) setJobs(items); }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [user?.id]);

  const days = useMemo(() => calendarDays(month), [month]);
  const monthEvents = events.filter((event) => {
    const date = new Date(`${event.date}T12:00:00`);
    return (
      date.getFullYear() === month.getFullYear() &&
      date.getMonth() === month.getMonth()
    );
  });
  const upcoming = [...events]
    .filter((event) => event.date >= dateKey(new Date()))
    .sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`))
    .slice(0, 6);

  const addEvent = async (payload) => {
    setSaving(true); setError("");
    try {
      const saved = editing ? await api.updateCalendarEvent(editing.id, payload) : await api.createCalendarEvent(payload);
      setEvents(current => [...current.filter(item => item.id !== saved.id), saved]);
      setEditing(null); return true;
    } catch (err) { setError(err.message); return false; }
    finally { setSaving(false); }
  };
  const removeEvent = async (id) => {
    setSaving(true); setError("");
    try { await api.deleteCalendarEvent(id); setEvents(current => current.filter(event => event.id !== id)); if (editing?.id === id) setEditing(null); }
    catch (err) { setError(err.message); } finally { setSaving(false); }
  };
  const importEvents = async () => {
    setSaving(true); setError("");
    try {
      for (const item of legacy) {
        const saved = await api.createCalendarEvent({ id: item.id, title: item.title, date: item.date, time: item.time || null,
          type: item.type, notes: item.notes || "", job_id: null, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
        setEvents(current => [...current.filter(event => event.id !== saved.id), saved]);
      }
      clearLegacyCalendarEvents(); setLegacy([]);
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  };
  const moveMonth = (amount) =>
    setMonth(
      (current) =>
        new Date(current.getFullYear(), current.getMonth() + amount, 1),
    );

  return (
    <main className="page calendar-page">
      <div className="page-header">
        <div>
          <h1>Calendar</h1>
          <p className="page-subtitle">
            Keep every important application moment in view.
          </p>
        </div>
        <Link className="btn" to="/jobs">
          Add a job
        </Link>
      </div>

      {loading && <p role="status">Loading calendar…</p>}
      {(error || loadError) && <p role="alert">{error || loadError}</p>}
      {legacy.length > 0 && <div className="card"><p>This browser has older calendar events. Import only if they belong to your account.</p><button className="btn" disabled={saving || loading || !!loadError} onClick={importEvents}>Import events from this browser</button></div>}
      <div className="calendar-layout">
        <section
          className="calendar-main card"
          aria-label="Application calendar"
        >
          <div className="calendar-toolbar">
            <div className="calendar-toolbar-actions">
              <button
                className="btn"
                type="button"
                onClick={() => setMonth(monthStart(new Date()))}
              >
                Today
              </button>
              <button
                className="icon-btn"
                type="button"
                onClick={() => moveMonth(-1)}
                aria-label="Previous month"
              >
                ←
              </button>
              <button
                className="icon-btn"
                type="button"
                onClick={() => moveMonth(1)}
                aria-label="Next month"
              >
                →
              </button>
            </div>
            <h2>{monthLabel(month)}</h2>
          </div>
          <div className="calendar-weekdays">
            {WEEKDAYS.map((day) => (
              <span key={day}>{day}</span>
            ))}
          </div>
          <div className="calendar-grid">
            {days.map(({ date, currentMonth }) => {
              const key = dateKey(date);
              const dayEvents = events.filter((event) => event.date === key);
              const today = key === dateKey(new Date());
              return (
                <div
                  className={`calendar-day ${currentMonth ? "" : "is-muted"} ${today ? "is-today" : ""}`}
                  key={key}
                >
                  <span className="calendar-day-number">{date.getDate()}</span>
                  <div className="calendar-day-events">
                    {dayEvents.slice(0, 3).map((event) => (
                      <EventPill event={event} key={event.id} />
                    ))}
                    {dayEvents.length > 3 && (
                      <span className="calendar-more">
                        +{dayEvents.length - 3} more
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="calendar-legend">
            {EVENT_TYPES.map((type) => (
              <span key={type.value}>
                <i className={`legend-dot ${TYPE_COLORS[type.value]}`} />
                {eventTypeShortLabel(type.value)}
              </span>
            ))}
          </div>
        </section>

        <aside className="calendar-side">
          <EventForm key={`${user?.id}-${editing?.id || "new"}`} onAdd={addEvent} initial={editing} onCancel={() => setEditing(null)} jobs={jobs} saving={saving || loading || !!loadError} />
          <section className="upcoming card">
            <div className="section-heading-row">
              <h2>Coming up</h2>
              <span>{upcoming.length}</span>
            </div>
            {loading || loadError ? null : upcoming.length === 0 ? (
              <p className="calendar-empty">
                No upcoming events yet. Add a deadline, interview, or offer date
                to stay on top of your search.
              </p>
            ) : (
              <div className="upcoming-list">
                {upcoming.map((event) => (
                  <article className="upcoming-item" key={event.id}>
                    <i
                      className={`legend-dot ${TYPE_COLORS[event.type] || "slate"}`}
                    />
                    <div>
                      <strong>{event.title}</strong>
                      <span>
                        {formatEventDate(event.date)}
                        {event.time ? ` · ${event.time}` : ""}
                      </span>
                      <small>{eventTypeLabel(event.type)}</small>
                      <button type="button" className="text-btn" disabled={saving} aria-label={`Edit ${event.title}`} onClick={() => setEditing(event)}>Edit</button>
                      {event.type === "interview" && (event.job_id && event.starts_at ? <Link className="text-link" to={`/interviews/${event.id}/prep`}>Prepare with AI</Link> : <button className="text-btn" disabled={saving} onClick={() => setEditing(event)}>Complete interview details</button>)}
                    </div>
                    <button
                      type="button"
                      className="text-btn"
                      onClick={() => removeEvent(event.id)}
                      disabled={saving}
                      aria-label={`Remove ${event.title}`}
                    >
                      ×
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
