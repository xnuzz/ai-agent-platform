/**
 * Agent 2 (Local Business Finder) API calls — existing documented endpoints only (docs/API_CONTRACTS.md).
 * UI components never call `api` directly for this feature; they go through the store or these functions.
 */
import { api } from './client'
import type {
  Approval, ApprovalDecision, Campaign, DashboardSummary, Evidence, Lead, OutreachMessage, Paginated, ProjectBrief, ResearchTask,
  ResearchTaskDetail,
} from './types'
import type { DiscoveryInput } from '@/features/localFinder/model'

const PAGE = 100

/** Follows `page` until exhausted or `maxPages` (protects the browser on very large workspaces). */
async function all<T>(path: string, query: Record<string, string | number | undefined>, maxPages = 10): Promise<{ items: T[]; truncated: boolean }> {
  const items: T[] = []
  for (let page = 1; page <= maxPages; page++) {
    const r = await api.get<Paginated<T>>(path, { ...query, page, page_size: PAGE })
    items.push(...r.results)
    if (!r.next) return { items, truncated: false }
  }
  return { items, truncated: true }
}

export const localFinderApi = {
  // ---- research tasks
  tasks: () => api.get<Paginated<ResearchTask>>('research-tasks/', { agent: 'LOCAL_LEADS', ordering: '-created_at', page_size: 20 }).then((r) => r.results),
  task: (id: string) => api.get<ResearchTaskDetail>(`research-tasks/${id}/`),
  startDiscovery: (input: DiscoveryInput) => api.post<ResearchTask>('research-tasks/', { task_type: 'LOCAL_LEAD_DISCOVERY', input }),
  cancelTask: (id: string) => api.post<ResearchTask>(`research-tasks/${id}/cancel/`),
  retryTask: (id: string) => api.post<ResearchTask>(`research-tasks/${id}/retry/`),

  // ---- leads + briefs (Agent 2 only)
  allLeads: () => all<Lead>('leads/', { source: 'LOCAL_LEADS', ordering: '-created_at' }),
  taskLeads: (taskId: string) => all<Lead>('leads/', { research_task: taskId, ordering: '-created_at' }, 3),
  allBriefs: () => all<ProjectBrief>('project-briefs/', {}),
  taskBriefs: (taskId: string) => all<ProjectBrief>('project-briefs/', { research_task: taskId }, 3),
  lead: (id: string) => api.get<Lead>(`leads/${id}/`),
  setLeadStatus: (id: string, status: string) => api.post<Lead>(`leads/${id}/set-status/`, { status }),
  briefsForLead: (leadId: string) => api.get<Paginated<ProjectBrief>>('project-briefs/', { lead: leadId }).then((r) => r.results),

  // ---- evidence (website scan facts, listing, findings)
  evidence: (id: string) => api.get<Evidence>(`evidence/${id}/`),

  // ---- approvals
  approvalsFor: (targetId: string) =>
    api.get<Paginated<Approval>>('approvals/', { target_id: targetId, ordering: '-created_at', page_size: 5 }).then((r) => r.results),
  decide: (approvalId: string, decision: ApprovalDecision, comment = '') =>
    api.post<Approval>(`approvals/${approvalId}/decide/`, { decision, comment }),

  // ---- outreach
  messagesForLead: (leadId: string) =>
    api.get<Paginated<OutreachMessage>>('outreach-messages/', { lead: leadId, page_size: 100 }).then((r) => r.results),
  campaign: (id: string) => api.get<Campaign>(`campaigns/${id}/`),
  patchCampaign: (id: string, body: Partial<Pick<Campaign, 'name' | 'offer'>>) => api.patch<Campaign>(`campaigns/${id}/`, body),
  patchMessage: (id: string, body: { subject: string; body: string }) => api.patch<OutreachMessage>(`outreach-messages/${id}/`, body),
  submitCampaign: (id: string, summary = '') => api.post<Approval>(`campaigns/${id}/submit/`, { summary }),

  summary: () => api.get<DashboardSummary>('dashboard/summary/'),
}
