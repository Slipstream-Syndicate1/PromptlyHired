import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { exportDocumentPdf } from '../lib/exportPdf.js'
import ResumeEditor from '../components/ResumeEditor.jsx'
import ResumePreview from '../components/ResumePreview.jsx'

// model_used on a resume copied straight from the master resume, without AI.
const MASTER_COPY = 'master-copy'

/**
 * Structured editor for a generated document.
 *
 * Fields and bullet lists rather than one freeform textarea: the document is
 * generated as structured JSON so the export template stays consistent, and
 * editing has to preserve that shape.
 *
 * Reviewing here is also the security backstop - job adverts are untrusted text
 * fed to a model, and a human reads the result before it ever leaves the app.
 */

function TextField({ label, value, onChange, rows = 1 }) {
  return (
    <label className="field">
      <span>{label}</span>
      {rows > 1 ? (
        <textarea rows={rows} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
      )}
    </label>
  )
}

function BulletList({ label, items, onChange }) {
  const update = (i, v) => onChange(items.map((item, idx) => (idx === i ? v : item)))
  const remove = (i) => onChange(items.filter((_, idx) => idx !== i))

  return (
    <div className="field">
      <span>{label}</span>
      {items.map((item, i) => (
        <div className="bullet-row" key={i}>
          <textarea rows={2} value={item} onChange={(e) => update(i, e.target.value)} />
          <button className="btn danger" type="button" onClick={() => remove(i)} aria-label="Remove">
            ×
          </button>
        </div>
      ))}
      <button className="btn" type="button" onClick={() => onChange([...items, ''])}>
        + Add
      </button>
    </div>
  )
}

// The same fields as the master resume, so a job's copy edits exactly like the
// master. Its edits stay on this document and never reach the master.
function ResumeForm({ value, patch }) {
  return <ResumeEditor value={value} onChange={patch} />
}

function CoverLetterForm({ value, patch }) {
  return (
    <>
      <TextField label="Greeting" value={value.greeting} onChange={(v) => patch({ greeting: v })} />
      <BulletList
        label="Paragraphs"
        items={value.paragraphs || []}
        onChange={(paragraphs) => patch({ paragraphs })}
      />
      <TextField label="Closing" value={value.closing} onChange={(v) => patch({ closing: v })} />
    </>
  )
}

export default function DocumentEditor() {
  const { documentId } = useParams()
  const navigate = useNavigate()
  const [doc, setDoc] = useState(null)
  const [draft, setDraft] = useState(null)
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .getDocument(documentId)
      .then((d) => {
        setDoc(d)
        setDraft(d.edited_content ?? d.content)
      })
      .catch((err) => setError(err.message))
  }, [documentId])

  const patch = (changes) => {
    setDraft((d) => ({ ...d, ...changes }))
    setDirty(true)
  }

  const save = async () => {
    setBusy(true)
    setError('')
    try {
      const updated = await api.updateDocument(documentId, draft)
      setDoc(updated)
      setDirty(false)
      setMessage('Saved.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const reset = async () => {
    setBusy(true)
    try {
      const updated = await api.resetDocument(documentId)
      setDoc(updated)
      setDraft(updated.content)
      setDirty(false)
      setMessage(fromMaster ? 'Reverted to the copy of your master resume.' : 'Reverted to the generated version.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    await api.deleteDocument(documentId)
    navigate('/history')
  }

  const isResume = doc?.kind === 'resume'
  const fromMaster = doc?.model_used === MASTER_COPY
  const title = useMemo(() => (isResume ? 'Tailored resume' : 'Cover letter'), [isResume])

  if (error && !doc) {
    return (
      <main className="page document-page">
        <div className="alert error">{error}</div>
        <Link className="btn" to="/history">‹ History</Link>
      </main>
    )
  }
  if (!doc || !draft) return <main className="page document-page"><div className="empty">Loading…</div></main>

  return (
    <main className="page document-page">
      <div className="page-header">
        <h1>{title}</h1>
        <Link className="count-pill" to={`/jobs/${doc.job_id}`}>
          ‹ Back to job
        </Link>
      </div>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      <div className="alert info">
        {fromMaster ? (
          <>
            A copy of your master resume for this job. Make your edits for this job here —
            they stay with this job and never change your master resume. Read it through
            before you use it.
          </>
        ) : (
          <>
            Read this through before you use it. It is a first draft built from your
            {isResume ? ' master resume' : ' resume'} — check every claim is one you would
            stand behind in an interview.
            {isResume && ' Edits here stay with this job and never change your master resume.'}
          </>
        )}
      </div>

      <div className="document-workspace">
        <div className="card document-editor-pane">
          <div className="resume-preview-label">Editor</div>
          {isResume ? (
            <ResumeForm value={draft} patch={patch} />
          ) : (
            <CoverLetterForm value={draft} patch={patch} />
          )}
        </div>
        <div className="document-preview-pane">
          <div className="resume-preview-label">Live preview</div>
          {isResume ? (
            <ResumePreview value={draft} />
          ) : (
            <article className="resume-paper cover-letter-paper">
              <p>{draft.greeting}</p>
              {(draft.paragraphs || []).filter(Boolean).map((paragraph, i) => <p key={i}>{paragraph}</p>)}
              <p>{draft.closing}</p>
            </article>
          )}
        </div>
      </div>

      <div className="job-actions">
        <button className="btn primary" onClick={save} disabled={!dirty || busy}>
          {busy ? 'Saving…' : dirty ? 'Save edits' : 'Saved'}
        </button>
        <button
          className="btn"
          onClick={() => exportDocumentPdf(doc.kind, draft)}
          disabled={busy}
        >
          Export PDF
        </button>
        {doc.edited_content && (
          <button className="btn" onClick={reset} disabled={busy}>
            {fromMaster ? 'Reset to master copy' : 'Reset to generated'}
          </button>
        )}
        <button className="btn danger" onClick={remove} disabled={busy}>
          Delete
        </button>
      </div>
    </main>
  )
}
