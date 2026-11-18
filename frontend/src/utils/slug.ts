/**
 * "Jäsenkysely 2026" → "jasenkysely-2026": the campaign tag of a survey (the "Tag …"
 * on live surveys, the newsletter snippet's default campaign, the QR file name).
 * Keep in sync with campaign_tag() in survey-manager's surveys/domain.py.
 */
export function slug(text: string): string {
  const tag = text
    .normalize('NFKD')
    .replace(/\p{M}/gu, '') // ä → a, é → e
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
    .replace(/-+$/, '');
  return tag || 'campaign';
}
