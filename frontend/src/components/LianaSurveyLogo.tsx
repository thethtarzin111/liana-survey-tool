/**
 * Stand-in LianaSurvey logo: a speech-bubble mark and the product name, in the
 * brand colours. Not the official logo. When Liana provides the logo file, put it
 * in src/assets/ and render it here instead; everything else uses this component.
 */
export function LianaSurveyLogo() {
  return (
    <span className="logo">
      <svg className="logo-mark" width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
        <rect width="26" height="26" rx="7" fill="currentColor" />
        <path
          d="M7 8.5h12a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5h-7l-3.5 3v-3H7A1.5 1.5 0 0 1 5.5 16v-6A1.5 1.5 0 0 1 7 8.5z"
          fill="var(--color-surface)"
        />
        <path d="M9.5 13l2 2 4.5-4.5" fill="none" stroke="var(--color-brand-dark)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="logo-name">
        Liana<strong>Survey</strong>
      </span>
    </span>
  );
}
