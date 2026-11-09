<script setup lang="ts">
/**
 * Business detail workspace (drawer). Every action calls an existing endpoint:
 *  Approve / Reject lead → decide the project brief's PENDING approval (launch requires the brief, ADR-006);
 *    a lead without a pending brief can only be archived (Reject) — Approve explains why it is unavailable.
 *  Request more research → CHANGES_REQUESTED on the brief approval with your comment.
 *  Edit project → BriefEditor (PATCH + resubmit, DRAFT/CHANGES_REQUESTED only).
 *  Edit / Approve outreach → OutreachTab (PATCH message + offer, decide campaign approval).
 */
import { computed, nextTick, ref, toRef, watch } from 'vue'
import { localFinderApi as api } from '@/api/localFinder'
import type { ProjectBrief } from '@/api/types'
import BriefEditor from '@/components/BriefEditor.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { fmtDate } from '@/components/format'
import { useAction } from '@/components/useAction'
import { complexityOf, countryName, locationLabel, POTENTIAL_LABEL, problemsOf, REVIEW_LABEL, toRow } from '@/features/localFinder/model'
import { useLeadWorkspace } from '@/features/localFinder/workspace'
import { useAuthStore } from '@/stores/auth'
import { useLocalFinderStore } from '@/stores/localFinder'
import LeadScore from './LeadScore.vue'
import OutreachTab from './detail/OutreachTab.vue'
import WebsiteAnalysis from './detail/WebsiteAnalysis.vue'

const store = useLocalFinderStore()
const auth = useAuthStore()
const ws = useLeadWorkspace(toRef(store, 'detailId'))
const { busy, error, notice, run } = useAction()
const panel = ref<HTMLElement>()
const tab = ref<Tab>('business')
const comment = ref('')
const editingBrief = ref(false)
const armedArchive = ref(false)

type Tab = 'business' | 'website' | 'opportunity' | 'project' | 'outreach'
const TABS: { id: Tab; label: string }[] = [
  { id: 'business', label: 'Business' }, { id: 'website', label: 'Website analysis' }, { id: 'opportunity', label: 'Opportunity' },
  { id: 'project', label: 'Project' }, { id: 'outreach', label: 'Outreach' },
]

const row = computed(() => (ws.lead.value ? toRow(ws.lead.value, ws.brief.value) : store.detailRow))
const lead = computed(() => row.value?.lead ?? null)
const b = computed(() => lead.value?.business ?? null)
const brief = computed(() => ws.brief.value)
const canAct = computed(() => auth.canWrite() && !store.demo)
const pendingBrief = computed(() => ws.pendingBriefApproval.value)
const archivable = computed(() => ['NEW', 'QUALIFIED', 'DISQUALIFIED'].includes(lead.value?.status ?? ''))
const approveHint = computed(() => {
  if (store.demo) return 'Demo data — actions are disabled.'
  if (!auth.canWrite()) return 'Your role is read-only.'
  if (pendingBrief.value) return 'Approves the project brief so its outreach can be launched.'
  if (!brief.value) return lead.value?.status === 'DISQUALIFIED' ? 'Agent 2 disqualified this lead (score below the threshold), so there is no project brief to approve.' : 'No project brief exists for this lead.'
  if (['DRAFT', 'CHANGES_REQUESTED'].includes(brief.value.status)) return `The brief is ${brief.value.status.replace(/_/g, ' ')} — edit it in the Project tab and submit it for approval.`
  return `The brief was already decided (${brief.value.status.replace(/_/g, ' ')}).`
})
const evidenceUrls = computed(() => [...new Map(ws.evidence.value.filter((e) => e.url).map((e) => [e.url, e])).values()])
const effort = computed(() => brief.value ? [brief.value.estimated_effort_hours_min, brief.value.estimated_effort_hours_max] : [null, null])
const weeks = computed(() => effort.value[1] ? `≈ ${Math.max(1, Math.ceil((effort.value[0] ?? effort.value[1]) / 30))}–${Math.max(1, Math.ceil(effort.value[1] / 30))} weeks at 30 h/week` : '')

watch(() => store.detailId, async (id) => {
  tab.value = 'business'; comment.value = ''; editingBrief.value = false; armedArchive.value = false
  if (id) { await nextTick(); panel.value?.focus() }
})

async function refreshAll() {
  await ws.reload()
  if (ws.lead.value) store.upsert(ws.lead.value, ws.brief.value)
  store.syncNow()
}
const decideBrief = (decision: 'APPROVED' | 'REJECTED' | 'CHANGES_REQUESTED', msg: string) => run(async () => {
  if (!pendingBrief.value) return
  await api.decide(pendingBrief.value.id, decision, comment.value)
  comment.value = ''
  await refreshAll()
}, msg)
const approveLead = () => decideBrief('APPROVED', 'Lead approved — project brief APPROVED.')
const requestMore = () => {
  if (!comment.value.trim()) { error.value = 'Describe what more research is needed in the comment.'; return }
  return decideBrief('CHANGES_REQUESTED', 'More research requested — brief returned with your comment.')
}
function rejectLead() {
  if (pendingBrief.value) return decideBrief('REJECTED', 'Lead rejected — project brief REJECTED.')
  if (!armedArchive.value) { armedArchive.value = true; return }
  armedArchive.value = false
  return run(async () => { if (lead.value) { await api.setLeadStatus(lead.value.id, 'ARCHIVED'); await refreshAll() } }, 'Lead archived.')
}
const rejectEnabled = computed(() => canAct.value && (!!pendingBrief.value || archivable.value))
function briefChanged(nb: ProjectBrief) { ws.brief.value = nb; void refreshAll() }

function onTabKey(e: KeyboardEvent) {
  const i = TABS.findIndex((t) => t.id === tab.value)
  const next = e.key === 'ArrowRight' ? (i + 1) % TABS.length : e.key === 'ArrowLeft' ? (i - 1 + TABS.length) % TABS.length : -1
  if (next < 0) return
  e.preventDefault()
  tab.value = TABS[next]!.id
  void nextTick(() => panel.value?.querySelector<HTMLElement>(`#tab-${tab.value}`)?.focus())
}
</script>

<template>
  <Transition name="lbf-sheet">
    <div v-if="store.detailId" class="fixed inset-0 z-50 flex justify-end">
      <div class="absolute inset-0 bg-slate-950/30 backdrop-blur-[1px]" aria-hidden="true" @click="store.closeDetail()" />
      <section ref="panel" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="detail-h"
        class="relative flex h-full w-full flex-col bg-white shadow-2xl outline-none sm:w-[680px] sm:max-w-[92vw] sm:rounded-l-2xl" data-testid="detail-panel">
        <header class="border-b border-slate-100 px-5 pt-5 pb-3">
          <div class="flex items-start gap-4">
            <LeadScore :score="lead?.score" :size="52" />
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <h2 id="detail-h" class="truncate text-lg font-semibold text-slate-900">{{ b?.name ?? 'Loading…' }}</h2>
                <span v-if="row" class="rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-medium text-violet-700">{{ REVIEW_LABEL[row.review] }}</span>
              </div>
              <p v-if="lead" class="truncate text-xs text-slate-500">{{ b?.category || 'Uncategorised' }} · {{ locationLabel(lead) }} · {{ POTENTIAL_LABEL[row!.potential] }}</p>
              <p v-if="lead" class="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">Lead <StatusBadge :status="lead.status" />
                <template v-if="brief">· Brief <StatusBadge :status="brief.status" /></template>
                <template v-if="ws.campaign.value">· Outreach <StatusBadge :status="ws.campaign.value.status" /></template>
              </p>
            </div>
            <button type="button" class="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Close details" @click="store.closeDetail()">
              <svg viewBox="0 0 20 20" class="h-5 w-5" fill="currentColor" aria-hidden="true"><path d="M5.3 5.3a1 1 0 0 1 1.4 0L10 8.6l3.3-3.3a1 1 0 1 1 1.4 1.4L11.4 10l3.3 3.3a1 1 0 0 1-1.4 1.4L10 11.4l-3.3 3.3a1 1 0 0 1-1.4-1.4L8.6 10 5.3 6.7a1 1 0 0 1 0-1.4Z" /></svg>
            </button>
          </div>
          <div class="-mb-3 mt-4 flex gap-1 overflow-x-auto" role="tablist" aria-label="Business details" @keydown="onTabKey">
            <button v-for="t in TABS" :id="`tab-${t.id}`" :key="t.id" type="button" role="tab" :aria-selected="tab === t.id" :aria-controls="`panel-${t.id}`"
              :tabindex="tab === t.id ? 0 : -1" class="shrink-0 border-b-2 px-3 py-2 text-xs font-medium transition"
              :class="tab === t.id ? 'border-violet-600 text-violet-700' : 'border-transparent text-slate-500 hover:text-slate-800'" @click="tab = t.id">{{ t.label }}</button>
          </div>
        </header>

        <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4" :id="`panel-${tab}`" role="tabpanel" :aria-labelledby="`tab-${tab}`">
          <p v-if="ws.error.value" class="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-800" role="alert">{{ ws.error.value }} <button type="button" class="underline" @click="ws.reload()">Retry</button></p>
          <div v-if="ws.loading.value" class="space-y-3"><div v-for="i in 4" :key="i" class="h-16 animate-pulse rounded-xl bg-slate-100" /></div>

          <template v-else-if="lead && b">
            <!-- BUSINESS -->
            <div v-if="tab === 'business'" class="space-y-4">
              <dl class="grid gap-3 sm:grid-cols-2">
                <div class="rounded-xl border border-slate-200 p-3"><dt class="label">Category</dt><dd class="text-sm text-slate-800">{{ b.category || '—' }}</dd></div>
                <div class="rounded-xl border border-slate-200 p-3"><dt class="label">Website</dt><dd class="truncate text-sm">
                  <a v-if="b.website" :href="b.website" target="_blank" rel="noopener noreferrer" class="text-violet-700 hover:underline">{{ b.website }}</a><span v-else class="text-slate-400">None listed</span></dd></div>
                <div class="rounded-xl border border-slate-200 p-3 sm:col-span-2"><dt class="label">Address</dt>
                  <dd class="text-sm text-slate-800">{{ [b.address_line1, b.postal_code, b.city, b.region, b.country_code && countryName(b.country_code)].filter(Boolean).join(', ') || '—' }}</dd></div>
                <div class="rounded-xl border border-slate-200 p-3"><dt class="label">Public e-mail</dt><dd class="truncate text-sm text-slate-800">{{ b.email || lead.contact_email || '—' }}</dd></div>
                <div class="rounded-xl border border-slate-200 p-3"><dt class="label">Phone</dt><dd class="text-sm text-slate-800">{{ b.phone || lead.contact_phone || '—' }}</dd></div>
                <div class="rounded-xl border border-slate-200 p-3 sm:col-span-2"><dt class="label">Location</dt>
                  <dd class="text-sm text-slate-800">
                    <template v-if="row?.coords">{{ row.coords[1].toFixed(5) }}, {{ row.coords[0].toFixed(5) }} <span class="text-xs text-slate-400">(supplied by the discovery provider)</span></template>
                    <span v-else class="text-amber-700">No coordinates supplied — not shown on the map.</span>
                  </dd></div>
              </dl>
              <p v-if="b.description" class="text-sm text-slate-600">{{ b.description }}</p>
              <p v-if="lead.is_suppressed" class="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-800">This contact is on the suppression list — it will never be e-mailed.</p>
              <p class="text-[11px] text-slate-400">First seen {{ fmtDate(lead.created_at) }} · updated {{ fmtDate(lead.updated_at) }} ·
                <RouterLink :to="`/leads/${lead.id}`" class="text-violet-700 hover:underline">full lead record (contact, legal basis, status)</RouterLink></p>
            </div>

            <!-- WEBSITE -->
            <WebsiteAnalysis v-else-if="tab === 'website'" :website="b.website" :evidence="ws.evidence.value" />

            <!-- OPPORTUNITY -->
            <div v-else-if="tab === 'opportunity'" class="space-y-4">
              <section>
                <h3 class="mb-2 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">Identified problems</h3>
                <ul class="space-y-2">
                  <li v-for="p in problemsOf(lead)" :key="p.code" class="rounded-xl border border-slate-200 p-3">
                    <div class="flex items-center gap-2"><StatusBadge :status="p.severity" /><span class="text-sm font-medium text-slate-800">{{ p.title || p.code }}</span><span class="ml-auto font-mono text-[10px] text-slate-400">{{ p.code }}</span></div>
                    <p v-if="p.description" class="mt-1 text-xs text-slate-600">{{ p.description }}</p>
                    <div v-if="p.evidence_ids?.length" class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
                      <template v-for="id in p.evidence_ids" :key="id">
                        <a v-if="ws.evidenceById.value.get(id)?.url" :href="ws.evidenceById.value.get(id)!.url" target="_blank" rel="noopener noreferrer" class="text-violet-700 hover:underline">
                          Evidence: {{ ws.evidenceById.value.get(id)!.title || ws.evidenceById.value.get(id)!.url }}</a>
                      </template>
                    </div>
                  </li>
                  <li v-if="!problemsOf(lead).length" class="text-sm text-slate-500">No problems recorded.</li>
                </ul>
              </section>
              <section v-if="brief?.proposed_solution"><h3 class="mb-1 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">Recommended solution</h3><p class="text-sm whitespace-pre-line text-slate-700">{{ brief.proposed_solution }}</p></section>
              <section v-if="brief?.summary || lead.qualification_notes"><h3 class="mb-1 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">Why the business may benefit</h3>
                <p v-if="brief?.summary" class="text-sm whitespace-pre-line text-slate-700">{{ brief.summary }}</p>
                <p v-if="lead.qualification_notes" class="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-xs whitespace-pre-line text-slate-600"><span class="font-medium">Scoring:</span> {{ lead.qualification_notes }}</p></section>
              <section><h3 class="mb-1 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">Source URLs</h3>
                <ul class="space-y-1 text-xs"><li v-for="e in evidenceUrls" :key="e.id" class="flex gap-2"><span class="w-24 shrink-0 text-slate-400">{{ e.source_type.replace(/_/g, ' ').toLowerCase() }}</span>
                  <a :href="e.url" target="_blank" rel="noopener noreferrer" class="truncate text-violet-700 hover:underline">{{ e.url }}</a></li>
                  <li v-if="!evidenceUrls.length" class="text-slate-400">No source URLs recorded.</li></ul></section>
            </div>

            <!-- PROJECT -->
            <div v-else-if="tab === 'project'" class="space-y-4">
              <p v-if="!brief" class="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">No project brief — Agent 2 writes one only for qualified leads.</p>
              <template v-else-if="editingBrief">
                <BriefEditor :brief="brief" :can-write="canAct" @changed="briefChanged" />
                <button type="button" class="btn-secondary" @click="editingBrief = false">Close editor</button>
              </template>
              <template v-else>
                <section><h3 class="text-base font-semibold text-slate-900">{{ brief.title }}</h3><p class="mt-1 text-sm whitespace-pre-line text-slate-600">{{ brief.summary }}</p></section>
                <div class="grid gap-3 sm:grid-cols-3">
                  <div class="rounded-xl border border-slate-200 p-3"><div class="label">Estimated time</div><div class="text-sm font-medium text-slate-800">{{ effort[0] ?? '?' }}–{{ effort[1] ?? '?' }} h</div><div class="text-[10px] text-slate-400">{{ weeks }}</div></div>
                  <div class="rounded-xl border border-slate-200 p-3"><div class="label">Complexity</div><div class="text-sm font-medium text-slate-800">{{ complexityOf(effort[1]) ?? '—' }}</div><div class="text-[10px] text-slate-400">derived from effort</div></div>
                  <div class="rounded-xl border border-slate-200 p-3"><div class="label">Value hypothesis</div>
                    <div class="text-sm font-medium text-slate-800">{{ brief.estimated_budget_min ?? '?' }}–{{ brief.estimated_budget_max ?? '?' }} {{ brief.currency }}</div><div class="text-[10px] text-slate-400">agent estimate, unvalidated</div></div>
                </div>
                <section><h3 class="mb-1 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">Required features</h3>
                  <ul class="list-disc space-y-0.5 pl-5 text-sm text-slate-700"><li v-for="s in (brief.scope_items as string[])" :key="s">{{ s }}</li></ul></section>
                <section v-if="(brief.tech_stack as string[]).length"><h3 class="mb-1 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">Suggested technology</h3>
                  <div class="flex flex-wrap gap-1.5"><span v-for="t in (brief.tech_stack as string[])" :key="t" class="rounded-full bg-violet-50 px-2.5 py-0.5 text-xs text-violet-700">{{ t }}</span></div></section>
                <p v-if="ws.latestBriefDecision.value?.decision_comment" class="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-900">
                  Latest review ({{ ws.latestBriefDecision.value.status.replace(/_/g, ' ') }}): “{{ ws.latestBriefDecision.value.decision_comment }}”</p>
                <div class="border-t border-slate-100 pt-3">
                  <button type="button" class="btn-secondary" :disabled="!canAct || !['DRAFT', 'CHANGES_REQUESTED'].includes(brief.status)" @click="editingBrief = true">Edit project</button>
                  <p v-if="!['DRAFT', 'CHANGES_REQUESTED'].includes(brief.status)" class="mt-1 text-[11px] text-slate-400">Editable only while DRAFT or CHANGES REQUESTED (now {{ brief.status.replace(/_/g, ' ') }}). Use “Request more research” to send it back.</p>
                </div>
              </template>
            </div>

            <!-- OUTREACH -->
            <OutreachTab v-else-if="tab === 'outreach'" :lead="lead" :campaign="ws.campaign.value" :message="ws.leadMessage.value"
              :pending="ws.pendingCampaignApproval.value" :can-write="canAct" :comment="comment" @changed="refreshAll" />
          </template>
        </div>

        <footer class="space-y-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3 sm:rounded-bl-2xl">
          <textarea v-model="comment" rows="1" class="input resize-none text-xs" placeholder="Comment for the decision (required for “Request more research”)" aria-label="Decision comment" :disabled="!canAct" />
          <div class="flex flex-wrap items-center gap-2">
            <button type="button" class="btn-accent" :disabled="busy || !canAct || !pendingBrief" :title="approveHint" data-testid="approve-lead" @click="approveLead">Approve lead</button>
            <button type="button" :class="armedArchive ? 'btn-danger' : 'btn-secondary'" :disabled="busy || !rejectEnabled" data-testid="reject-lead" @click="rejectLead">
              {{ pendingBrief ? 'Reject lead' : armedArchive ? 'Confirm: archive lead' : 'Reject lead' }}</button>
            <button type="button" class="btn-secondary" :disabled="busy || !canAct || !pendingBrief" data-testid="request-more" @click="requestMore">Request more research</button>
            <span v-if="notice" class="text-xs text-emerald-700" role="status">{{ notice }}</span>
          </div>
          <p v-if="error" class="text-xs text-rose-700" role="alert">{{ error }}</p>
          <p class="text-[11px] text-slate-500">{{ pendingBrief ? 'Decisions apply to the project brief approval. Request more research returns it with your comment (Agent 2 does not re-run automatically yet).' : approveHint }}
            <template v-if="!pendingBrief && archivable && canAct"> Reject archives the lead (final).</template></p>
        </footer>
      </section>
    </div>
  </Transition>
</template>

<style scoped>
.lbf-sheet-enter-active, .lbf-sheet-leave-active { transition: opacity .2s ease; }
.lbf-sheet-enter-active section, .lbf-sheet-leave-active section { transition: transform .25s ease; }
.lbf-sheet-enter-from, .lbf-sheet-leave-to { opacity: 0; }
.lbf-sheet-enter-from section, .lbf-sheet-leave-to section { transform: translateX(32px); }
@media (prefers-reduced-motion: reduce) { .lbf-sheet-enter-active, .lbf-sheet-leave-active, .lbf-sheet-enter-active section, .lbf-sheet-leave-active section { transition: none; } }
</style>
