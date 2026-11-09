/**
 * Static option lists for the research configuration form.
 * Problem codes come from docs/AGENT_2_CONTRACT.md; categories mirror the ones Agent 2's OSM provider
 * maps to tags (agents/agent_2_local_leads/local_leads/discovery/osm.py) — free text is also accepted.
 */
import { countryName } from './model'

export const CATEGORY_SUGGESTIONS = [
  'Restaurant', 'Cafe', 'Bakery', 'Bar', 'Hotel', 'Guest house', 'Dentist', 'Doctor', 'Clinic', 'Pharmacy',
  'Veterinarian', 'Physiotherapist', 'Optician', 'Hair salon', 'Beauty salon', 'Gym', 'Yoga', 'Florist',
  'Butcher', 'Bookstore', 'Clothing', 'Dry cleaning', 'Tattoo', 'Photographer', 'Auto repair', 'Plumber',
  'Electrician', 'Carpenter', 'Painter', 'Lawyer', 'Accountant', 'Real estate', 'Driving school',
]

/** Development services offered → the Agent 2 checks (`checks` input) that find demand for them. */
export const SERVICES: { id: string; label: string; hint: string; checks: string[] }[] = [
  { id: 'new-site', label: 'New website', hint: 'No site, or the listed site is down', checks: ['NO_WEBSITE', 'WEBSITE_UNREACHABLE'] },
  { id: 'redesign', label: 'Redesign & mobile', hint: 'Outdated design/CMS, not mobile friendly', checks: ['OUTDATED_DESIGN', 'OUTDATED_CMS', 'NOT_MOBILE_FRIENDLY'] },
  { id: 'booking', label: 'Online booking', hint: 'No reservation or booking option', checks: ['NO_ONLINE_BOOKING'] },
  { id: 'conversion', label: 'Contact & conversion', hint: 'No contact form', checks: ['NO_CONTACT_FORM'] },
  { id: 'security', label: 'Security & SSL', hint: 'HTTPS, certificates, headers, mixed content', checks: ['NO_HTTPS', 'NO_HTTPS_REDIRECT', 'SSL_EXPIRED', 'SSL_INVALID_CERTIFICATE', 'SSL_EXPIRING_SOON', 'MIXED_CONTENT', 'SECURITY_HEADERS_MISSING'] },
  { id: 'performance', label: 'Performance', hint: 'Slow pages, broken links', checks: ['SLOW_PAGE_LOAD', 'BROKEN_LINKS'] },
  { id: 'seo', label: 'SEO & analytics', hint: 'On-page SEO, meta tags, analytics', checks: ['POOR_SEO', 'MISSING_META', 'NO_ANALYTICS'] },
  { id: 'accessibility', label: 'Accessibility', hint: 'Alt text, labels, language, zoom', checks: ['ACCESSIBILITY_ISSUES'] },
]

export const LANGUAGES = [
  ['en', 'English'], ['bg', 'Bulgarian'], ['de', 'German'], ['fr', 'French'], ['es', 'Spanish'], ['it', 'Italian'],
  ['nl', 'Dutch'], ['pl', 'Polish'], ['pt', 'Portuguese'], ['ro', 'Romanian'], ['el', 'Greek'], ['cs', 'Czech'],
] as const

// Codes Intl.DisplayNames knows but that are not countries.
const NOT_COUNTRIES = new Set(['EU', 'EZ', 'UN', 'QO', 'ZZ', 'XA', 'XB', 'AA', 'QM', 'QN', 'QP', 'QQ', 'QR', 'QS', 'QT', 'QU', 'QV', 'QW', 'QX', 'QY', 'QZ'])
let countries: { code: string; name: string }[] | null = null

/** ISO 3166-1 alpha-2 countries with English names, from the browser's own region data. */
export function countryOptions(): { code: string; name: string }[] {
  if (countries) return countries
  const out: { code: string; name: string }[] = []
  for (let a = 65; a <= 90; a++) {
    for (let b = 65; b <= 90; b++) {
      const code = String.fromCharCode(a, b)
      if (NOT_COUNTRIES.has(code)) continue
      const name = countryName(code)
      if (name && name !== code) out.push({ code, name })
    }
  }
  countries = out.sort((x, y) => x.name.localeCompare(y.name))
  return countries
}

/** Approximate country bounding boxes [west, south, east, north] — used ONLY to frame the empty map. */
export const COUNTRY_BOUNDS: Record<string, [number, number, number, number]> = {
  BG: [22.36, 41.24, 28.61, 44.22], RO: [20.26, 43.62, 29.7, 48.27], GR: [19.37, 34.8, 28.25, 41.75],
  RS: [18.82, 42.23, 23.01, 46.19], MK: [20.45, 40.85, 23.04, 42.37], TR: [25.66, 35.82, 44.82, 42.11],
  DE: [5.87, 47.27, 15.04, 55.06], AT: [9.53, 46.37, 17.16, 49.02], CH: [5.96, 45.82, 10.49, 47.81],
  FR: [-5.14, 41.33, 9.56, 51.09], ES: [-9.39, 35.95, 3.32, 43.79], PT: [-9.53, 36.84, -6.19, 42.15],
  IT: [6.63, 36.62, 18.52, 47.09], NL: [3.31, 50.75, 7.23, 53.56], BE: [2.54, 49.5, 6.41, 51.5],
  PL: [14.12, 49.0, 24.15, 54.84], CZ: [12.09, 48.55, 18.86, 51.06], SK: [16.83, 47.73, 22.57, 49.61],
  HU: [16.11, 45.74, 22.9, 48.59], HR: [13.49, 42.39, 19.45, 46.55], SI: [13.38, 45.42, 16.61, 46.88],
  GB: [-8.65, 49.86, 1.77, 60.86], IE: [-10.48, 51.42, -5.99, 55.39], DK: [8.07, 54.56, 15.2, 57.75],
  SE: [11.11, 55.34, 24.17, 69.06], NO: [4.65, 57.98, 31.1, 71.18], FI: [20.55, 59.81, 31.59, 70.09],
  US: [-124.73, 24.52, -66.95, 49.38], CA: [-141.0, 41.68, -52.62, 83.11], AU: [113.34, -43.63, 153.57, -10.67],
}
