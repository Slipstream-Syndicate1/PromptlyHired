import './ResumePanel.css'

/**
 * The fields of a resume in the master resume layout.
 *
 * Shared by the master resume on Profile and each job's tailored copy, so both
 * edit the same shape and preview and export the same way. `onChange` receives
 * only the fields that changed.
 */

export const emptyEntry = () => ({ title: '', meta: '', right: '', subtitle: '', subtitle_right: '', bullets: [''] })

const CONTACT_KEYS = ['phone', 'email', 'linkedin', 'github']
const SKILL_ROWS = ['Languages', 'Frameworks', 'Developer Tools', 'Libraries']

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

const isSkillRow = (item) =>
  SKILL_ROWS.some((label) => item.trim().toLowerCase().startsWith(`${label.toLowerCase()}:`))

function SkillLinesEditor({ items, onChange }) {
  // Lines outside the four template rows (e.g. "Certifications: ...", or plain
  // skills in older documents) stay visible and editable rather than hidden.
  const other = items.map((item, index) => ({ item, index })).filter(({ item }) => !isSkillRow(item))
  return (
    <div className="master-section exact-skills-editor">
      <div className="master-section-title-row"><strong>Technical Skills</strong></div>
      <p className="fine-print">These four rows map directly to the reference template.</p>
      {SKILL_ROWS.map((label) => (
        <label className="field skill-row-editor" key={label}>
          <span>{label}</span>
          <input
            value={getSkillValue(items, label)}
            placeholder={label === 'Languages' ? 'Java, Python, C/C++, SQL, JavaScript' : `Add ${label.toLowerCase()}`}
            onChange={(e) => onChange(setSkillValue(items, label, e.target.value))}
          />
        </label>
      ))}
      {other.length > 0 && <p className="fine-print legacy-bullets-label">Other skill lines</p>}
      {other.map(({ item, index }) => (
        <div className="bullet-row" key={index}>
          <input
            value={item}
            placeholder="Certifications: AWS Cloud Practitioner"
            aria-label="Skill line"
            onChange={(e) => onChange(items.map((line, i) => (i === index ? e.target.value : line)))}
          />
          <button className="btn danger" type="button" aria-label="Remove skill line" onClick={() => onChange(items.filter((_, i) => i !== index))}>×</button>
        </div>
      ))}
      <button className="btn" type="button" onClick={() => onChange([...items, ''])}>+ Add skill line</button>
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

export default function ResumeEditor({ value, onChange }) {
  const patch = onChange
  const sections = value.sections || []
  const contact = splitContactLine(value.contact_line || '')
  const updateContact = (key, next) => patch({ contact_line: joinContactLine({ ...contact, [key]: next }) })
  const updateSection = (index, changes) => patch({ sections: sections.map((s, i) => i === index ? { ...s, ...changes } : s) })
  const addSection = () => patch({ sections: [...sections, { heading: 'New Section', bullets: [], entries: [] }] })
  const removeSection = (index) => patch({ sections: sections.filter((_, i) => i !== index) })
  const entriesOf = (index) => sections[index].entries || []
  const bulletsOf = (index) => sections[index].bullets || []
  const addEntry = (index) => updateSection(index, { entries: [...entriesOf(index), emptyEntry()] })
  const updateEntry = (index, entryIndex, entry) => updateSection(index, { entries: entriesOf(index).map((e, i) => i === entryIndex ? entry : e) })
  const removeEntry = (index, entryIndex) => updateSection(index, { entries: entriesOf(index).filter((_, i) => i !== entryIndex) })
  const addBullet = (index) => updateSection(index, { bullets: [...bulletsOf(index), ''] })
  const updateBullet = (index, bulletIndex, bullet) => updateSection(index, { bullets: bulletsOf(index).map((b, i) => i === bulletIndex ? bullet : b) })
  const removeBullet = (index, bulletIndex) => updateSection(index, { bullets: bulletsOf(index).filter((_, i) => i !== bulletIndex) })

  return (
    <>
      <div className="master-section exact-header-editor">
        <div className="master-section-title-row"><strong>Header</strong></div>
        <label className="field"><span>Full name</span><input value={value.full_name || ''} placeholder="Jake Ryan" onChange={(e) => patch({ full_name: e.target.value })} /></label>
        <div className="exact-contact-grid">
          <label className="field"><span>Phone</span><input value={contact.phone} placeholder="123-456-7890" onChange={(e) => updateContact('phone', e.target.value)} /></label>
          <label className="field"><span>Email</span><input value={contact.email} placeholder="jake@su.edu" onChange={(e) => updateContact('email', e.target.value)} /></label>
          <label className="field"><span>LinkedIn</span><input value={contact.linkedin} placeholder="linkedin.com/in/jake" onChange={(e) => updateContact('linkedin', e.target.value)} /></label>
          <label className="field"><span>GitHub</span><input value={contact.github} placeholder="github.com/jake" onChange={(e) => updateContact('github', e.target.value)} /></label>
        </div>
      </div>

      <details className="resume-optional-fields">
        <summary>Optional extras (not in the reference template)</summary>
        <label className="field"><span>Headline</span><input value={value.headline || ''} placeholder="Leave blank for the exact template" onChange={(e) => patch({ headline: e.target.value })} /></label>
        <label className="field"><span>Summary</span><textarea rows="3" value={value.summary || ''} placeholder="Leave blank for the exact template" onChange={(e) => patch({ summary: e.target.value })} /></label>
      </details>

      {sections.map((section, sectionIndex) => {
        const heading = section.heading || ''
        const lower = heading.trim().toLowerCase()
        const structured = ['education', 'experience', 'projects', 'project'].includes(lower)
        const entries = section.entries || []
        const bullets = section.bullets || []
        return (
          <div className="master-section" key={sectionIndex}>
            <div className="master-section-title-row">
              {structured
                ? <strong>{heading}</strong>
                : <input className="master-section-title-input" value={heading} aria-label="Section heading" onChange={(e) => updateSection(sectionIndex, { heading: e.target.value })} />}
              {!structured && <button className="btn danger compact" type="button" onClick={() => removeSection(sectionIndex)}>Remove section</button>}
            </div>
            {structured && entries.map((entry, entryIndex) => (
              <EntryEditor key={entryIndex} sectionName={heading} entry={entry} onChange={(next) => updateEntry(sectionIndex, entryIndex, next)} onRemove={() => removeEntry(sectionIndex, entryIndex)} />
            ))}
            {structured && <button className="btn" type="button" onClick={() => addEntry(sectionIndex)}>+ Add {lower === 'education' ? 'education' : lower.startsWith('project') ? 'project' : 'experience'} entry</button>}
            {bullets.length > 0 && structured && <p className="fine-print legacy-bullets-label">Existing loose bullets</p>}
            {bullets.map((bullet, bulletIndex) => (
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
      <SkillLinesEditor items={value.skills || []} onChange={(skills) => patch({ skills })} />
    </>
  )
}
