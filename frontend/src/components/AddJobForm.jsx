import { useState } from 'react'
import { api } from '../api/client'

/**
 * Paste a link, or paste the text: the Jobs page's add-a-job, where the
 * description matters because matching is built on it. The tracking board
 * has its own lighter QuickAddJob.
 */
export default function AddJobForm({ onAdded }) {
  const [mode, setMode] = useState('url')
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const job =
        mode === 'url'
          ? await api.addJobFromUrl(url)
          : await api.addJobFromText({ text, title, company, url: url || undefined })
      setUrl('')
      setText('')
      setTitle('')
      setCompany('')
      await onAdded(job)
    } catch (err) {
      setError(err.message)
      // Sites that block server-side fetches are common enough that the
      // fallback should be offered rather than explained.
      if (mode === 'url' && /blocked|could not find|not be reached/i.test(err.message)) {
        setMode('text')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2 className="section-title" style={{ marginTop: 0 }}>
        Add a job
      </h2>

      <div className="job-actions" style={{ marginTop: 0, marginBottom: 12 }}>
        <button
          type="button"
          className={mode === 'url' ? 'btn on' : 'btn'}
          onClick={() => setMode('url')}
        >
          Paste a link
        </button>
        <button
          type="button"
          className={mode === 'text' ? 'btn on' : 'btn'}
          onClick={() => setMode('text')}
        >
          Paste the text
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}

      {mode === 'url' ? (
        <>
          <label className="field">
            <span>Job posting URL</span>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
              required
            />
          </label>
          <p className="fine-print">
            Works with most company careers pages and job boards. Some sites
            (LinkedIn and Indeed among them) block automated fetches — if that
            happens, switch to “Paste the text”.
          </p>
        </>
      ) : (
        <>
          <label className="field">
            <span>Job title</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} />
          </label>
          <label className="field">
            <span>Company</span>
            <input value={company} onChange={(e) => setCompany(e.target.value)} maxLength={200} />
          </label>
          <label className="field">
            <span>Link to the posting (optional, for the Apply button)</span>
            <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} />
          </label>
          <label className="field">
            <span>Job description</span>
            <textarea
              rows={10}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Copy the whole advert and paste it here…"
              required
              minLength={200}
            />
          </label>
        </>
      )}

      <button className="btn primary block" type="submit" disabled={busy}>
        {busy ? 'Reading the job…' : 'Add job'}
      </button>
    </form>
  )
}
