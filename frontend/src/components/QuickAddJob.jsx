import { useState } from 'react'
import { api } from '../api/client'

/**
 * The tracking board's add-a-job: paste a link, or type a title and company.
 * No description - this is for logging a job you're tracking, not one you
 * want analysed. The Jobs page's AddJobForm is the full version.
 */
export default function QuickAddJob({ onAdded, onCancel }) {
  const [mode, setMode] = useState('url')
  const [url, setUrl] = useState('')
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
          : await api.addJobManual({ title, company, url: url || undefined })
      setUrl('')
      setTitle('')
      setCompany('')
      await onAdded(job)
    } catch (err) {
      setError(err.message)
      // A blocked fetch shouldn't be a dead end: switch to typing it in,
      // keeping the link for the Apply button.
      if (mode === 'url' && /blocked|could not find|not be reached/i.test(err.message)) {
        setMode('manual')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card quick-add-job" onSubmit={submit}>
      <div className="quick-add-modes">
        <button type="button" className={mode === 'url' ? 'btn on' : 'btn'} onClick={() => setMode('url')}>
          Paste a link
        </button>
        <button type="button" className={mode === 'manual' ? 'btn on' : 'btn'} onClick={() => setMode('manual')}>
          Enter details
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}

      {mode === 'url' ? (
        <label className="field">
          <span>Job posting URL</span>
          <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" required />
        </label>
      ) : (
        <>
          <label className="field">
            <span>Job title</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} required />
          </label>
          <label className="field">
            <span>Company</span>
            <input value={company} onChange={(e) => setCompany(e.target.value)} maxLength={200} required />
          </label>
          <label className="field">
            <span>Link (optional)</span>
            <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
          </label>
        </>
      )}

      <div className="quick-add-actions">
        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? 'Adding…' : 'Add'}
        </button>
        <button className="btn link" type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </form>
  )
}
