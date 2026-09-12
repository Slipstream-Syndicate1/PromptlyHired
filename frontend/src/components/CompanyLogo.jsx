/** A company's logo, or its first letter when the source has none. */
export default function CompanyLogo({ company, size = 'md' }) {
  if (company.logo_url) {
    return (
      <img className={`jc-logo jc-logo-${size}`} src={company.logo_url} alt="" loading="lazy" />
    )
  }
  return (
    <div className={`jc-logo jc-logo-${size} jc-logo-fallback`} aria-hidden="true">
      {(company.name || '?').slice(0, 1).toUpperCase()}
    </div>
  )
}
