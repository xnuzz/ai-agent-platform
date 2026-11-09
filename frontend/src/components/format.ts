export const fmtDate = (v?: string | null) => (v ? new Date(v).toLocaleString() : '—')
export const agentLabel = (a?: string) => ({ SAAS_RESEARCH: 'Agent 1 · SaaS research', LOCAL_LEADS: 'Agent 2 · Local leads', MANUAL: 'Manual' })[a ?? ''] ?? a ?? '—'
export const taskLabel = (t?: string) => ({
  SAAS_OPPORTUNITY_RESEARCH: 'Opportunity research', SAAS_CUSTOMER_RESEARCH: 'Customer research', LOCAL_LEAD_DISCOVERY: 'Local lead discovery',
})[t ?? ''] ?? t ?? '—'
/** Deep copy of plain API data (also safe for Vue reactive proxies, unlike structuredClone). */
export const clone = <T>(v: T): T => (v === undefined ? v : JSON.parse(JSON.stringify(v)))
