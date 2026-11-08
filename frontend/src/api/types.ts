// Aliases over generated OpenAPI types (src/api/schema.d.ts — regenerate with `npm run gen:api`).
import type { components } from './schema'

type S = components['schemas']
export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] }

export type User = S['User']
export type Workspace = S['Workspace']
export type ResearchTask = S['ResearchTask']
export type ResearchTaskDetail = S['ResearchTaskDetail']
export type TaskType = S['TaskTypeEnum']
export type Opportunity = S['Opportunity']
export type SoftwareIdea = S['SoftwareIdea']
export type Lead = S['Lead']
export type ProjectBrief = S['ProjectBrief']
export type Campaign = S['Campaign']
export type OutreachMessage = S['OutreachMessage']
export type Approval = S['Approval']
export type ApprovalDecision = S['ApprovalDecisionEnum']
export type SuppressionEntry = S['SuppressionEntry']
export type AuditEvent = S['AuditEvent']

export interface DashboardSummary {
  research_tasks: Record<string, number>
  active_tasks_by_agent: Record<string, number>
  pending_approvals: Record<string, number>
  opportunities: Record<string, number>
  software_ideas: Record<string, number>
  leads: Record<string, number>
  leads_by_source: Record<string, number>
  project_briefs: Record<string, number>
  campaigns: Record<string, number>
  outreach_messages: Record<string, number>
}
