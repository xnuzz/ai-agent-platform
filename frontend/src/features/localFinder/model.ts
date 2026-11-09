/**
 * Agent 2 dashboard: pure view-model derivations (no I/O, no Vue).
 *
 * Every value here is derived from backend data (`Lead`, `ProjectBrief`, `ResearchTask`). The
 * "review state", "potential" and "agent state" labels are DISPLAY groupings over the canonical
 * statuses in backend/apps/common/enums.py — they are never sent to the API.
 */
import type { Lead, ProjectBrief, ResearchTask } from '@/api/types'

export type Problem = { code: string; title?: string; severity?: 'LOW' | 'MEDIUM' | 'HIGH'; description?: string; evidence_ids?: string[] }
export type Potential = 'high' | 'medium' | 'low' | 'unscored'
export type ReviewState = 'new' | 'reviewed' | 'approved' | 'rejected'
export type MarkerTone = 'new' | 'hot' | 'reviewed' | 'approved' | 'rejected'
export type LeadFilter = 'all' | 'high' | 'medium' | 'low' | 'new' | 'reviewed' | 'approved' | 'rejected'
export type LeadSort = 'recent' | 'score' | 'name' | 'problems'
/** Display state of the agent, derived from the latest Agent 2 task (TaskStatus) and its heartbeat. */
export type AgentState = 'IDLE' | 'WAITING' | 'SCANNING' | 'UNRESPONSIVE' | 'COMPLETED' | 'FAILED' | 'STOPPED'

export const HIGH_SCORE = 75
export const MEDIUM_SCORE = 50
/** A RUNNING task whose last heartbeat is older than this is shown as unresponsive (SDK beats every 60 s). */
export const STALE_HEARTBEAT_MS = 150_000
/** A QUEUED task nobody claimed for this long means no Agent 2 worker is connected. */
export const UNCLAIMED_MS = 30_000

/** Problem codes that mean "website missing or outdated" (AGENT_2_CONTRACT.md vocabulary). */
export const WEBSITE_GAP_CODES = new Set(['NO_WEBSITE', 'WEBSITE_UNREACHABLE', 'OUTDATED_CMS', 'OUTDATED_DESIGN', 'NOT_MOBILE_FRIENDLY'])

const SEVERITY_RANK: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 }

export const problemsOf = (l: Lead): Problem[] => (Array.isArray(l.problems) ? (l.problems as Problem[]) : [])

/** The most severe problem — the one-line "identified problem" on cards, popups and notifications. */
export function topProblem(l: Lead): Problem | null {
  return [...problemsOf(l)].sort((a, b) => (SEVERITY_RANK[b.severity ?? ''] ?? 0) - (SEVERITY_RANK[a.severity ?? ''] ?? 0))[0] ?? null
}
export const problemLabel = (p: Problem | null) => (p ? p.title || p.code.replace(/_/g, ' ').toLowerCase() : '')

export function potentialOf(score: number | null | undefined): Potential {
  if (score == null) return 'unscored'
  return score >= HIGH_SCORE ? 'high' : score >= MEDIUM_SCORE ? 'medium' : 'low'
}

/**
 * Review state: from the lead's project brief when there is one (brief approval gates launch, ADR-006),
 * otherwise from the lead status. Agent-DISQUALIFIED leads are still "new" (nobody reviewed them).
 */
export function reviewStateOf(l: Lead, brief?: ProjectBrief | null): ReviewState {
  if (['CONTACTED', 'REPLIED', 'WON'].includes(l.status)) return 'approved'
  if (['LOST', 'ARCHIVED'].includes(l.status)) return 'rejected'
  switch (brief?.status) {
    case 'APPROVED': return 'approved'
    case 'REJECTED': case 'ARCHIVED': return 'rejected'
    case 'CHANGES_REQUESTED': return 'reviewed'
    default: return 'new'
  }
}

export function markerTone(state: ReviewState, potential: Potential): MarkerTone {
  if (state === 'new') return potential === 'high' ? 'hot' : 'new'
  return state
}

export const REVIEW_LABEL: Record<ReviewState, string> = {
  new: 'New discovery', reviewed: 'Reviewed', approved: 'Approved', rejected: 'Rejected',
}
export const POTENTIAL_LABEL: Record<Potential, string> = {
  high: 'High potential', medium: 'Medium potential', low: 'Low potential', unscored: 'Not scored',
}

/** Backend coordinates are decimal strings. Missing, malformed, out-of-range or (0,0) → null: never guess a position. */
export function coordsOf(l: Lead): [number, number] | null {
  const { latitude, longitude } = l.business
  if (latitude == null || longitude == null || latitude === '' || longitude === '') return null
  const lat = Number(latitude), lng = Number(longitude)
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return null
  if (lat === 0 && lng === 0) return null
  return [lng, lat]
}

export function locationLabel(l: Lead): string {
  const b = l.business
  const country = b.country_code ? countryName(b.country_code) : ''
  return [b.city, country].filter(Boolean).join(', ') || b.address_line1 || 'Location unknown'
}

let regionNames: Intl.DisplayNames | null = null
export function countryName(code: string): string {
  try {
    regionNames ??= new Intl.DisplayNames(['en'], { type: 'region' })
    return regionNames.of(code.toUpperCase()) ?? code
  } catch {
    return code
  }
}

export interface LeadRow {
  lead: Lead
  brief: ProjectBrief | null
  potential: Potential
  review: ReviewState
  tone: MarkerTone
  coords: [number, number] | null
  problem: Problem | null
}

export function toRow(lead: Lead, brief: ProjectBrief | null): LeadRow {
  const potential = potentialOf(lead.score)
  const review = reviewStateOf(lead, brief)
  return { lead, brief, potential, review, tone: markerTone(review, potential), coords: coordsOf(lead), problem: topProblem(lead) }
}

export function matchesFilter(r: LeadRow, f: LeadFilter): boolean {
  if (f === 'all') return true
  if (f === 'high' || f === 'medium' || f === 'low') return r.potential === f
  return r.review === f
}

export function matchesSearch(r: LeadRow, q: string): boolean {
  if (!q) return true
  const b = r.lead.business
  const hay = [b.name, b.category, b.city, b.region, b.domain, b.address_line1, ...problemsOf(r.lead).map((p) => `${p.code} ${p.title ?? ''}`)]
    .join(' ').toLowerCase()
  return q.toLowerCase().split(/\s+/).filter(Boolean).every((t) => hay.includes(t))
}

export function sortRows(rows: LeadRow[], sort: LeadSort): LeadRow[] {
  const by: Record<LeadSort, (a: LeadRow, b: LeadRow) => number> = {
    recent: (a, b) => b.lead.created_at.localeCompare(a.lead.created_at),
    score: (a, b) => (b.lead.score ?? -1) - (a.lead.score ?? -1),
    name: (a, b) => a.lead.business.name.localeCompare(b.lead.business.name),
    problems: (a, b) => problemsOf(b.lead).length - problemsOf(a.lead).length,
  }
  return [...rows].sort((a, b) => by[sort](a, b) || a.lead.id.localeCompare(b.lead.id))
}

// ------------------------------------------------------------------ agent state

export function agentStateOf(task: ResearchTask | null, now = Date.now()): AgentState {
  if (!task) return 'IDLE'
  switch (task.status) {
    case 'QUEUED': return 'WAITING'
    case 'RUNNING': {
      const beat = Date.parse(task.heartbeat_at ?? task.started_at ?? task.updated_at)
      return Number.isFinite(beat) && now - beat > STALE_HEARTBEAT_MS ? 'UNRESPONSIVE' : 'SCANNING'
    }
    case 'COMPLETED': return 'COMPLETED'
    case 'FAILED': return 'FAILED'
    case 'CANCELLED': return 'STOPPED'
    default: return 'IDLE'
  }
}

export const isActive = (t: ResearchTask | null | undefined) => t?.status === 'QUEUED' || t?.status === 'RUNNING'
/** True when a QUEUED task has waited long enough that no Agent 2 worker is evidently polling. */
export const isUnclaimed = (t: ResearchTask | null, now = Date.now()) =>
  t?.status === 'QUEUED' && now - Date.parse(t.created_at) > UNCLAIMED_MS

export type DiscoveryInput = {
  location: { city: string; country_code: string; region?: string; radius_km?: number; latitude?: number; longitude?: number }
  categories?: string[]; max_businesses?: number; checks?: string[]; min_score?: number; language?: string; notes?: string
}
export const taskInput = (t: ResearchTask | null): DiscoveryInput | null =>
  t && t.task_type === 'LOCAL_LEAD_DISCOVERY' ? (t.input as DiscoveryInput) : null

export function taskArea(t: ResearchTask | null): string {
  const loc = taskInput(t)?.location
  if (!loc) return '—'
  return [loc.city, loc.region, loc.country_code && countryName(loc.country_code)].filter(Boolean).join(', ')
}

// ------------------------------------------------------------------ analytics

export interface Kpis {
  discovered: number
  scanned: number
  qualified: number
  high: number
  websiteGaps: number
  opportunities: number
  qualifiedRate: number
  discovered24h: number
  qualified24h: number
  mapped: number
}

const QUALIFIED_STATUSES = new Set(['QUALIFIED', 'CONTACTED', 'REPLIED', 'WON'])

export function kpis(rows: LeadRow[], now = Date.now()): Kpis {
  const dayAgo = now - 86_400_000
  let scanned = 0, qualified = 0, high = 0, websiteGaps = 0, opportunities = 0, discovered24h = 0, qualified24h = 0, mapped = 0
  for (const r of rows) {
    const probs = problemsOf(r.lead)
    const recent = Date.parse(r.lead.created_at) >= dayAgo
    if (r.lead.business.website) scanned++
    if (QUALIFIED_STATUSES.has(r.lead.status)) { qualified++; if (recent) qualified24h++ }
    if (r.potential === 'high') high++
    if (probs.some((p) => WEBSITE_GAP_CODES.has(p.code))) websiteGaps++
    opportunities += probs.length
    if (recent) discovered24h++
    if (r.coords) mapped++
  }
  return {
    discovered: rows.length, scanned, qualified, high, websiteGaps, opportunities, mapped,
    qualifiedRate: rows.length ? Math.round((qualified / rows.length) * 100) : 0, discovered24h, qualified24h,
  }
}

export type TimePoint = { t: number; label: string; count: number; cumulative: number }

/**
 * Discoveries over time, bucketed by 5 min (span ≤ 2 h), hour (≤ 48 h) or day. Empty buckets are kept so the
 * time axis is honest, and a leading zero bucket shows the start of the run.
 */
export function discoveriesOverTime(rows: LeadRow[], maxBuckets = 30): TimePoint[] {
  if (!rows.length) return []
  const times = rows.map((r) => Date.parse(r.lead.created_at)).filter(Number.isFinite).sort((a, b) => a - b)
  if (!times.length) return []
  const first = times[0]!, last = times[times.length - 1]!
  const span = last - first
  const step = span <= 2 * 3_600_000 ? 300_000 : span <= 48 * 3_600_000 ? 3_600_000 : 86_400_000
  const floor = (t: number) => {
    if (step < 86_400_000) return Math.floor(t / step) * step
    const d = new Date(t)
    d.setHours(0, 0, 0, 0)
    return d.getTime()
  }
  const end = floor(last)
  let start = floor(first) - step // leading empty bucket: nothing discovered before the first result
  if ((end - start) / step + 1 > maxBuckets) start = end - (maxBuckets - 1) * step
  const counts = new Map<number, number>()
  let before = 0
  for (const t of times) {
    const k = floor(t)
    if (k < start) before++
    else counts.set(k, (counts.get(k) ?? 0) + 1)
  }
  const fmt = step < 86_400_000
    ? (t: number) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : (t: number) => new Date(t).toLocaleDateString([], { month: 'short', day: 'numeric' })
  const out: TimePoint[] = []
  let cumulative = before
  for (let t = start; t <= end; t += step) {
    const count = counts.get(t) ?? 0
    cumulative += count
    out.push({ t, label: fmt(t), count, cumulative })
  }
  return out
}

export type CategoryStat = { category: string; discovered: number; qualified: number; opportunities: number }

/** Qualified opportunities per business category (top N, remainder folded into "Other"). */
export function byCategory(rows: LeadRow[], top = 6): CategoryStat[] {
  const map = new Map<string, CategoryStat>()
  for (const r of rows) {
    const key = r.lead.business.category?.trim() || 'Uncategorised'
    const s = map.get(key) ?? { category: key, discovered: 0, qualified: 0, opportunities: 0 }
    s.discovered++
    if (QUALIFIED_STATUSES.has(r.lead.status)) s.qualified++
    s.opportunities += problemsOf(r.lead).length
    map.set(key, s)
  }
  const all = [...map.values()].sort((a, b) => b.qualified - a.qualified || b.discovered - a.discovered || a.category.localeCompare(b.category))
  if (all.length <= top) return all
  const rest = all.slice(top - 1).reduce((o, s) => ({
    category: 'Other', discovered: o.discovered + s.discovered, qualified: o.qualified + s.qualified, opportunities: o.opportunities + s.opportunities,
  }), { category: 'Other', discovered: 0, qualified: 0, opportunities: 0 })
  return [...all.slice(0, top - 1), rest]
}

export type ScoreBucket = { from: number; to: number; count: number; potential: Potential }

/** Lead score histogram in 10-point buckets (90–100 is the last, inclusive). */
export function scoreDistribution(rows: LeadRow[]): ScoreBucket[] {
  const buckets: ScoreBucket[] = Array.from({ length: 10 }, (_, i) => ({
    from: i * 10, to: i === 9 ? 100 : i * 10 + 9, count: 0, potential: potentialOf(i * 10),
  }))
  for (const r of rows) {
    if (r.lead.score == null) continue
    buckets[Math.min(9, Math.floor(r.lead.score / 10))]!.count++
  }
  return buckets
}

/** Rough complexity label from the agent's effort estimate (labelled as derived in the UI). */
export function complexityOf(maxHours: number | null | undefined): 'Low' | 'Medium' | 'High' | null {
  if (maxHours == null) return null
  return maxHours <= 40 ? 'Low' : maxHours <= 120 ? 'Medium' : 'High'
}

export const compact = (n: number) => (n >= 10_000 ? new Intl.NumberFormat('en', { notation: 'compact' }).format(n) : n.toLocaleString('en'))
