/**
 * Data for the business detail workspace: the lead, its project brief and outreach campaign with their
 * approvals, and the evidence behind every finding. Loaded on open, reloaded after each action.
 */
import { computed, ref, watch, type Ref } from 'vue'
import { errorText } from '@/api/client'
import { localFinderApi as api } from '@/api/localFinder'
import type { Approval, Campaign, Evidence, Lead, OutreachMessage, ProjectBrief } from '@/api/types'
import { problemsOf } from './model'

export function useLeadWorkspace(leadId: Ref<string | null>) {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lead = ref<Lead | null>(null)
  const brief = ref<ProjectBrief | null>(null)
  const briefApprovals = ref<Approval[]>([])
  const messages = ref<OutreachMessage[]>([])
  const campaign = ref<Campaign | null>(null)
  const campaignApprovals = ref<Approval[]>([])
  const evidence = ref<Evidence[]>([])
  let seq = 0

  async function load(id: string | null, quiet = false) {
    const mine = ++seq
    if (!id) return
    if (!quiet) { loading.value = true; lead.value = null; brief.value = null; campaign.value = null; evidence.value = []; messages.value = [] }
    error.value = null
    try {
      const [l, briefs, msgs] = await Promise.all([api.lead(id), api.briefsForLead(id), api.messagesForLead(id)])
      const b = briefs.sort((x, y) => y.created_at.localeCompare(x.created_at))[0] ?? null
      const campaignId = msgs.find((m) => m.sequence_step === 1)?.campaign ?? msgs[0]?.campaign
      const evIds = [...new Set([...l.evidence_ids, ...problemsOf(l).flatMap((p) => p.evidence_ids ?? [])])].slice(0, 40)
      const [bApprovals, c, cApprovals, ev] = await Promise.all([
        b ? api.approvalsFor(b.id) : Promise.resolve([]),
        campaignId ? api.campaign(campaignId) : Promise.resolve(null),
        campaignId ? api.approvalsFor(campaignId) : Promise.resolve([]),
        Promise.all(evIds.map((e) => api.evidence(e).catch(() => null))),
      ])
      if (mine !== seq) return // a newer lead was opened meanwhile
      lead.value = l; brief.value = b; briefApprovals.value = bApprovals; messages.value = msgs
      campaign.value = c; campaignApprovals.value = cApprovals; evidence.value = ev.filter((x): x is Evidence => !!x)
    } catch (e) {
      if (mine === seq) error.value = errorText(e)
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  watch(leadId, (id) => load(id), { immediate: true })

  const pendingBriefApproval = computed(() => briefApprovals.value.find((a) => a.status === 'PENDING') ?? null)
  const pendingCampaignApproval = computed(() => campaignApprovals.value.find((a) => a.status === 'PENDING') ?? null)
  const latestBriefDecision = computed(() => briefApprovals.value.find((a) => a.decided_at) ?? null)
  const leadMessage = computed(() => messages.value.find((m) => m.campaign === campaign.value?.id && m.sequence_step === 1) ?? null)
  const evidenceById = computed(() => new Map(evidence.value.map((e) => [e.id, e])))

  return {
    loading, error, lead, brief, briefApprovals, messages, campaign, campaignApprovals, evidence,
    pendingBriefApproval, pendingCampaignApproval, latestBriefDecision, leadMessage, evidenceById,
    reload: () => load(leadId.value, true),
  }
}
