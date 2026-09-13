export default function ResumePreview({ value, className = '' }) {
  const sections = value?.sections || []
  const skills = value?.skills || []

  return (
    <article className={`resume-paper ${className}`.trim()} aria-label="Resume preview">
      <header className="resume-paper-header">
        <h1>{value?.full_name || 'Your Name'}</h1>
        {value?.headline && <p className="resume-paper-headline">{value.headline}</p>}
      </header>

      {value?.summary && (
        <section className="resume-paper-section">
          <h2>Summary</h2>
          <p>{value.summary}</p>
        </section>
      )}

      {sections.map((section, index) => {
        const bullets = (section.bullets || []).filter(Boolean)
        if (!section.heading && !bullets.length) return null
        return (
          <section className="resume-paper-section" key={index}>
            <h2>{section.heading || 'Section'}</h2>
            {bullets.length > 0 && (
              <ul>{bullets.map((bullet, bulletIndex) => <li key={bulletIndex}>{bullet}</li>)}</ul>
            )}
          </section>
        )
      })}

      {skills.filter(Boolean).length > 0 && (
        <section className="resume-paper-section">
          <h2>Skills</h2>
          <p className="resume-paper-skills">{skills.filter(Boolean).join(' · ')}</p>
        </section>
      )}
    </article>
  )
}
