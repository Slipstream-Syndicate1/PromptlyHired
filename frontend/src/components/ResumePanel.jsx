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

const emptyEntry = () => ({ title: '', meta: '', right: '', subtitle: '', subtitle_right: '', bullets: [''] })

const CONTACT_KEYS = ['phone', 'email', 'linkedin', 'github']

const splitContactLine = (value = '') => {
  const parts = String(value).split('|').map((part) => part.trim())
  return Object.fromEntries(CONTACT_KEYS.map((key, index) => [key, parts[index] || '']))
}

const joinContactLine = (contact) => CONTACT_KEYS.map((key) => contact[key]?.trim() || '').join(' | ')

const getSkillValue = (items, label) => {
  const prefix = `${label}:`
  const match = (items || []).find((item) => item.trim().toLowerCase().startsWith(prefix.toLowerCase()))
  return match ? match.slice(match.indexOf(':') + 1).trim() : ''
}

const setSkillValue = (items, label, value) => {
  const prefix = `${label}:`
  const next = [...(items || [])]
  const index = next.findIndex((item) => item.trim().toLowerCase().startsWith(prefix.toLowerCase()))
  const line = `${label}: ${value}`
  if (index >= 0) next[index] = line
  else next.push(line)
  return next
}

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

function SkillLinesEditor({ items, onChange }) {
  const rows = ['Languages', 'Frameworks', 'Developer Tools', 'Libraries']
  return (
    <div className="master-section exact-skills-editor">
      <div className="master-section-title-row"><strong>Technical Skills</strong></div>
      <p className="fine-print">These four rows map directly to the reference template.</p>
      {rows.map((label) => (
        <label className="field skill-row-editor" key={label}>
          <span>{label}</span>
          <input
            value={getSkillValue(items, label)}
            placeholder={label === 'Languages' ? 'Java, Python, C/C++, SQL, JavaScript' : `Add ${label.toLowerCase()}`}
            onChange={(e) => onChange(setSkillValue(items, label, e.target.value))}
          />
        </label>
      ))}
    </div>
  )
}

function EntryEditor({ sectionName, entry, onChange, onRemove }) {
  const lower = sectionName.trim().toLowerCase()
  const isEducation = lower === 'education'
  const isProject = lower === 'projects' || lower === 'project'
  const labels = isEducation
    ? { title: 'School', right: 'Location', subtitle: 'Degree / program', subtitleRight: 'Dates' }
    : isProject
      ? { title: 'Project name', right: 'Dates', subtitle: 'Technologies', subtitleRight: '' }
      : { title: 'Position / title', right: 'Dates', subtitle: 'Company / organization', subtitleRight: 'Location' }

  const patch = (changes) => onChange({ ...entry, ...changes })
  const bullets = entry.bullets || []
  const updateBullet = (index, value) => patch({ bullets: bullets.map((b, i) => i === index ? value : b) })

  return (
    <div className="resume-entry-editor">
      <div className="resume-entry-editor-grid">
        <label className="field"><span>{labels.title}</span><input value={entry.title || ''} onChange={(e) => patch({ title: e.target.value })} /></label>
        <label className="field"><span>{labels.right}</span><input value={entry.right || ''} placeholder={isEducation ? 'Georgetown, TX' : 'June 2020 – Present'} onChange={(e) => patch({ right: e.target.value })} /></label>
        {isProject ? (
          <label className="field resume-entry-editor-wide"><span>{labels.subtitle}</span><input value={entry.meta || ''} placeholder="Python, Flask, React, PostgreSQL, Docker" onChange={(e) => patch({ meta: e.target.value })} /></label>
        ) : (
          <>
            <label className="field"><span>{labels.subtitle}</span><input value={entry.subtitle || ''} onChange={(e) => patch({ subtitle: e.target.value })} /></label>
            <label className="field"><span>{labels.subtitleRight}</span><input value={entry.subtitle_right || ''} placeholder={isEducation ? 'Aug. 2018 – May 2021' : 'College Station, TX'} onChange={(e) => patch({ subtitle_right: e.target.value })} /></label>
          </>
        )}
      </div>
      {!isEducation && (
        <div className="resume-entry-bullets">
          <span className="field-label">Bullets</span>
          {bullets.map((bullet, index) => (
            <div className="bullet-row" key={index}>
              <textarea rows="2" value={bullet} placeholder="Developed…" onChange={(e) => updateBullet(index, e.target.value)} />
              <button className="btn danger" type="button" onClick={() => patch({ bullets: bullets.filter((_, i) => i !== index) })}>×</button>
            </div>
          ))}
          <button className="btn" type="button" onClick={() => patch({ bullets: [...bullets, ''] })}>+ Add bullet</button>
        </div>
      )}
      <button className="btn danger compact" type="button" onClick={onRemove}>Remove entry</button>
    </div>
  )
}

function MasterResumeEditor({ resume, user, onSaved }) {
  const [master, setMaster] = useState(() => normalizeMaster(resume.master_content, user, resume.skill_profile))
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [mobileView, setMobileView] = useState('edit')

  useEffect(() => {
    setMaster(normalizeMaster(resume.master_content, user, resume.skill_profile))
    setDirty(false)
  }, [resume.id, resume.master_content, user?.name])

  const patch = (changes) => { setMaster((m) => ({ ...m, ...changes })); setDirty(true); setMessage('') }
  const contact = splitContactLine(master.contact_line || '')
  const updateContact = (key, value) => patch({ contact_line: joinContactLine({ ...contact, [key]: value }) })
  const updateSection = (index, changes) => patch({ sections: master.sections.map((s, i) => i === index ? { ...s, ...changes } : s) })
  const addSection = () => patch({ sections: [...master.sections, { heading: 'New Section', bullets: [], entries: [] }] })
  const removeSection = (index) => patch({ sections: master.sections.filter((_, i) => i !== index) })
  const addEntry = (sectionIndex) => updateSection(sectionIndex, { entries: [...(master.sections[sectionIndex].entries || []), emptyEntry()] })
  const updateEntry = (sectionIndex, entryIndex, value) => updateSection(sectionIndex, { entries: (master.sections[sectionIndex].entries || []).map((e, i) => i === entryIndex ? value : e) })
  const removeEntry = (sectionIndex, entryIndex) => updateSection(sectionIndex, { entries: (master.sections[sectionIndex].entries || []).filter((_, i) => i !== entryIndex) })
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
          <p className="job-company">Edit simple fields on the left; the preview and PDF keep the exact classic one-page layout from the reference.</p>
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
          <div className="master-section exact-header-editor">
            <div className="master-section-title-row"><strong>Header</strong></div>
            <label className="field"><span>Full name</span><input value={master.full_name} placeholder="Jake Ryan" onChange={(e) => patch({ full_name: e.target.value })} /></label>
            <div className="exact-contact-grid">
              <label className="field"><span>Phone</span><input value={contact.phone} placeholder="123-456-7890" onChange={(e) => updateContact('phone', e.target.value)} /></label>
              <label className="field"><span>Email</span><input value={contact.email} placeholder="jake@su.edu" onChange={(e) => updateContact('email', e.target.value)} /></label>
              <label className="field"><span>LinkedIn</span><input value={contact.linkedin} placeholder="linkedin.com/in/jake" onChange={(e) => updateContact('linkedin', e.target.value)} /></label>
              <label className="field"><span>GitHub</span><input value={contact.github} placeholder="github.com/jake" onChange={(e) => updateContact('github', e.target.value)} /></label>
            </div>
          </div>

          <details className="resume-optional-fields">
            <summary>Optional extras (not in the reference template)</summary>
            <label className="field"><span>Headline</span><input value={master.headline} placeholder="Leave blank for the exact template" onChange={(e) => patch({ headline: e.target.value })} /></label>
            <label className="field"><span>Summary</span><textarea rows="3" value={master.summary} placeholder="Leave blank for the exact template" onChange={(e) => patch({ summary: e.target.value })} /></label>
          </details>

          {master.sections.map((section, sectionIndex) => {
            const lower = section.heading.trim().toLowerCase()
            const structured = ['education', 'experience', 'projects', 'project'].includes(lower)
            return (
              <div className="master-section" key={sectionIndex}>
                <div className="master-section-title-row">
                  {structured
                    ? <strong>{section.heading}</strong>
                    : <input className="master-section-title-input" value={section.heading} onChange={(e) => updateSection(sectionIndex, { heading: e.target.value })} />}
                  {!structured && <button className="btn danger compact" type="button" onClick={() => removeSection(sectionIndex)}>Remove section</button>}
                </div>
                {structured && (section.entries || []).map((entry, entryIndex) => (
                  <EntryEditor key={entryIndex} sectionName={section.heading} entry={entry} onChange={(value) => updateEntry(sectionIndex, entryIndex, value)} onRemove={() => removeEntry(sectionIndex, entryIndex)} />
                ))}
                {structured && <button className="btn" type="button" onClick={() => addEntry(sectionIndex)}>+ Add {lower === 'education' ? 'education' : lower.startsWith('project') ? 'project' : 'experience'} entry</button>}
                {(section.bullets || []).length > 0 && structured && <p className="fine-print legacy-bullets-label">Existing loose bullets</p>}
                {(section.bullets || []).map((bullet, bulletIndex) => (
                  <div className="bullet-row" key={`loose-${bulletIndex}`}>
                    <textarea rows="2" value={bullet} placeholder="Add a concise accomplishment or detail" onChange={(e) => updateBullet(sectionIndex, bulletIndex, e.target.value)} />
                    <button className="btn danger" type="button" onClick={() => removeBullet(sectionIndex, bulletIndex)}>×</button>
                  </div>
                ))}
                {!structured && <button className="btn" type="button" onClick={() => addBullet(sectionIndex)}>+ Add bullet</button>}
              </div>
            )
          })}
          <button className="btn" type="button" onClick={addSection}>+ Add custom section</button>
          <SkillLinesEditor items={master.skills || []} onChange={(skills) => patch({ skills })} />
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
