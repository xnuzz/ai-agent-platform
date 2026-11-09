<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Campaign, Lead, OutreachMessage, Paginated, ProjectBrief } from '@/api/types'
import BriefEditor from '@/components/BriefEditor.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import Notice from '@/components/Notice.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel } from '@/components/format'
import { useAction } from '@/components/useAction'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ id: string }>()
const auth = useAuthStore()
const lead = ref<Lead | null>(null)
const briefs = ref<ProjectBrief[]>([])
const campaigns = ref<Campaign[]>([])
const form = ref<Record<string, any>>({})
const { busy, error, notice, run } = useAction()
const FIELDS = ['qualification_notes', 'contact_name', 'contact_role', 'contact_email', 'contact_phone', 'contact_email_type', 'legal_basis', 'legal_basis_note'] as const
const NEXT: Record<string, string[]> = {
  NEW: ['QUALIFIED', 'DISQUALIFIED', 'ARCHIVED'], QUALIFIED: ['DISQUALIFIED', 'ARCHIVED'], DISQUALIFIED: ['QUALIFIED', 'ARCHIVED'],
  CONTACTED: ['REPLIED', 'WON', 'LOST', 'ARCHIVED'], REPLIED: ['WON', 'LOST', 'ARCHIVED'], WON: ['ARCHIVED'], LOST: ['ARCHIVED'], ARCHIVED: [],
}
const dirty = computed(() => lead.value != null && FIELDS.some((f) => form.value[f] !== (lead.value as any)[f]))

function reset(l: Lead) {
  lead.value = l
  form.value = Object.fromEntries(FIELDS.map((f) => [f, (l as any)[f]]))
}
onMounted(async () => {
  reset(await api.get<Lead>(`leads/${props.id}/`))
  briefs.value = (await api.get<Paginated<ProjectBrief>>('project-briefs/', { lead: props.id })).results
  const msgs = (await api.get<Paginated<OutreachMessage>>('outreach-messages/', { lead: props.id, page_size: 100 })).results
  campaigns.value = await Promise.all([...new Set(msgs.map((m) => m.campaign))].map((id) => api.get<Campaign>(`campaigns/${id}/`)))
})
const save = () => run(async () => reset(await api.patch<Lead>(`leads/${props.id}/`, form.value)), 'Saved.')
const setStatus = (status: string) => run(async () => reset(await api.post<Lead>(`leads/${props.id}/set-status/`, { status })))
function briefChanged(b: ProjectBrief) { briefs.value = briefs.value.map((x) => (x.id === b.id ? b : x)) }
</script>

<template>
  <template v-if="lead">
    <PageHeader :title="lead.business.name" :subtitle="`${agentLabel(lead.source)} · ${lead.business.city} ${lead.business.country_code}`">
      <RouterLink to="/leads" class="btn-secondary">Back</RouterLink>
    </PageHeader>
    <ErrorBanner :message="error" />
    <div class="mb-4 flex flex-wrap items-center gap-2 text-sm">
      <StatusBadge :status="lead.status" /><span class="text-silver">Score {{ lead.score ?? '—' }}</span>
      <span v-if="lead.is_suppressed" class="rounded bg-bad/10 px-2 py-0.5 text-xs text-bad">On suppression list</span>
      <template v-if="auth.canWrite()">
        <span class="ml-2 text-xs text-silver">Move to:</span>
        <button v-for="s in NEXT[lead.status ?? ''] ?? []" :key="s" class="btn-secondary" :disabled="busy" @click="setStatus(s)">{{ s.replace('_', ' ') }}</button>
      </template>
    </div>
    <div class="grid gap-4 lg:grid-cols-3">
      <div class="space-y-4 lg:col-span-2">
        <BriefEditor v-for="b in briefs" :key="b.id" :brief="b" :can-write="auth.canWrite()" @changed="briefChanged" />
        <form class="card space-y-4" @submit.prevent="save">
          <h3 class="font-semibold">Contact &amp; legal basis</h3>
          <fieldset :disabled="!auth.canWrite()" class="grid gap-4 md:grid-cols-2">
            <div><label class="label">Contact name</label><input v-model="form.contact_name" class="input" /></div>
            <div><label class="label">Role</label><input v-model="form.contact_role" class="input" /></div>
            <div><label class="label">Email</label><input v-model="form.contact_email" type="email" class="input" /></div>
            <div><label class="label">Phone</label><input v-model="form.contact_phone" class="input" /></div>
            <div><label class="label">Email type</label>
              <select v-model="form.contact_email_type" class="input"><option>GENERIC_BUSINESS</option><option>PERSONAL_WORK</option><option>UNKNOWN</option></select></div>
            <div><label class="label">Legal basis</label>
              <select v-model="form.legal_basis" class="input"><option>LEGITIMATE_INTEREST</option><option>CONSENT</option><option>UNKNOWN</option></select></div>
            <div class="md:col-span-2"><label class="label">Legal basis note (LIA summary / consent record)</label><textarea v-model="form.legal_basis_note" rows="2" class="input" /></div>
            <div class="md:col-span-2"><label class="label">Qualification notes</label><textarea v-model="form.qualification_notes" rows="3" class="input" /></div>
          </fieldset>
          <p v-if="form.legal_basis === 'UNKNOWN'" class="text-xs text-warn">Messages to this lead will be blocked at send time until a legal basis is recorded.</p>
          <p class="text-xs text-silver">Changing the email here does not alter already-drafted messages (they keep the address that was reviewed).</p>
          <div v-if="auth.canWrite()" class="flex items-center gap-3"><button class="btn-primary" :disabled="busy || !dirty">Save</button><Notice :notice="notice" /></div>
        </form>
      </div>
      <aside class="space-y-4">
        <section class="card text-sm">
          <h3 class="mb-2 font-medium">Business</h3>
          <a v-if="lead.business.website" :href="lead.business.website" target="_blank" rel="noopener noreferrer" class="text-ink">{{ lead.business.website }}</a>
          <div class="text-silver">{{ lead.business.address_line1 }}</div>
          <div class="text-silver">{{ lead.business.email }} {{ lead.business.phone }}</div>
          <div class="text-xs text-silver">{{ lead.business.category }}</div>
        </section>
        <section class="card text-sm">
          <h3 class="mb-2 font-medium">Problems</h3>
          <ul class="space-y-1"><li v-for="p in (lead.problems as any[])" :key="p.code"><StatusBadge :status="p.severity" /> {{ p.title }}</li></ul>
          <p v-if="!(lead.problems as any[]).length" class="text-silver">None recorded.</p>
        </section>
        <section class="card text-sm">
          <h3 class="mb-2 font-medium">Campaigns</h3>
          <RouterLink v-for="c in campaigns" :key="c.id" :to="`/campaigns/${c.id}`" class="flex justify-between py-1 text-ink">{{ c.name }} <StatusBadge :status="c.status" /></RouterLink>
          <p v-if="!campaigns.length" class="text-silver">None.</p>
        </section>
      </aside>
    </div>
  </template>
</template>
