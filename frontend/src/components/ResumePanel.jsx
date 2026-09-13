import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
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
  summary: profile?.summary || '',
  sections: [
    { heading: 'Experience', bullets: [''] },
    { heading: 'Education', bullets: [''] },
    { heading: 'Projects', bullets: [''] },
  ],
  skills: profile?.skills || [],
})

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

function MasterResumeEditor({ resume, user, onSaved }) {
  const [master, setMaster] = useState(() => resume.master_content || emptyMaster(user, resume.skill_profile))
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [mobileView, setMobileView] = useState('edit')

  useEffect(() => {
    setMaster(resume.master_content || emptyMaster(user, resume.skill_profile))
    setDirty(false)
  }, [resume.id, resume.master_content, user?.name])

  const patch = (changes) => { setMaster((m) => ({ ...m, ...changes })); setDirty(true); setMessage('') }
  const updateSection = (index, changes) => patch({ sections: master.sections.map((s, i) => i === index ? { ...s, ...changes } : s) })
  const addSection = () => patch({ sections: [...master.sections, { heading: 'New Section', bullets: [''] }] })
  const removeSection = (index) => patch({ sections: master.sections.filter((_, i) => i !== index) })
  const addBullet = (sectionIndex) => updateSection(sectionIndex, { bullets: [...(master.sections[sectionIndex].bullets || []), ''] })
  const updateBullet = (sectionIndex, bulletIndex, value) => updateSection(sectionIndex, { bullets: master.sections[sectionIndex].bullets.map((b, i) => i === bulletIndex ? value : b) })
  const removeBullet = (sectionIndex, bulletIndex) => updateSection(sectionIndex, { bullets: master.sections[sectionIndex].bullets.filter((_, i) => i !== bulletIndex) })

  const save = async () => {
    setBusy(true); setError(''); setMessage('')
    try {
      const updated = await api.updateMasterResume(resume.id, master)
      onSaved(updated)
      setDirty(false)
      setMessage('Master resume saved. New tailored documents will use this version.')
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="card master-resume-card">
      <div className="master-resume-heading">
        <div>
          <h2 className="section-title" style={{ marginTop: 0 }}>Master resume</h2>
          <p className="job-company">This is your editable base resume. New tailored resumes and cover letters use the saved version.</p>
        </div>
        <div className="master-resume-actions">
          <button className="btn primary" type="button" onClick={save} disabled={!dirty || busy}>{busy ? 'Saving…' : dirty ? 'Save master' : 'Saved'}</button>
          <button className="btn" type="button" onClick={() => exportDocumentPdf('resume', master)} disabled={busy}>Export PDF</button>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      <div className="resume-mobile-tabs">
        <button className={`btn ${mobileView === 'edit' ? 'primary' : ''}`} type="button" onClick={() => setMobileView('edit')}>Edit</button>
        <button className={`btn ${mobileView === 'preview' ? 'primary' : ''}`} type="button" onClick={() => setMobileView('preview')}>Preview</button>
      </div>

      <div className="resume-workspace">
        <div className={`resume-editor-pane ${mobileView !== 'edit' ? 'mobile-hidden' : ''}`}>
          <label className="field"><span>Full name</span><input value={master.full_name} onChange={(e) => patch({ full_name: e.target.value })} /></label>
          <label className="field"><span>Headline</span><input value={master.headline} placeholder="e.g. Software Developer" onChange={(e) => patch({ headline: e.target.value })} /></label>
          <label className="field"><span>Professional summary</span><textarea rows="4" value={master.summary} onChange={(e) => patch({ summary: e.target.value })} /></label>

          {master.sections.map((section, sectionIndex) => (
            <div className="master-section" key={sectionIndex}>
              <div className="master-section-title-row">
                <input className="master-section-title-input" value={section.heading} onChange={(e) => updateSection(sectionIndex, { heading: e.target.value })} />
                <button className="btn danger compact" type="button" onClick={() => removeSection(sectionIndex)}>Remove</button>
              </div>
              {(section.bullets || []).map((bullet, bulletIndex) => (
                <div className="bullet-row" key={bulletIndex}>
                  <textarea rows="2" value={bullet} placeholder="Add a concise accomplishment, qualification, or detail" onChange={(e) => updateBullet(sectionIndex, bulletIndex, e.target.value)} />
                  <button className="btn danger" type="button" onClick={() => removeBullet(sectionIndex, bulletIndex)} aria-label="Remove bullet">×</button>
                </div>
              ))}
              <button className="btn" type="button" onClick={() => addBullet(sectionIndex)}>+ Add bullet</button>
            </div>
          ))}
          <button className="btn" type="button" onClick={addSection}>+ Add section</button>
          <TagEditor label="Skills" items={master.skills || []} onChange={(skills) => patch({ skills })} placeholder="e.g. Python" />
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
        </div>
        <p className="fine-print">PDF, DOCX or plain text, up to 10 MB.</p>
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
    </>
  )
}
