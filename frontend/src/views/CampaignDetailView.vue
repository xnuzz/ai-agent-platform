<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Campaign, OutreachMessage, Paginated } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import LatestDecision from '@/components/LatestDecision.vue'
import Notice from '@/components/Notice.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel, fmtDate } from '@/components/format'
import { useAction } from '@/components/useAction'
import { useAuthStore } from '@/stores/auth'

type Offer = { headline: string; value_proposition: string; pricing: string; call_to_action: string }
const props = defineProps<{ id: string }>()
const auth = useAuthStore()
const campaign = ref<Campaign | null>(null)
const messages = ref<OutreachMessage[]>([])
const form = ref<{ name: string; offer: Offer }>({ name: '', offer: { headline: '', value_proposition: '', pricing: '', call_to_action: '' } })
const drafts = ref<Record<string, { subject: string; body: string }>>({})
const editing = ref<string | null>(null)
const note = ref('')
const reviewKey = ref(0)
const { busy, error, notice, run } = useAction()

const editable = computed(() => auth.canWrite() && ['DRAFT', 'CHANGES_REQUESTED'].includes(campaign.value?.status ?? ''))
const campaignDirty = computed(() => campaign.value != null &&
  (form.value.name !== campaign.value.name || JSON.stringify(form.value.offer) !== JSON.stringify({ ...emptyOffer(), ...(campaign.value.offer as object) })))
const draftCount = computed(() => messages.value.filter((m) => m.status === 'DRAFT').length)
const emptyOffer = (): Offer => ({ headline: '', value_proposition: '', pricing: '', call_to_action: '' })

function reset(c: Campaign) {
  campaign.value = c
  form.value = { name: c.name, offer: { ...emptyOffer(), ...(c.offer as object) } }
}
async function load() {
  reset(await api.get<Campaign>(`campaigns/${props.id}/`))
  messages.value = (await api.get<Paginated<OutreachMessage>>('outreach-messages/', { campaign: props.id, page_size: 100 })).results
}
onMounted(load)

const saveCampaign = () => run(async () => reset(await api.patch<Campaign>(`campaigns/${props.id}/`, form.value)), 'Saved.')
function startEdit(m: OutreachMessage) {
  drafts.value[m.id] = { subject: m.subject ?? '', body: m.body }
  editing.value = m.id
}
const saveMessage = (m: OutreachMessage) => run(async () => {
  const updated = await api.patch<OutreachMessage>(`outreach-messages/${m.id}/`, drafts.value[m.id])
  messages.value = messages.value.map((x) => (x.id === m.id ? updated : x))
  editing.value = null
}, 'Message saved.')
const submit = () => run(async () => {
  if (campaignDirty.value) reset(await api.patch<Campaign>(`campaigns/${props.id}/`, form.value))
  await api.post(`campaigns/${props.id}/submit/`, { summary: note.value })
  note.value = ''
  await load()
  reviewKey.value++
}, 'Submitted for approval.')
const action = (a: 'launch' | 'pause' | 'cancel') => run(async () => { await api.post(`campaigns/${props.id}/${a}/`); await load() })
const cancelMsg = (id: string) => run(async () => { await api.post(`outreach-messages/${id}/cancel/`); await load() })
</script>

<template>
  <template v-if="campaign">
    <PageHeader :title="campaign.name" :subtitle="`${agentLabel(campaign.source)} · ${campaign.channel}`">
      <RouterLink to="/campaigns" class="btn-secondary">Back</RouterLink>
      <template v-if="auth.canWrite()">
        <button v-if="['APPROVED', 'PAUSED'].includes(campaign.status ?? '')" class="btn-primary" :disabled="busy" @click="action('launch')">Launch</button>
        <button v-if="campaign.status === 'ACTIVE'" class="btn-secondary" :disabled="busy" @click="action('pause')">Pause</button>
        <button v-if="['DRAFT', 'APPROVED', 'ACTIVE', 'PAUSED', 'CHANGES_REQUESTED'].includes(campaign.status ?? '')" class="btn-danger" :disabled="busy" @click="action('cancel')">Cancel campaign</button>
      </template>
    </PageHeader>
    <ErrorBanner :message="error" />
    <div class="mb-4 flex flex-wrap items-center gap-4 text-sm">
      <StatusBadge :status="campaign.status" /><span>Approved {{ fmtDate(campaign.approved_at) }}</span><span>Launched {{ fmtDate(campaign.launched_at) }}</span>
      <Notice :notice="notice" />
    </div>

    <form class="card mb-4 space-y-4" @submit.prevent="saveCampaign">
      <LatestDecision :target-id="campaign.id" :refresh-key="reviewKey" />
      <fieldset :disabled="!editable" class="grid gap-4 md:grid-cols-2">
        <div class="md:col-span-2"><label class="label">Campaign name</label><input v-model="form.name" class="input" required maxlength="300" /></div>
        <div><label class="label">Offer headline</label><input v-model="form.offer.headline" class="input" /></div>
        <div><label class="label">Call to action</label><input v-model="form.offer.call_to_action" class="input" /></div>
        <div><label class="label">Value proposition</label><textarea v-model="form.offer.value_proposition" rows="3" class="input" /></div>
        <div><label class="label">Pricing</label><textarea v-model="form.offer.pricing" rows="3" class="input" /></div>
      </fieldset>
      <div v-if="editable" class="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-4">
        <button class="btn-secondary" :disabled="busy || !campaignDirty">Save campaign</button>
        <input v-model="note" class="input max-w-xs" placeholder="Note for the reviewer (optional)" />
        <button type="button" class="btn-primary" :disabled="busy || !draftCount" @click="submit">Submit {{ draftCount }} message(s) for approval</button>
      </div>
      <p v-else-if="auth.canWrite() && campaign.status === 'WAITING_FOR_APPROVAL'" class="text-xs text-slate-500">Locked while waiting for approval. You can still exclude individual messages.</p>
    </form>

    <div class="space-y-3">
      <article v-for="m in messages" :key="m.id" class="card">
        <div class="flex items-start justify-between gap-2">
          <div><div class="text-xs text-slate-500">To {{ m.business_name }} &lt;{{ m.to_email }}&gt;</div>
            <div v-if="editing !== m.id" class="font-medium">{{ m.subject }}</div></div>
          <div class="flex items-center gap-2"><StatusBadge :status="m.status" />
            <button v-if="editable && m.status === 'DRAFT' && editing !== m.id" class="btn-secondary" @click="startEdit(m)">Edit</button>
            <button v-if="auth.canWrite() && ['DRAFT', 'WAITING_FOR_APPROVAL', 'APPROVED'].includes(m.status ?? '')" class="btn-secondary" :disabled="busy" @click="cancelMsg(m.id)">Exclude</button>
          </div>
        </div>
        <form v-if="editing === m.id" class="mt-3 space-y-3" @submit.prevent="saveMessage(m)">
          <div><label class="label">Subject</label><input v-model="drafts[m.id]!.subject" class="input" maxlength="300" required /></div>
          <div><label class="label">Body (plain text — sender identity and opt-out footer are added automatically)</label>
            <textarea v-model="drafts[m.id]!.body" rows="10" class="input font-mono text-xs" required /></div>
          <div class="flex gap-2"><button class="btn-primary" :disabled="busy">Save message</button><button type="button" class="btn-secondary" @click="editing = null">Discard</button></div>
        </form>
        <pre v-else class="mt-2 font-sans text-sm whitespace-pre-wrap text-slate-700">{{ m.body }}</pre>
        <div v-if="m.error && Object.keys(m.error).length" class="mt-2 text-xs text-rose-700">{{ (m.error as any).code }} {{ ((m.error as any).reasons ?? []).join(', ') }}</div>
      </article>
    </div>
  </template>
</template>
