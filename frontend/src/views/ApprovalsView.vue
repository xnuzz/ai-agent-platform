<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, errorText } from '@/api/client'
import type { Approval, ApprovalDecision, Paginated } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel, fmtDate } from '@/components/format'
import { useAuthStore } from '@/stores/auth'

type Snap = { content: Record<string, any>; context?: Record<string, any>; messages?: Record<string, any>[] }
const auth = useAuthStore()
const status = ref('PENDING')
const items = ref<Approval[]>([])
const selected = ref<Approval | null>(null)
const comment = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
const snap = computed(() => (selected.value?.snapshot ?? { content: {} }) as Snap)
const typeLabel: Record<string, string> = { SOFTWARE_IDEA: 'Software idea', PROJECT_BRIEF: 'Project brief', CAMPAIGN: 'Outreach campaign' }

async function load() {
  items.value = (await api.get<Paginated<Approval>>('approvals/', { status: status.value || undefined })).results
  selected.value = items.value.find((a) => a.id === selected.value?.id) ?? items.value[0] ?? null
}
watch(status, load, { immediate: true })

async function decide(decision: ApprovalDecision) {
  if (!selected.value) return
  busy.value = true
  error.value = null
  try {
    await api.post(`approvals/${selected.value.id}/decide/`, { decision, comment: comment.value })
    comment.value = ''
    await load()
  } catch (e) { error.value = errorText(e) } finally { busy.value = false }
}
const title = (a: Approval) => {
  const c = (a.snapshot as Snap).content
  return c.name ?? c.title ?? 'Untitled'
}
</script>

<template>
  <PageHeader title="Approval center" subtitle="Agents can only request. Approval here is the only way anything proceeds or gets sent.">
    <select v-model="status" class="input w-44">
      <option value="PENDING">Pending</option><option value="APPROVED">Approved</option>
      <option value="REJECTED">Rejected</option><option value="CHANGES_REQUESTED">Changes requested</option><option value="">All</option>
    </select>
  </PageHeader>
  <ErrorBanner :message="error" />
  <div class="grid gap-4 lg:grid-cols-5">
    <div class="space-y-2 lg:col-span-2">
      <button v-for="a in items" :key="a.id" class="card block w-full p-4 text-left"
        :class="selected?.id === a.id ? 'border-indigo-400 ring-2 ring-indigo-100' : ''" @click="selected = a">
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs font-medium text-slate-500 uppercase">{{ typeLabel[a.target_type] }}</span><StatusBadge :status="a.status" />
        </div>
        <div class="mt-1 font-medium">{{ title(a) }}</div>
        <div class="mt-1 text-xs text-slate-500">{{ a.requested_by_agent ? agentLabel(a.requested_by_agent) : 'Manual' }} · {{ fmtDate(a.created_at) }}</div>
      </button>
      <p v-if="!items.length" class="card text-sm text-slate-500">Nothing here.</p>
    </div>
    <section v-if="selected" class="card space-y-4 lg:col-span-3">
      <div>
        <div class="text-xs font-medium text-slate-500 uppercase">{{ typeLabel[selected.target_type] }}</div>
        <h2 class="text-xl font-semibold">{{ title(selected) }}</h2>
        <p v-if="selected.summary" class="mt-2 rounded-lg bg-indigo-50 p-3 text-sm text-indigo-900">{{ selected.summary }}</p>
      </div>

      <template v-if="selected.target_type === 'SOFTWARE_IDEA'">
        <p class="text-sm">{{ snap.content.summary }}</p>
        <dl class="grid gap-3 text-sm md:grid-cols-2">
          <div v-for="k in ['problem', 'solution', 'target_customers', 'pricing_model', 'differentiation', 'mvp_scope']" :key="k" v-show="snap.content[k]">
            <dt class="label">{{ k.replace('_', ' ') }}</dt><dd>{{ snap.content[k] }}</dd>
          </div>
        </dl>
        <div v-if="snap.content.key_features?.length"><div class="label">Key features</div><ul class="list-disc pl-5 text-sm"><li v-for="f in snap.content.key_features" :key="f">{{ f }}</li></ul></div>
        <div v-if="snap.content.risks?.length"><div class="label">Risks</div><ul class="list-disc pl-5 text-sm"><li v-for="r in snap.content.risks" :key="r">{{ r }}</li></ul></div>
        <p class="text-xs text-slate-500">Approving automatically queues Agent 1 customer research for this idea.</p>
      </template>

      <template v-else-if="selected.target_type === 'PROJECT_BRIEF'">
        <div class="text-sm text-slate-600">{{ snap.context?.business_name }} · {{ snap.context?.city }} · <a :href="snap.context?.website" target="_blank" rel="noopener" class="text-indigo-600">{{ snap.context?.website }}</a> · lead score {{ snap.context?.lead_score }}</div>
        <p class="text-sm">{{ snap.content.summary }}</p>
        <div v-if="snap.content.problems?.length"><div class="label">Detected problems</div>
          <ul class="space-y-1 text-sm"><li v-for="p in snap.content.problems" :key="p.code"><StatusBadge :status="p.severity" /> {{ p.title }}</li></ul>
        </div>
        <div v-if="snap.content.scope_items?.length"><div class="label">Scope</div><ul class="list-disc pl-5 text-sm"><li v-for="s in snap.content.scope_items" :key="s">{{ s }}</li></ul></div>
        <div class="text-sm">Effort {{ snap.content.estimated_effort_hours?.join('–') }} h · Budget {{ snap.content.estimated_budget?.join('–') }} {{ snap.content.currency }}</div>
      </template>

      <template v-else>
        <div class="text-sm text-slate-600">{{ snap.context?.message_count }} message(s). Sender identity + unsubscribe footer are appended automatically.</div>
        <div v-for="m in snap.messages" :key="m.id" class="rounded-lg border border-slate-200 p-3 text-sm">
          <div class="text-xs text-slate-500">To {{ m.business_name }} &lt;{{ m.to_email }}&gt;</div>
          <div class="font-medium">{{ m.subject }}</div>
          <pre class="mt-1 font-sans whitespace-pre-wrap text-slate-700">{{ m.body }}</pre>
        </div>
      </template>

      <div v-if="snap.context?.evidence?.length">
        <div class="label">Evidence</div>
        <ul class="space-y-1 text-sm"><li v-for="e in snap.context.evidence" :key="e.id"><a :href="e.url" target="_blank" rel="noopener noreferrer" class="text-indigo-600">{{ e.title || e.url }}</a> <span class="text-xs text-slate-400">{{ e.source_type }}</span></li></ul>
      </div>

      <div v-if="selected.status === 'PENDING' && auth.canWrite()" class="space-y-2 border-t border-slate-200 pt-4">
        <textarea v-model="comment" class="input" rows="2" placeholder="Comment (optional)" />
        <div class="flex gap-2">
          <button class="btn-primary" :disabled="busy" @click="decide('APPROVED')">Approve</button>
          <button class="btn-secondary" :disabled="busy" @click="decide('CHANGES_REQUESTED')">Request changes</button>
          <button class="btn-danger" :disabled="busy" @click="decide('REJECTED')">Reject</button>
        </div>
      </div>
      <div v-else-if="selected.decided_at" class="border-t border-slate-200 pt-4 text-sm text-slate-500">
        Decided by {{ selected.decided_by_email }} · {{ fmtDate(selected.decided_at) }} <span v-if="selected.decision_comment">— “{{ selected.decision_comment }}”</span>
      </div>
    </section>
  </div>
</template>
