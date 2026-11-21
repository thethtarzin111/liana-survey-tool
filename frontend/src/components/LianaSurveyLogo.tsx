import logo from '../assets/lianasurvey-logo.png';

/**
 * The LianaSurvey logo (green checklist and "lianasurvey"), trimmed and with a
 * transparent background. Decorative: the link around it carries the name.
 * To change the logo, replace src/assets/lianasurvey-logo.png.
 */
export function LianaSurveyLogo() {
  return <img className="logo" src={logo} alt="" width={169} height={28} />;
}
