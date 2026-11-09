/**
 * DEVELOPMENT MOCK — never used in production.
 * Loaded only by `import.meta.env.DEV && ?demo=1` (LocalBusinessFinderView), so Vite drops it from
 * production builds. Fictional businesses at fixed, hand-picked coordinates in Sofia replay a research run
 * through the same store ingestion path as live data. The UI shows a "DEMO DATA" banner and disables actions.
 */
import type { Lead, ProjectBrief, ResearchTask } from '@/api/types'
import type { useLocalFinderStore } from '@/stores/localFinder'

type Store = ReturnType<typeof useLocalFinderStore>
type P = { code: string; title: string; severity: 'LOW' | 'MEDIUM' | 'HIGH' }

const TASK_ID = 'demo-task-0000-0000-000000000001'
// name, category, lat, lng (null = provider gave no coordinates), score, problems
const FIXTURES: [string, string, number | null, number | null, number, P[]][] = [
  ['Demo · Bella Restaurant', 'Restaurant', 42.69332, 23.32144, 85, [{ code: 'NO_ONLINE_BOOKING', title: 'No online booking or reservation option', severity: 'MEDIUM' }, { code: 'NOT_MOBILE_FRIENDLY', title: 'Not optimised for mobile devices', severity: 'HIGH' }]],
  ['Demo · Vitosha Dental', 'Dentist', 42.68412, 23.31655, 78, [{ code: 'OUTDATED_CMS', title: 'Outdated CMS version', severity: 'HIGH' }]],
  ['Demo · Lozenets Bakery', 'Bakery', 42.67951, 23.32602, 64, [{ code: 'NO_HTTPS', title: 'Website not served over HTTPS', severity: 'HIGH' }]],
  ['Demo · Studio Cut', 'Hair salon', 42.69760, 23.33421, 41, [{ code: 'MISSING_META', title: 'Missing title or meta description', severity: 'LOW' }]],
  ['Demo · Iztok Fitness', 'Gym', 42.67503, 23.35388, 72, [{ code: 'SLOW_PAGE_LOAD', title: 'Slow page load', severity: 'MEDIUM' }, { code: 'NO_CONTACT_FORM', title: 'No contact form', severity: 'MEDIUM' }]],
  ['Demo · Oborishte Vet', 'Veterinarian', 42.69741, 23.34303, 90, [{ code: 'NO_WEBSITE', title: 'No website found', severity: 'HIGH' }]],
  ['Demo · Florist Rosa', 'Florist', 42.69091, 23.31071, 55, [{ code: 'NO_ANALYTICS', title: 'No privacy-friendly visitor analytics', severity: 'LOW' }, { code: 'POOR_SEO', title: 'Basic on-page SEO gaps', severity: 'MEDIUM' }]],
  ['Demo · Mladost Auto Repair', 'Auto repair', 42.64953, 23.37912, 81, [{ code: 'WEBSITE_UNREACHABLE', title: 'Listed website does not respond', severity: 'HIGH' }]],
  ['Demo · Café Sredets', 'Cafe', 42.69628, 23.32557, 36, [{ code: 'SECURITY_HEADERS_MISSING', title: 'Missing HTTP security headers', severity: 'LOW' }]],
  ['Demo · Hotel Sofia Garden', 'Hotel', 42.68866, 23.33702, 76, [{ code: 'NO_ONLINE_BOOKING', title: 'No online booking or reservation option', severity: 'MEDIUM' }, { code: 'OUTDATED_DESIGN', title: 'Outdated page markup and design', severity: 'MEDIUM' }]],
  ['Demo · Lyulin Pharmacy', 'Pharmacy', null, null, 58, [{ code: 'ACCESSIBILITY_ISSUES', title: 'Accessibility issues', severity: 'MEDIUM' }]],
  ['Demo · Boyana Law Office', 'Lawyer', 42.64509, 23.26718, 69, [{ code: 'SSL_EXPIRING_SOON', title: 'TLS certificate expires soon', severity: 'MEDIUM' }]],
]

export function startDemoFeed(store: Store): () => void {
  store.demo = true
  const started = Date.now()
  const iso = (offset = 0) => new Date(started + offset).toISOString()
  const task: ResearchTask = {
    id: TASK_ID, agent: 'LOCAL_LEADS', task_type: 'LOCAL_LEAD_DISCOVERY', status: 'QUEUED',
    input: { location: { city: 'Sofia', country_code: 'BG', radius_km: 8, latitude: 42.6977, longitude: 23.3219 }, categories: [], max_businesses: FIXTURES.length },
    priority: 0, parent_task: null, software_idea: null, progress: 0, stage: '', progress_message: '', attempt: 0, max_attempts: 3,
    cancel_requested: false, error: {}, result_summary: {}, started_at: null, finished_at: null, heartbeat_at: null, created_by: null,
    created_at: iso(), updated_at: iso(),
  }
  store.ingestTasks([task], false)
  store.replaceLeads([], false)
  store.markLoaded()
  store.connection = 'live'

  const timers: number[] = []
  const at = (ms: number, fn: () => void) => timers.push(window.setTimeout(fn, ms))
  const update = (patch: Partial<ResearchTask>) => {
    Object.assign(task, patch, { updated_at: new Date().toISOString(), heartbeat_at: new Date().toISOString() })
    store.ingestTasks([{ ...task }])
  }
  const leads: Lead[] = []
  const briefs: ProjectBrief[] = []

  at(800, () => update({ status: 'RUNNING', started_at: new Date().toISOString(), progress: 5, stage: 'DISCOVERING_BUSINESSES', progress_message: 'Searching for businesses in Sofia, BG' }))
  FIXTURES.forEach(([name, category, lat, lng, score, problems], i) => {
    at(2500 + i * 1700, () => {
      const id = `demo-lead-${String(i).padStart(4, '0')}`
      const now = new Date().toISOString()
      const qualified = score >= 50
      leads.push({
        id, research_task: TASK_ID, source: 'LOCAL_LEADS', software_idea: null, status: qualified ? 'QUALIFIED' : 'DISQUALIFIED', score,
        qualification_notes: `Demo fixture. Score ${score} from ${problems.length} finding(s).`, problems, contact_name: '', contact_role: '',
        contact_email: '', contact_phone: '', contact_email_type: 'UNKNOWN', legal_basis: 'UNKNOWN', legal_basis_note: '', evidence_ids: [],
        is_suppressed: false, created_at: now, updated_at: now,
        business: {
          id: `demo-biz-${i}`, name, website: problems[0]!.code === 'NO_WEBSITE' ? '' : `https://example.com/demo-${i}`, domain: problems[0]!.code === 'NO_WEBSITE' ? '' : 'example.com',
          email: '', phone: '', address_line1: '', city: 'Sofia', region: '', postal_code: '', country_code: 'BG',
          latitude: lat == null ? null : lat.toFixed(6), longitude: lng == null ? null : lng.toFixed(6), category, description: 'Fictional business (demo data).',
          source_data: {}, created_at: now, updated_at: now,
        },
      })
      if (qualified) {
        briefs.push({
          id: `demo-brief-${i}`, lead: id, research_task: TASK_ID, title: `Website improvements for ${name}`, summary: 'Demo brief.', problems,
          proposed_solution: 'Demo solution.', scope_items: problems.map((p) => p.title), tech_stack: ['Static site'], estimated_effort_hours_min: 20,
          estimated_effort_hours_max: 40, estimated_budget_min: '1000.00', estimated_budget_max: '2000.00', currency: 'EUR', status: 'WAITING_FOR_APPROVAL',
          evidence_ids: [], approved_at: null, approved_by: null, created_at: now, updated_at: now,
        })
      }
      store.ingestBriefs([...briefs])
      store.ingestLeads([...leads])
      update({
        progress: Math.round(10 + ((i + 1) / FIXTURES.length) * 88), stage: i % 2 ? 'QUALIFYING' : 'SCANNING_WEBSITES',
        progress_message: `Processed ${i + 1} of ${FIXTURES.length} businesses`,
      })
    })
  })
  at(2500 + FIXTURES.length * 1700 + 800, () => update({ status: 'COMPLETED', progress: 100, stage: 'SUBMITTING', progress_message: 'Done', finished_at: new Date().toISOString() }))
  return () => timers.forEach((t) => window.clearTimeout(t))
}
