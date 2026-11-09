<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { Lead, Paginated } from '@/api/types'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel } from '@/components/format'

const source = ref('')
const leads = ref<Lead[]>([])
const router = useRouter()

watch(source, async () => {
  leads.value = (await api.get<Paginated<Lead>>('leads/', { source: source.value || undefined, ordering: '-score' })).results
}, { immediate: true })

</script>

<template>
  <PageHeader title="Leads & project briefs" subtitle="Businesses qualified by either agent. Contact data is personal data — handle per GDPR.">
    <select v-model="source" class="input w-48"><option value="">All sources</option><option value="LOCAL_LEADS">Agent 2 · Local</option><option value="SAAS_RESEARCH">Agent 1 · SaaS</option></select>
  </PageHeader>
  <div class="card overflow-x-auto p-0">
    <table class="table">
      <thead><tr><th>Business</th><th>Source</th><th>Score</th><th>Problems</th><th>Legal basis</th><th>Status</th></tr></thead>
      <tbody>
        <tr v-for="l in leads" :key="l.id" class="cursor-pointer hover:bg-slate-50" @click="router.push(`/leads/${l.id}`)">
            <td><div class="font-medium">{{ l.business.name }}</div><div class="text-xs text-slate-500">{{ l.business.city }} {{ l.business.country_code }} · {{ l.business.domain }}</div></td>
            <td class="text-xs text-slate-500">{{ agentLabel(l.source) }}</td>
            <td class="tabular-nums">{{ l.score ?? '—' }}</td>
            <td class="text-xs">{{ (l.problems as any[]).map((p) => p.code).join(', ') || '—' }}</td>
            <td class="text-xs">{{ l.legal_basis }}<span v-if="l.is_suppressed" class="ml-1 text-rose-600">(suppressed)</span></td>
            <td><StatusBadge :status="l.status" /></td>
        </tr>
        <tr v-if="!leads.length"><td colspan="6" class="py-8 text-center text-slate-500">No leads yet.</td></tr>
      </tbody>
    </table>
  </div>
</template>
