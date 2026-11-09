/**
 * Agent 2 live events.
 *
 * The platform has no push transport yet (INTEGRATION_STATUS: "Live updates (SSE/WebSocket) ⬜ — UI polls").
 * The dashboard therefore derives the documented event vocabulary by diffing successive API snapshots.
 * If an SSE/WebSocket endpoint is added later, only the transport in `liveFeed.ts` changes: the store
 * consumes these same event objects.
 */
import type { Lead, ResearchTask } from '@/api/types'

export type DiscoveryEvent =
  | { type: 'research.started'; task: ResearchTask }
  | { type: 'research.progress'; task: ResearchTask }
  | { type: 'research.completed'; task: ResearchTask }
  | { type: 'research.failed'; task: ResearchTask }
  | { type: 'research.cancelled'; task: ResearchTask }
  | { type: 'business.discovered'; lead: Lead }
  | { type: 'business.updated'; lead: Lead; previous: Lead }
  | { type: 'business.qualified'; lead: Lead }

export type EventType = DiscoveryEvent['type']

const QUALIFIED = 'QUALIFIED'

/** Events for leads in `next` compared with the `known` snapshot (by id). Unchanged leads emit nothing. */
export function diffLeads(known: Record<string, Lead>, next: Lead[]): DiscoveryEvent[] {
  const out: DiscoveryEvent[] = []
  for (const lead of next) {
    const prev = known[lead.id]
    if (!prev) {
      out.push({ type: 'business.discovered', lead })
      if (lead.status === QUALIFIED) out.push({ type: 'business.qualified', lead })
    } else if (prev.updated_at !== lead.updated_at || prev.status !== lead.status || prev.business.updated_at !== lead.business.updated_at) {
      out.push({ type: 'business.updated', lead, previous: prev })
      if (lead.status === QUALIFIED && prev.status !== QUALIFIED) out.push({ type: 'business.qualified', lead })
    }
  }
  return out
}

/** Lifecycle/progress events for one task between two polls. `prev` undefined = first sighting. */
export function diffTask(prev: ResearchTask | undefined, next: ResearchTask): DiscoveryEvent[] {
  if (prev && prev.updated_at === next.updated_at && prev.status === next.status && prev.progress === next.progress) return []
  const out: DiscoveryEvent[] = []
  const changed = !prev || prev.status !== next.status
  if (changed && next.status === 'RUNNING') out.push({ type: 'research.started', task: next })
  if (next.status === 'RUNNING' && prev && (prev.progress !== next.progress || prev.stage !== next.stage || prev.progress_message !== next.progress_message)) {
    out.push({ type: 'research.progress', task: next })
  }
  // Terminal transitions are only events when we saw the task before (not when loading history).
  if (prev && changed) {
    if (next.status === 'COMPLETED') out.push({ type: 'research.completed', task: next })
    if (next.status === 'FAILED') out.push({ type: 'research.failed', task: next })
    if (next.status === 'CANCELLED') out.push({ type: 'research.cancelled', task: next })
  }
  return out
}
