import { useEffect, useRef, useState } from 'react'
import './ResumePanel.css'
import { api } from '../api/client'
import ConfirmDialog from './ConfirmDialog.jsx'
import ResumeEditor, { emptyEntry } from './ResumeEditor.jsx'
import ResumePreview from './ResumePreview.jsx'
import { exportDocumentPdf } from '../lib/exportPdf.js'

const ACCEPT = '.pdf,.docx,.txt'
const ACCEPT_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
].join(',')

const emptyMaster = (user, profile) => ({
  full_name: user?.name || '',
  headline: '',
  contact_line: '',
  summary: '',
  sections: [
    { heading: 'Education', bullets: [], entries: [emptyEntry()] },
    { heading: 'Experience', bullets: [], entries: [emptyEntry()] },
    { heading: 'Projects', bullets: [], entries: [emptyEntry()] },
  ],
  skills: profile?.skills?.length ? [`Languages: ${profile.skills.join(', ')}`] : ['Languages: ', 'Frameworks: ', 'Developer Tools: ', 'Libraries: '],
})

const normalizeMaster = (value, user, profile) => {
  const base = value || emptyMaster(user, profile)
  return {
    ...base,
    contact_line: base.contact_line || '',
    sections: (base.sections || []).map((section) => ({ ...section, bullets: section.bullets || [], entries: section.entries || [] })),
    skills: base.skills || [],
  }
}

function TagEditor({ label, items, onChange, placeholder }) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const value = draft.trim()
    if (!value) return
    if (!items.some((i) => i.toLowerCase() === value.toLowerCase())) onChange([...items, value])
    setDraft('')
  }
  return (
    <div className="field">
      <span>{label}</span>
      <div className="tag-row">
        {items.map((item) => (
          <span className="tag" key={item}>{item}<button type="button" onClick={() => onChange(items.filter((i) => i !== item))} aria-label={`Remove ${item}`}>×</button></span>
        ))}
      </div>
      <div className="bullet-row">
        <input value={draft} placeholder={placeholder} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
        <button className="btn" type="button" onClick={add}>Add</button>
      </div>
    </div>
  )
}

/**
 * The master resume: the user's permanent base resume. Saving it here is what
 * every job's resume starts from; editing a job's copy never changes it.
 */
function MasterResumeEditor({ resume, user, onSaved }) {
  const [master, setMaster] = useState(() => normalizeMaster(resume.master_content, user, resume.skill_profile))
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [filling, setFilling] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [mobileView, setMobileView] = useState('edit')

  useEffect(() => {
    setMaster(normalizeMaster(resume.master_content, user, resume.skill_profile))
    setDirty(false)
  }, [resume.id, resume.master_content, user?.name])

  const patch = (changes) => { setMaster((m) => ({ ...m, ...changes })); setDirty(true); setMessage('') }

  const save = async () => {
    setBusy(true); setError(''); setMessage('')
    try {
      const updated = await api.updateMasterResume(resume.id, master)
      onSaved(updated)
      setDirty(false)
      setMessage('Master resume saved. Every new resume you make for a job starts from this version.')
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  // Costs one AI request, so it only runs when asked, and saves nothing by itself.
  const fillFromCv = async () => {
    if ((resume.master_content || dirty) && !window.confirm('Replace everything in the editor with details read from your uploaded CV? Nothing is saved until you click Save master.')) return
    setFilling(true); setError(''); setMessage('')
    try {
      const draft = await api.draftMasterFromUpload(resume.id)
      setMaster(normalizeMaster(draft, user, resume.skill_profile))
      setDirty(true)
      setMessage('Filled in from your uploaded CV. Check every field, then click Save master.')
    } catch (err) { setError(err.message) } finally { setFilling(false) }
  }

  const working = busy || filling

  return (
    <div className="card master-resume-card">
      <div className="master-resume-heading">
        <div>
          <h2 className="section-title" style={{ marginTop: 0 }}>Master resume</h2>
          <p className="job-company">Your base resume. Every resume you make for a job starts from the saved version, and changes made for one job never change it.</p>
          {!resume.master_content && !dirty && (
            <p className="fine-print">Not saved yet. Fill it in from your uploaded CV to skip retyping, check it, then save it.</p>
          )}
        </div>
        <div className="master-resume-actions">
          <button className="btn" type="button" onClick={fillFromCv} disabled={working}>{filling ? 'Reading your CV…' : 'Fill from uploaded CV'}</button>
          <button className="btn primary" type="button" onClick={save} disabled={!dirty || working}>{busy ? 'Saving…' : dirty ? 'Save master' : 'Saved'}</button>
          <button className="btn" type="button" onClick={() => exportDocumentPdf('resume', master)} disabled={working}>Export PDF</button>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info" role="status">{message}</div>}

      <div className="resume-mobile-tabs">
        <button className={`btn ${mobileView === 'edit' ? 'primary' : ''}`} type="button" onClick={() => setMobileView('edit')}>Edit</button>
        <button className={`btn ${mobileView === 'preview' ? 'primary' : ''}`} type="button" onClick={() => setMobileView('preview')}>Preview</button>
      </div>

      <div className="resume-workspace">
        <div className={`resume-editor-pane ${mobileView !== 'edit' ? 'mobile-hidden' : ''}`}>
          <ResumeEditor value={master} onChange={patch} />
        </div>

        <div className={`resume-preview-pane ${mobileView !== 'preview' ? 'mobile-hidden' : ''}`}>
          <div className="resume-preview-label">Live preview</div>
          <ResumePreview value={master} />
        </div>
      </div>
    </div>
  )
}

export default function ResumePanel({ resume, onChange, user }) {
  const inputRef = useRef(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [profile, setProfile] = useState(resume?.skill_profile ?? null)
  const [dirty, setDirty] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  useEffect(() => { setProfile(resume?.skill_profile ?? null); setDirty(false) }, [resume])

  const run = async (fn, done) => {
    setBusy(true); setError(''); setMessage('')
    try { await fn(); if (done) setMessage(done) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const pick = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    await run(async () => { const uploaded = await api.uploadResume(file); setProfile(uploaded.skill_profile ?? null); setDirty(false); onChange(uploaded) }, 'Resume uploaded and analysed.')
    if (inputRef.current) inputRef.current.value = ''
  }
  const setField = (key, value) => { setProfile((p) => ({ ...p, [key]: value })); setDirty(true) }
  const saveProfile = () => run(async () => { const updated = await api.updateSkillProfile(resume.id, { skills: profile.skills, job_titles: profile.job_titles, domains: profile.domains, locations: profile.locations, seniority: profile.seniority, years_experience: profile.years_experience, summary: profile.summary }); setProfile(updated); setDirty(false) }, 'Skill profile saved. Your job feed will use it.')
  const reanalyse = () => run(async () => { setProfile(await api.reanalyzeResume(resume.id)); setDirty(false) }, 'Re-analysed your resume.')

  const remove = async () => {
    let deleted = false
    await run(async () => {
      await api.deleteResume(resume.id)
      setProfile(null)
      // An older CV, if there is one, becomes the active one.
      onChange(await api.getActiveResume())
      deleted = true
    }, 'Resume deleted.')
    // On failure the dialog stays open, with the reason shown on the page behind it.
    if (deleted) setConfirmingDelete(false)
  }

  return (
    <>
      {resume && <MasterResumeEditor resume={resume} user={user} onSaved={onChange} />}
      <div className="card">
        <h2 className="section-title" style={{ marginTop: 0 }}>Uploaded resume & job matching</h2>
        {error && <div className="alert error">{error}</div>}
        {message && <div className="alert info">{message}</div>}
        {resume ? <p className="job-company"><strong>{resume.original_filename}</strong> · uploaded {new Date(resume.uploaded_at).toLocaleDateString()}</p> : <p className="job-company">Upload a resume to create your master resume, extract your skillset, and power job matching.</p>}
        <div className="job-actions">
          <button className={resume ? 'btn' : 'btn primary'} type="button" disabled={busy} onClick={() => inputRef.current?.click()}>{busy ? 'Working…' : resume ? 'Replace uploaded resume' : 'Upload resume'}</button>
          {resume && <button className="btn" type="button" disabled={busy} onClick={reanalyse}>Re-analyse</button>}
          {resume && <button className="btn link" type="button" disabled={busy} onClick={() => setConfirmingDelete(true)}>Delete uploaded resume</button>}
        </div>
        <p className="fine-print">PDF, DOCX or plain text, up to 10 MB. Replacing it keeps your saved master resume.</p>
        <input ref={inputRef} type="file" accept={`${ACCEPT},${ACCEPT_TYPES}`} onChange={pick} hidden />

        {resume && profile && <>
          <h2 className="section-title">Skill profile</h2>
          <p className="job-company" style={{ marginBottom: 12 }}>This powers your job feed. It stays separate from the wording and layout of your master resume.</p>
          <TagEditor label="Job titles to search for" items={profile.job_titles || []} onChange={(v) => setField('job_titles', v)} placeholder="e.g. Backend Engineer" />
          <TagEditor label="Skills" items={profile.skills || []} onChange={(v) => setField('skills', v)} placeholder="e.g. Python" />
          <TagEditor label="Preferred locations" items={profile.locations || []} onChange={(v) => setField('locations', v)} placeholder="e.g. Edmonton" />
          <label className="field"><span>Seniority</span><input value={profile.seniority ?? ''} onChange={(e) => setField('seniority', e.target.value)} /></label>
          <label className="field"><span>Years of experience</span><input type="number" min="0" step="0.5" value={profile.years_experience ?? ''} onChange={(e) => setField('years_experience', e.target.value === '' ? null : Number(e.target.value))} /></label>
          {dirty && <button className="btn primary block" type="button" onClick={saveProfile} disabled={busy}>Save skill profile</button>}
        </>}
        {resume && !profile && <div className="alert info">We couldn’t analyse this resume automatically. Try “Re-analyse”, or check the server has an <code>ANTHROPIC_API_KEY</code> configured.</div>}
      </div>

      {confirmingDelete && resume && (
        <ConfirmDialog
          title="Delete this resume?"
          phrase="Delete Resume"
          confirmLabel="Confirm Delete"
          busy={busy}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={remove}
        >
          <p>
            <strong>{resume.original_filename}</strong> and everything built from it will be
            deleted:
          </p>
          <ul>
            <li>its skill profile, which powers your job feed and recommendations</li>
            <li>its master resume</li>
            <li>the match scores worked out against it</li>
            <li>the resumes and cover letters generated from it</li>
          </ul>
          <p>Your tracked applications are kept, including the record that you applied.</p>
        </ConfirmDialog>
      )}
    </>
  )
}
