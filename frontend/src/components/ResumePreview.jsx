const formatContactLine = (value = '') => String(value).split('|').map((part) => part.trim()).filter(Boolean).join(' | ')
const hasText = (value) => String(value ?? '').trim().length > 0
const entryHasContent = (entry = {}) => (
  [entry.title, entry.meta, entry.right, entry.subtitle, entry.subtitle_right].some(hasText)
  || (entry.bullets || []).some(hasText)
)

function Entry({ entry }) {
  const bullets = (entry?.bullets || []).filter(hasText)
  return (
    <div className="resume-entry">
      {(hasText(entry.title) || hasText(entry.meta) || hasText(entry.right)) && (
        <div className="resume-entry-row resume-entry-primary">
          <div className="resume-entry-left">
            {hasText(entry.title) && <strong>{entry.title}</strong>}
            {hasText(entry.meta) && <><span className="resume-entry-separator">{hasText(entry.title) ? ' | ' : ''}</span><em>{entry.meta}</em></>}
          </div>
          {hasText(entry.right) && <span className="resume-entry-right">{entry.right}</span>}
        </div>
      )}
      {(hasText(entry.subtitle) || hasText(entry.subtitle_right)) && (
        <div className="resume-entry-row resume-entry-secondary">
          {hasText(entry.subtitle) ? <em>{entry.subtitle}</em> : <span />}
          {hasText(entry.subtitle_right) && <em className="resume-entry-right">{entry.subtitle_right}</em>}
        </div>
      )}
      {bullets.length > 0 && <ul>{bullets.map((bullet, i) => <li key={i}>{bullet}</li>)}</ul>}
    </div>
  )
}

function SkillLine({ value }) {
  const index = value.indexOf(':')
  if (index === -1) return <>{value}</>
  return <><strong>{value.slice(0, index + 1)}</strong>{value.slice(index + 1)}</>
}

export default function ResumePreview({ value, className = '' }) {
  const sections = (value?.sections || []).map((section) => ({
    ...section,
    entries: (section.entries || []).filter(entryHasContent),
    bullets: (section.bullets || []).filter(hasText),
  })).filter((section) => hasText(section.heading) && (section.entries.length > 0 || section.bullets.length > 0))
  const skills = (value?.skills || []).filter(hasText)
  const contactLine = formatContactLine(value?.contact_line || '')

  return (
    <article className={`resume-paper classic-resume ${className}`.trim()} aria-label="Resume preview">
      <header className="resume-paper-header">
        <h1>{value?.full_name || 'Your Name'}</h1>
        {contactLine && <p className="resume-contact-line">{contactLine}</p>}
        {hasText(value?.headline) && <p className="resume-paper-headline">{value.headline}</p>}
      </header>

      {hasText(value?.summary) && (
        <section className="resume-paper-section">
          <h2>Summary</h2>
          <p>{value.summary}</p>
        </section>
      )}

      {sections.map((section, index) => (
        <section className="resume-paper-section" key={index}>
          <h2>{section.heading}</h2>
          {section.entries.map((entry, entryIndex) => <Entry entry={entry} key={entryIndex} />)}
          {section.bullets.length > 0 && <ul className="resume-generic-bullets">{section.bullets.map((bullet, bulletIndex) => <li key={bulletIndex}>{bullet}</li>)}</ul>}
        </section>
      ))}

      {skills.length > 0 && (
        <section className="resume-paper-section resume-skills-section">
          <h2>Technical Skills</h2>
          <div className="resume-paper-skills">{skills.map((skill, i) => <p key={i}><SkillLine value={skill} /></p>)}</div>
        </section>
      )}
    </article>
  )
}
