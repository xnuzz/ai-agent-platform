<script setup lang="ts">
import { ref } from 'vue'
import { api, errorText } from '@/api/client'
import type { Paginated, ResearchTask } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import PageHeader from '@/components/PageHeader.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel, fmtDate, taskLabel } from '@/components/format'
import { usePolling } from '@/components/usePolling'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const tasks = ref<ResearchTask[]>([])
const error = ref<string | null>(null)
const kind = ref<'saas' | 'local'>('saas')
const saas = ref({ industry: '', regions: '', keywords: '', max_opportunities: 5 })
const local = ref({ city: '', country_code: '', radius_km: 10, categories: '', max_businesses: 25 })
const split = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)

const load = async () => { tasks.value = (await api.get<Paginated<ResearchTask>>('research-tasks/')).results }
usePolling(load)

async function start() {
  error.value = null
  try {
    const body = kind.value === 'saas'
      ? { task_type: 'SAAS_OPPORTUNITY_RESEARCH', input: { industry: saas.value.industry, regions: split(saas.value.regions), keywords: split(saas.value.keywords), max_opportunities: saas.value.max_opportunities } }
      : { task_type: 'LOCAL_LEAD_DISCOVERY', input: { location: { city: local.value.city, country_code: local.value.country_code, radius_km: local.value.radius_km }, categories: split(local.value.categories), max_businesses: local.value.max_businesses } }
    await api.post('research-tasks/', body)
    await load()
  } catch (e) { error.value = errorText(e) }
}
</script>

<template>
  <PageHeader title="Agent tasks" subtitle="Start research. Agents prepare everything; approvals gate every outbound step." />
  <ErrorBanner :message="error" />
  <form v-if="auth.canWrite()" class="card mb-6 space-y-4" @submit.prevent="start">
    <div class="flex gap-2">
      <button type="button" :class="kind === 'saas' ? 'btn-primary' : 'btn-secondary'" @click="kind = 'saas'">Agent 1 · SaaS opportunities</button>
      <button type="button" :class="kind === 'local' ? 'btn-primary' : 'btn-secondary'" @click="kind = 'local'">Agent 2 · Local leads</button>
    </div>
    <div v-if="kind === 'saas'" class="grid gap-3 md:grid-cols-4">
      <div class="md:col-span-2"><label class="label">Industry</label><input v-model="saas.industry" required class="input" placeholder="Dental clinics" /></div>
      <div><label class="label">Regions (ISO, comma)</label><input v-model="saas.regions" class="input" placeholder="DE, AT" /></div>
      <div><label class="label">Max opportunities</label><input v-model.number="saas.max_opportunities" type="number" min="1" max="20" class="input" /></div>
      <div class="md:col-span-4"><label class="label">Keywords (comma)</label><input v-model="saas.keywords" class="input" /></div>
    </div>
    <div v-else class="grid gap-3 md:grid-cols-4">
      <div><label class="label">City</label><input v-model="local.city" required class="input" placeholder="Plovdiv" /></div>
      <div><label class="label">Country (ISO)</label><input v-model="local.country_code" required maxlength="2" class="input" placeholder="BG" /></div>
      <div><label class="label">Radius km</label><input v-model.number="local.radius_km" type="number" min="1" max="100" class="input" /></div>
      <div><label class="label">Max businesses</label><input v-model.number="local.max_businesses" type="number" min="1" max="200" class="input" /></div>
      <div class="md:col-span-4"><label class="label">Categories (comma)</label><input v-model="local.categories" class="input" placeholder="Bakery, Dentist" /></div>
    </div>
    <button class="btn-primary">Start task</button>
  </form>
  <div class="card overflow-x-auto p-0">
    <table class="table">
      <thead><tr><th>Task</th><th>Agent</th><th>Status</th><th class="w-48">Progress</th><th>Created</th></tr></thead>
      <tbody>
        <tr v-for="t in tasks" :key="t.id" class="hover:bg-slate-50">
          <td><RouterLink :to="`/tasks/${t.id}`" class="font-medium text-indigo-700">{{ taskLabel(t.task_type) }}</RouterLink></td>
          <td class="text-slate-500">{{ agentLabel(t.agent) }}</td>
          <td><StatusBadge :status="t.status" /></td>
          <td><ProgressBar :value="t.progress ?? 0" /><div class="mt-1 text-xs text-slate-500">{{ t.stage }}</div></td>
          <td class="text-slate-500">{{ fmtDate(t.created_at) }}</td>
        </tr>
        <tr v-if="!tasks.length"><td colspan="5" class="py-8 text-center text-slate-500">No tasks yet.</td></tr>
      </tbody>
    </table>
  </div>
</template>
