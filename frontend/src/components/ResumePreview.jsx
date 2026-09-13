import './ResumePanel.css'

const formatContactLine = (value = '') => String(value).split('|').map((part) => part.trim()).filter(Boolean).join(' | ')
function Entry({ entry }) {
  const bullets = (entry?.bullets || []).filter(Boolean)
  return (
    <div className="resume-entry">
      <div className="resume-entry-row resume-entry-primary">
        <div className="resume-entry-left">
          <strong>{entry.title}</strong>
          {entry.meta && <><span className="resume-entry-separator"> | </span><em>{entry.meta}</em></>}
        </div>
        {entry.right && <span className="resume-entry-right">{entry.right}</span>}
      </div>
      {(entry.subtitle || entry.subtitle_right) && (
        <div className="resume-entry-row resume-entry-secondary">
          <em>{entry.subtitle}</em>
          {entry.subtitle_right && <em className="resume-entry-right">{entry.subtitle_right}</em>}
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
  const sections = value?.sections || []
  const skills = (value?.skills || []).filter(Boolean)
  const contactLine = formatContactLine(value?.contact_line || '')

  return (
    <article className={`resume-paper classic-resume ${className}`.trim()} aria-label="Resume preview">
      <header className="resume-paper-header">
        <h1>{value?.full_name || 'Your Name'}</h1>
        {contactLine && <p className="resume-contact-line">{contactLine}</p>}
        {value?.headline && <p className="resume-paper-headline">{value.headline}</p>}
      </header>

      {value?.summary && (
        <section className="resume-paper-section">
          <h2>Summary</h2>
          <p>{value.summary}</p>
        </section>
      )}

      {sections.map((section, index) => {
        const entries = section.entries || []
        const bullets = (section.bullets || []).filter(Boolean)
        if (!section.heading && !entries.length && !bullets.length) return null
        return (
          <section className="resume-paper-section" key={index}>
            <h2>{section.heading || 'Section'}</h2>
            {entries.map((entry, entryIndex) => <Entry entry={entry} key={entryIndex} />)}
            {bullets.length > 0 && <ul className="resume-generic-bullets">{bullets.map((bullet, bulletIndex) => <li key={bulletIndex}>{bullet}</li>)}</ul>}
          </section>
        )
      })}

      {skills.length > 0 && (
        <section className="resume-paper-section resume-skills-section">
          <h2>Technical Skills</h2>
          <div className="resume-paper-skills">{skills.map((skill, i) => <p key={i}><SkillLine value={skill} /></p>)}</div>
        </section>
      )}
    </article>
  )
}
