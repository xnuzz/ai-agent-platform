/**
 * Turns Agent 2 website-scan evidence (`source_type: WEBSITE_SCAN`, metadata.facts written by
 * agents/agent_2_local_leads/local_leads/analyzer) into display rows. Only measured facts are shown;
 * a check the scanner did not run is reported as "not measured", never as passed.
 */
import type { Evidence } from '@/api/types'

export type CheckStatus = 'ok' | 'issue' | 'info' | 'unmeasured'
export type Check = { label: string; status: CheckStatus; detail: string }
export type Facts = Record<string, any>

export interface WebsiteAnalysis {
  scanned: boolean
  skippedReason: string
  url: string
  retrievedAt: string | null
  mobile: Check[]
  accessibility: Check[]
  brokenLinks: { checked: number | null; broken: { url: string; status: number | null; error: string }[] }
  functionality: Check[]
  technical: Check[]
}

type ScanMeta = { facts?: Facts; scanned?: boolean; skipped_reason?: string; scanner?: string; code?: string }

/** The scan evidence (one per business) — not the per-finding WEBSITE_SCAN evidence, which carries `code`. */
export const isScanEvidence = (e: Evidence) => e.source_type === 'WEBSITE_SCAN' && !(e.metadata as ScanMeta)?.code && 'facts' in ((e.metadata as object) ?? {})

const has = (f: Facts, k: string) => Object.prototype.hasOwnProperty.call(f, k) && f[k] !== null && f[k] !== undefined
const yes = (label: string, ok: boolean, okText: string, badText: string): Check => ({ label, status: ok ? 'ok' : 'issue', detail: ok ? okText : badText })
const unmeasured = (label: string): Check => ({ label, status: 'unmeasured', detail: 'Not measured in this scan' })

export function analyse(e: Evidence | undefined): WebsiteAnalysis | null {
  if (!e) return null
  const meta = (e.metadata ?? {}) as ScanMeta
  const f: Facts = meta.facts ?? {}
  const vp = String(f.viewport ?? '').toLowerCase().replace(/\s/g, '')

  const mobile: Check[] = has(f, 'viewport')
    ? [yes('Responsive viewport', vp.includes('width=device-width'), 'width=device-width is set', f.viewport ? `Viewport "${f.viewport}" is not responsive` : 'No viewport meta tag — renders as a zoomed-out desktop page')]
    : [unmeasured('Responsive viewport')]
  if (vp.includes('user-scalable=no') || vp.includes('maximum-scale=1')) mobile.push({ label: 'Zoom', status: 'issue', detail: 'Pinch-zoom is disabled' })

  const a11y: Check[] = []
  if (Array.isArray(f.accessibility_issues)) {
    if (f.accessibility_issues.length) a11y.push(...f.accessibility_issues.map((t: string) => ({ label: 'Accessibility', status: 'issue' as const, detail: t })))
    else a11y.push({ label: 'Measured checks', status: 'ok', detail: 'Alt text, page language, form labels and zoom passed' })
  } else a11y.push(unmeasured('Accessibility'))
  if (has(f, 'images')) a11y.push({ label: 'Images without alt text', status: f.images_missing_alt ? 'info' : 'ok', detail: `${f.images_missing_alt ?? 0} of ${f.images}` })

  const links = (f.links ?? null) as { checked?: number; broken?: { url: string; status: number | null; error: string }[] } | null

  const functionality: Check[] = [
    has(f, 'contact_form') ? yes('Contact form', !!f.contact_form, 'Found', 'Not found on the homepage or contact page') : unmeasured('Contact form'),
    has(f, 'online_booking') ? yes('Online booking', !!f.online_booking, 'Found', 'No booking or reservation option found') : { label: 'Online booking', status: 'unmeasured', detail: 'Only checked for booking-type categories' },
    has(f, 'analytics_detected') ? yes('Visitor analytics', !!f.analytics_detected, 'Detected', 'No analytics script detected') : unmeasured('Visitor analytics'),
  ]

  const technical: Check[] = []
  if (has(f, 'https')) technical.push(yes('HTTPS', !!f.https, 'Served over HTTPS', 'Served over plain HTTP'))
  const tls = f.tls as { checked?: boolean; valid?: boolean; days_left?: number; not_after?: string; error?: string; issuer?: string } | undefined
  if (tls?.checked) {
    technical.push(tls.valid
      ? { label: 'TLS certificate', status: (tls.days_left ?? 99) <= 14 ? 'issue' : 'ok', detail: `Valid${tls.days_left != null ? `, expires in ${tls.days_left} days` : ''}${tls.issuer ? ` (${tls.issuer})` : ''}` }
      : { label: 'TLS certificate', status: 'issue', detail: tls.error || 'Not trusted by browsers' })
  }
  if (has(f, 'html_seconds')) technical.push({ label: 'Homepage HTML load', status: f.html_seconds > 3 ? 'issue' : 'ok', detail: `${Number(f.html_seconds).toFixed(2)} s · ${Math.round((f.html_bytes ?? 0) / 1024)} KB` })
  if (f.cms) technical.push({ label: 'CMS', status: 'info', detail: `${f.cms}${f.cms_version ? ` ${f.cms_version}` : ''}` })
  if (Array.isArray(f.security_headers_missing)) technical.push(yes('Security headers', !f.security_headers_missing.length, 'All checked headers present', `Missing: ${f.security_headers_missing.join(', ')}`))
  if (Array.isArray(f.insecure_resources) && f.insecure_resources.length) technical.push({ label: 'Mixed content', status: 'issue', detail: `${f.insecure_resources.length} resource(s) over HTTP` })
  if (Array.isArray(f.seo_issues)) technical.push(yes('On-page SEO', !f.seo_issues.length, 'No gaps found', f.seo_issues.join('; ')))
  if (has(f, 'title')) technical.push(yes('Title / meta description', !!f.title && !!f.meta_description, 'Both present', `Missing: ${[!f.title && 'title', !f.meta_description && 'meta description'].filter(Boolean).join(', ')}`))
  if (Array.isArray(f.legacy_markup) && f.legacy_markup.length) technical.push({ label: 'Legacy markup', status: 'issue', detail: f.legacy_markup.join('; ') })

  return {
    scanned: !!meta.scanned, skippedReason: meta.skipped_reason ?? '', url: e.url, retrievedAt: e.retrieved_at,
    mobile, accessibility: a11y, brokenLinks: { checked: links?.checked ?? null, broken: links?.broken ?? [] }, functionality, technical,
  }
}
