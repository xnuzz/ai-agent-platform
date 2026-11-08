<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, errorText } from '@/api/client'
import type { Campaign, OutreachMessage, Paginated } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel, fmtDate } from '@/components/format'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ id: string }>()
const auth = useAuthStore()
const campaign = ref<Campaign | null>(null)
const messages = ref<OutreachMessage[]>([])
const error = ref<string | null>(null)

async function load() {
  campaign.value = await api.get<Campaign>(`campaigns/${props.id}/`)
  messages.value = (await api.get<Paginated<OutreachMessage>>('outreach-messages/', { campaign: props.id, page_size: 100 })).results
}
onMounted(load)

async function run(fn: () => Promise<unknown>) {
  error.value = null
  try { await fn(); await load() } catch (e) { error.value = errorText(e) }
}
const action = (a: 'launch' | 'pause' | 'cancel') => run(() => api.post(`campaigns/${props.id}/${a}/`))
const cancelMsg = (id: string) => run(() => api.post(`outreach-messages/${id}/cancel/`))
</script>

<template>
  <template v-if="campaign">
    <PageHeader :title="campaign.name" :subtitle="`${agentLabel(campaign.source)} · ${campaign.channel}`">
      <template v-if="auth.canWrite()">
        <button v-if="['APPROVED', 'PAUSED'].includes(campaign.status ?? '')" class="btn-primary" @click="action('launch')">Launch</button>
        <button v-if="campaign.status === 'ACTIVE'" class="btn-secondary" @click="action('pause')">Pause</button>
        <button v-if="['DRAFT', 'APPROVED', 'ACTIVE', 'PAUSED', 'CHANGES_REQUESTED'].includes(campaign.status ?? '')" class="btn-danger" @click="action('cancel')">Cancel</button>
      </template>
    </PageHeader>
    <ErrorBanner :message="error" />
    <div class="mb-4 flex flex-wrap gap-4 text-sm"><StatusBadge :status="campaign.status" /><span>Approved {{ fmtDate(campaign.approved_at) }}</span><span>Launched {{ fmtDate(campaign.launched_at) }}</span></div>
    <div class="space-y-3">
      <article v-for="m in messages" :key="m.id" class="card">
        <div class="flex items-start justify-between gap-2">
          <div><div class="text-xs text-slate-500">To {{ m.business_name }} &lt;{{ m.to_email }}&gt;</div><div class="font-medium">{{ m.subject }}</div></div>
          <div class="flex items-center gap-2"><StatusBadge :status="m.status" />
            <button v-if="auth.canWrite() && ['DRAFT', 'WAITING_FOR_APPROVAL', 'APPROVED'].includes(m.status ?? '')" class="btn-secondary" @click="cancelMsg(m.id)">Exclude</button>
          </div>
        </div>
        <pre class="mt-2 font-sans text-sm whitespace-pre-wrap text-slate-700">{{ m.body }}</pre>
        <div v-if="m.error && Object.keys(m.error).length" class="mt-2 text-xs text-rose-700">{{ (m.error as any).code }} {{ ((m.error as any).reasons ?? []).join(', ') }}</div>
      </article>
    </div>
  </template>
</template>
