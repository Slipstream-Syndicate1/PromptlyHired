import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import JobCard from './JobCard.jsx'

/**
 * Live jobs from Adzuna and Himalayas, with search and filters.
 *
 * Searching is explicit (the Search button or Enter), not on every keystroke:
 * uncached searches spend a limited free API quota. Typing still filters the
 * jobs you added yourself instantly, through onSearchChange.
 */

const JOB_TYPES = [
  ['', 'Any type'],
  ['full_time', 'Full-time'],
  ['part_time', 'Part-time'],
  ['contract', 'Contract'],
]

const POSTED_WITHIN = [
  ['', 'Any time'],
  ['1', 'Past 24 hours'],
  ['7', 'Past week'],
  ['30', 'Past month'],
]

const NO_FILTERS = { q: '', location: '', job_type: '', remote_only: false, posted_within_days: '' }

function sameFilters(a, b) {
  return Object.keys(NO_FILTERS).every((key) => a[key] === b[key])
}

export default function JobFeed({ onSearchChange }) {
  const [form, setForm] = useState(NO_FILTERS)
  // The search the results on screen belong to, so "Load more" continues it
  // even if the form has been edited since.
  const [applied, setApplied] = useState(NO_FILTERS)
  const [jobs, setJobs] = useState([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [sources, setSources] = useState([])
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const latestRequest = useRef(0)

  const run = useCallback(async (filters, nextPage) => {
    const requestId = ++latestRequest.current
    if (nextPage === 1) setLoading(true)
    else setLoadingMore(true)
    setError('')
    try {
      const result = await api.jobFeed({
        ...filters,
        remote_only: filters.remote_only || undefined,
        page: nextPage,
      })
      // A newer search started while this one was in flight.
      if (requestId !== latestRequest.current) return
      setJobs((current) =>
        nextPage === 1
          ? result.jobs
          : [...current, ...result.jobs.filter((job) => !current.some((c) => c.id === job.id))],
      )
      setPage(result.page)
      setHasMore(result.has_more)
      setSources(result.sources)
      setNotice(result.notice || '')
    } catch (err) {
      if (requestId === latestRequest.current) setError(err.message)
    } finally {
      if (requestId === latestRequest.current) {
        setLoading(false)
        setLoadingMore(false)
      }
    }
  }, [])

  useEffect(() => {
    run(NO_FILTERS, 1)
  }, [run])

  const set = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm((current) => ({ ...current, [key]: value }))
    if (key === 'q') onSearchChange?.(value)
  }

  const submit = (event) => {
    event.preventDefault()
    setApplied(form)
    run(form, 1)
  }

  const clear = () => {
    setForm(NO_FILTERS)
    setApplied(NO_FILTERS)
    onSearchChange?.('')
    run(NO_FILTERS, 1)
  }

  const toggleSave = async (job) => {
    const next = !job.is_saved
    const mark = (value) =>
      setJobs((current) => current.map((j) => (j.id === job.id ? { ...j, is_saved: value } : j)))
    mark(next)
    try {
      await (next ? api.saveJob(job.id) : api.unsaveJob(job.id))
    } catch (err) {
      mark(!next)
      setError(err.message)
    }
  }

  const filtering = !sameFilters(applied, NO_FILTERS)
  const remoteOnlyResults = sources.length === 1 && sources[0] === 'himalayas' && !applied.remote_only

  return (
    <section aria-labelledby="job-feed-title">
      <h2 className="section-title" id="job-feed-title" style={{ marginTop: 0 }}>
        Find jobs
      </h2>

      <form className="card" role="search" onSubmit={submit}>
        <label className="field">
          <span>Search</span>
          <input
            type="search"
            value={form.q}
            onChange={set('q')}
            placeholder="Job title, skill or company"
            maxLength={200}
            enterKeyHint="search"
          />
        </label>

        <div className="filter-grid">
          <label className="field">
            <span>Location</span>
            <input
              value={form.location}
              onChange={set('location')}
              placeholder={form.remote_only ? 'Not needed for remote roles' : 'City or region'}
              maxLength={120}
              disabled={form.remote_only}
            />
          </label>
          <label className="field">
            <span>Job type</span>
            <select value={form.job_type} onChange={set('job_type')}>
              {JOB_TYPES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Posted</span>
            <select value={form.posted_within_days} onChange={set('posted_within_days')}>
              {POSTED_WITHIN.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label
            className="field"
            style={{ flexDirection: 'row', alignItems: 'center', gap: 10, alignSelf: 'end' }}
          >
            <input
              type="checkbox"
              checked={form.remote_only}
              onChange={set('remote_only')}
              style={{ width: 'auto', margin: 0 }}
            />
            <span style={{ margin: 0 }}>Remote only</span>
          </label>
        </div>

        <div className="job-actions" style={{ marginTop: 0 }}>
          <button className="btn primary" type="submit" disabled={loading}>
            {loading ? 'Searching…' : 'Search'}
          </button>
          {(filtering || !sameFilters(form, NO_FILTERS)) && (
            <button className="btn" type="button" onClick={clear} disabled={loading}>
              Clear
            </button>
          )}
        </div>
      </form>

      {notice && <div className="alert info">{notice}</div>}
      {error && <div className="alert error">{error}</div>}

      {loading ? (
        <div className="empty">Finding jobs…</div>
      ) : jobs.length === 0 ? (
        !error && (
          <div className="empty">
            <h2>No jobs found</h2>
            <p>Try a broader search, a different location, or fewer filters.</p>
          </div>
        )
      ) : (
        <>
          <p className="fine-print">
            Showing {jobs.length} job{jobs.length === 1 ? '' : 's'}
            {filtering ? ' for your search' : ', newest first'}.
            {remoteOnlyResults && ' Only remote roles are available right now.'}
          </p>
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} onToggleSave={toggleSave} />
          ))}
          {hasMore && (
            <button
              className="btn block"
              type="button"
              onClick={() => run(applied, page + 1)}
              disabled={loadingMore}
            >
              {loadingMore ? 'Loading…' : 'Load more jobs'}
            </button>
          )}
        </>
      )}

      <p className="fine-print">
        Listings from{' '}
        <a href="https://www.adzuna.ca" target="_blank" rel="noopener noreferrer">
          Adzuna
        </a>{' '}
        and{' '}
        <a href="https://himalayas.app" target="_blank" rel="noopener noreferrer">
          Himalayas
        </a>
        . Apply buttons open the original listing.
      </p>
    </section>
  )
}
