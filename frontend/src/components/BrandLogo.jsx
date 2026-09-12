export default function BrandLogo({ compact = false }) {
  return (
    <div
      className={`brand-logo ${compact ? "brand-logo-compact" : ""}`}
      aria-label="PromptlyHired"
    >
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 36 36" fill="none">
          <path
            d="M8 25.5V11.8c0-1.1.9-2 2-2h11.2c3.8 0 6.8 3 6.8 6.8s-3 6.8-6.8 6.8H14"
            stroke="currentColor"
            strokeWidth="3.2"
            strokeLinecap="round"
          />
          <path
            d="M8 18h12.2"
            stroke="currentColor"
            strokeWidth="3.2"
            strokeLinecap="round"
          />
          <path
            d="m22.8 21.4 4 4"
            stroke="currentColor"
            strokeWidth="3.2"
            strokeLinecap="round"
          />
        </svg>
      </span>
      {!compact && (
        <span className="brand-wordmark">
          Promptly<span>Hired</span>
        </span>
      )}
    </div>
  );
}
