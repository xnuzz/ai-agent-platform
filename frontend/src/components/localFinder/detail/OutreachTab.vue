<script setup lang="ts">
import { computed, ref } from 'vue'
import { localFinderApi as api } from '@/api/localFinder'
import type { Approval, Campaign, Lead, OutreachMessage } from '@/api/types'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAction } from '@/components/useAction'

type Offer = { headline: string; value_proposition: string; pricing: string; call_to_action: string }
const props = defineProps<{ lead: Lead; campaign: Campaign | null; message: OutreachMessage | null; pending: Approval | null; canWrite: boolean; comment: string }>()
const emit = defineEmits<{ changed: [] }>()
const { busy, error, notice, run } = useAction()
const editing = ref(false)
const form = ref<{ subject: string; body: string; offer: Offer }>({ subject: '', body: '', offer: emptyOffer() })

function emptyOffer(): Offer { return { headline: '', value_proposition: '', pricing: '', call_to_action: '' } }
const offer = computed<Offer>(() => ({ ...emptyOffer(), ...((props.campaign?.offer ?? {}) as Partial<Offer>) }))
const editable = computed(() => ['DRAFT', 'CHANGES_REQUESTED'].includes(props.campaign?.status ?? '') && props.message?.status === 'DRAFT')
const submittable = computed(() => ['DRAFT', 'CHANGES_REQUESTED'].includes(props.campaign?.status ?? ''))
const recipient = computed(() => props.message?.to_email || props.lead.contact_email || props.lead.business.email || '')
const others = computed(() => Math.max(0, (Object.values((props.campaign?.message_counts ?? {}) as Record<string, number>).reduce((a, b) => a + b, 0)) - 1))
const editHint = computed(() => {
  if (!props.campaign) return 'No outreach campaign was drafted for this lead.'
  if (!props.canWrite) return 'Your role is read-only.'
  if (!editable.value) return `Locked while the campaign is ${props.campaign.status.replace(/_/g, ' ')}. Request changes on its approval to edit.`
  return ''
})

function startEdit() {
  form.value = { subject: props.message?.subject ?? '', body: props.message?.body ?? '', offer: { ...offer.value } }
  editing.value = true
}
const save = () => run(async () => {
  if (!props.campaign || !props.message) return
  await api.patchMessage(props.message.id, { subject: form.value.subject, body: form.value.body })
  await api.patchCampaign(props.campaign.id, { offer: form.value.offer })
  editing.value = false
  emit('changed')
}, 'Outreach saved.')
const submit = () => run(async () => { if (props.campaign) { await api.submitCampaign(props.campaign.id, props.comment); emit('changed') } }, 'Submitted for approval.')
const approve = () => run(async () => { if (props.pending) { await api.decide(props.pending.id, 'APPROVED', props.comment); emit('changed') } }, 'Outreach approved.')
</script>

<template>
  <div class="space-y-4">
    <p v-if="!campaign" class="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">
      No outreach was drafted for this lead<template v-if="lead.is_suppressed"> — the contact is on the suppression list</template><template v-else-if="!recipient"> — no usable business e-mail was found</template>.
    </p>
    <template v-else>
      <div class="grid gap-3 sm:grid-cols-3">
        <div class="rounded-xl border border-slate-200 p-3 text-xs"><div class="label">Channel</div><div class="font-medium text-slate-800">{{ campaign.channel }} · step 1</div></div>
        <div class="rounded-xl border border-slate-200 p-3 text-xs"><div class="label">Recipient</div><div class="truncate font-medium text-slate-800">{{ recipient || '—' }}</div><div class="text-slate-500">{{ lead.contact_email_type?.replace(/_/g, ' ').toLowerCase() }}</div></div>
        <div class="rounded-xl border border-slate-200 p-3 text-xs"><div class="label">Legal basis</div>
          <div class="font-medium" :class="lead.legal_basis === 'UNKNOWN' ? 'text-amber-700' : 'text-slate-800'">{{ lead.legal_basis?.replace(/_/g, ' ') }}</div>
          <div v-if="lead.legal_basis === 'UNKNOWN'" class="text-[10px] text-amber-700">Sending is blocked until set on the lead</div></div>
      </div>
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span class="text-slate-500">Campaign</span><StatusBadge :status="campaign.status" />
        <span v-if="message" class="text-slate-500">· message</span><StatusBadge v-if="message" :status="message.status" />
        <RouterLink :to="`/campaigns/${campaign.id}`" class="ml-auto font-medium text-violet-700 hover:underline">Open campaign ↗</RouterLink>
      </div>

      <form v-if="editing" class="space-y-3 rounded-xl border border-violet-200 bg-violet-50/40 p-3" @submit.prevent="save">
        <div><label class="label" for="o-subj">Subject</label><input id="o-subj" v-model="form.subject" class="input" required maxlength="300" /></div>
        <div><label class="label" for="o-body">Message (plain text — sender identity and opt-out footer are added by the platform)</label>
          <textarea id="o-body" v-model="form.body" rows="9" class="input font-mono text-xs" required /></div>
        <div class="grid gap-3 sm:grid-cols-2">
          <div><label class="label" for="o-h">Offer headline</label><input id="o-h" v-model="form.offer.headline" class="input" maxlength="300" /></div>
          <div><label class="label" for="o-cta">Call to action</label><input id="o-cta" v-model="form.offer.call_to_action" class="input" maxlength="500" /></div>
          <div><label class="label" for="o-v">Value proposition</label><textarea id="o-v" v-model="form.offer.value_proposition" rows="3" class="input" /></div>
          <div><label class="label" for="o-p">Pricing</label><textarea id="o-p" v-model="form.offer.pricing" rows="3" class="input" /></div>
        </div>
        <div class="flex gap-2"><button class="btn-accent" :disabled="busy">Save outreach</button><button type="button" class="btn-secondary" @click="editing = false">Discard</button></div>
      </form>
      <template v-else>
        <section class="rounded-xl border border-slate-200">
          <div class="border-b border-slate-100 px-3 py-2 text-xs"><span class="text-slate-500">Subject:</span> <span class="font-medium text-slate-800">{{ message?.subject || '—' }}</span></div>
          <pre class="max-h-72 overflow-y-auto px-3 py-2 font-sans text-xs whitespace-pre-wrap text-slate-700">{{ message?.body || 'No message for this lead in the campaign.' }}</pre>
        </section>
        <section class="rounded-xl bg-slate-50 p-3 text-xs">
          <div class="label">Suggested offer</div>
          <div class="font-medium text-slate-800">{{ offer.headline || '—' }}</div>
          <p v-if="offer.value_proposition" class="mt-1 line-clamp-4 text-slate-600">{{ offer.value_proposition }}</p>
          <div class="mt-2 grid gap-2 sm:grid-cols-2"><div><span class="text-slate-500">Pricing:</span> {{ offer.pricing || '—' }}</div><div><span class="text-slate-500">Call to action:</span> {{ offer.call_to_action || '—' }}</div></div>
        </section>
      </template>
      <section class="rounded-xl border border-dashed border-slate-300 p-3 text-xs text-slate-500">
        <div class="label">Follow-up message</div>
        Not available: v1 sends only the first e-mail (follow-up sequences need reply detection — ADR-008).
      </section>
      <p v-if="others" class="text-[11px] text-slate-500">This campaign contains {{ others }} other message(s); approving approves the whole campaign.</p>
    </template>

    <p v-if="error" class="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-800" role="alert">{{ error }}</p>
    <p v-if="notice" class="text-xs text-emerald-700" role="status">{{ notice }}</p>
    <div class="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
      <button type="button" class="btn-secondary" :disabled="busy || !!editHint || editing" :title="editHint" @click="startEdit">Edit outreach</button>
      <button v-if="submittable && canWrite" type="button" class="btn-secondary" :disabled="busy || editing" @click="submit">Submit for approval</button>
      <button type="button" class="btn-accent" :disabled="busy || !pending || !canWrite" :title="pending ? '' : 'No pending outreach approval'" @click="approve">Approve outreach</button>
      <span v-if="editHint && campaign" class="w-full text-[11px] text-slate-400">{{ editHint }}</span>
      <span v-if="!pending && campaign" class="w-full text-[11px] text-slate-400">Approve outreach needs a pending approval (campaign is {{ campaign.status.replace(/_/g, ' ') }}).</span>
    </div>
  </div>
</template>
