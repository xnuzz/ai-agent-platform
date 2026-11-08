<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/api/client'
import type { Lead, Paginated, ProjectBrief } from '@/api/types'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel } from '@/components/format'

const source = ref('')
const leads = ref<Lead[]>([])
const briefs = ref<Record<string, ProjectBrief[]>>({})
const open = ref<string | null>(null)

watch(source, async () => {
  leads.value = (await api.get<Paginated<Lead>>('leads/', { source: source.value || undefined, ordering: '-score' })).results
}, { immediate: true })

async function toggle(lead: Lead) {
  open.value = open.value === lead.id ? null : lead.id
  if (open.value && !briefs.value[lead.id]) {
    briefs.value[lead.id] = (await api.get<Paginated<ProjectBrief>>('project-briefs/', { lead: lead.id })).results
  }
}
</script>

<template>
  <PageHeader title="Leads & project briefs" subtitle="Businesses qualified by either agent. Contact data is personal data — handle per GDPR.">
    <select v-model="source" class="input w-48"><option value="">All sources</option><option value="LOCAL_LEADS">Agent 2 · Local</option><option value="SAAS_RESEARCH">Agent 1 · SaaS</option></select>
  </PageHeader>
  <div class="card overflow-x-auto p-0">
    <table class="table">
      <thead><tr><th>Business</th><th>Source</th><th>Score</th><th>Problems</th><th>Legal basis</th><th>Status</th></tr></thead>
      <tbody>
        <template v-for="l in leads" :key="l.id">
          <tr class="cursor-pointer hover:bg-slate-50" @click="toggle(l)">
            <td><div class="font-medium">{{ l.business.name }}</div><div class="text-xs text-slate-500">{{ l.business.city }} {{ l.business.country_code }} · {{ l.business.domain }}</div></td>
            <td class="text-xs text-slate-500">{{ agentLabel(l.source) }}</td>
            <td class="tabular-nums">{{ l.score ?? '—' }}</td>
            <td class="text-xs">{{ (l.problems as any[]).map((p) => p.code).join(', ') || '—' }}</td>
            <td class="text-xs">{{ l.legal_basis }}<span v-if="l.is_suppressed" class="ml-1 text-rose-600">(suppressed)</span></td>
            <td><StatusBadge :status="l.status" /></td>
          </tr>
          <tr v-if="open === l.id">
            <td colspan="6" class="bg-slate-50">
              <p class="mb-2 text-sm">{{ l.qualification_notes }}</p>
              <div v-for="b in briefs[l.id] ?? []" :key="b.id" class="mb-2 rounded-lg border border-slate-200 bg-white p-3">
                <div class="flex justify-between"><span class="font-medium">{{ b.title }}</span><StatusBadge :status="b.status" /></div>
                <p class="text-sm text-slate-600">{{ b.summary }}</p>
              </div>
              <p v-if="!(briefs[l.id] ?? []).length" class="text-xs text-slate-500">No project brief.</p>
            </td>
          </tr>
        </template>
        <tr v-if="!leads.length"><td colspan="6" class="py-8 text-center text-slate-500">No leads yet.</td></tr>
      </tbody>
    </table>
  </div>
</template>
