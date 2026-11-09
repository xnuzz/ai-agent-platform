<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import type { DashboardSummary, Paginated, ResearchTask } from '@/api/types'
import PageHeader from '@/components/PageHeader.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel, taskLabel } from '@/components/format'
import { usePolling } from '@/components/usePolling'

const summary = ref<DashboardSummary | null>(null)
const active = ref<ResearchTask[]>([])
const sum = (o?: Record<string, number>) => Object.values(o ?? {}).reduce((a, b) => a + b, 0)

usePolling(async () => {
  summary.value = await api.get<DashboardSummary>('dashboard/summary/')
  active.value = (await api.get<Paginated<ResearchTask>>('research-tasks/', { status: 'RUNNING' })).results
})

const tiles = computed(() => {
  const s = summary.value
  return [
    { label: 'Pending approvals', value: sum(s?.pending_approvals), to: '/approvals' },
    { label: 'Active agent tasks', value: sum(s?.active_tasks_by_agent), to: '/tasks' },
    { label: 'Leads', value: sum(s?.leads), to: '/leads' },
    { label: 'Messages sent', value: s?.outreach_messages?.SENT ?? 0, to: '/campaigns' },
  ]
})
</script>

<template>
  <PageHeader title="Dashboard" subtitle="Both agents, one pipeline. Nothing is sent without your approval." />
  <div class="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
    <RouterLink v-for="t in tiles" :key="t.label" :to="t.to" class="card hover:border-indigo-300">
      <div class="text-xs font-medium tracking-wide text-slate-500 uppercase">{{ t.label }}</div>
      <div class="mt-2 text-3xl font-semibold tabular-nums">{{ t.value }}</div>
    </RouterLink>
  </div>
  <div class="grid gap-4 lg:grid-cols-2">
    <section class="card">
      <h2 class="mb-3 font-medium">Running now</h2>
      <p v-if="!active.length" class="text-sm text-slate-500">No agent is working right now.</p>
      <RouterLink v-for="t in active" :key="t.id" :to="`/tasks/${t.id}`" class="mb-3 block">
        <div class="flex justify-between text-sm"><span>{{ taskLabel(t.task_type) }}</span><span class="text-slate-500">{{ t.progress }}%</span></div>
        <div class="mb-1 text-xs text-slate-500">{{ agentLabel(t.agent) }} · {{ t.stage || 'starting' }} {{ t.progress_message }}</div>
        <ProgressBar :value="t.progress ?? 0" />
      </RouterLink>
    </section>
    <section class="card">
      <h2 class="mb-3 font-medium">Pipeline</h2>
      <dl v-if="summary" class="space-y-2 text-sm">
        <div v-for="(obj, key) in { 'Software ideas': summary.software_ideas, 'Project briefs': summary.project_briefs, 'Campaigns': summary.campaigns, 'Leads by source': summary.leads_by_source }" :key="key">
          <dt class="text-slate-500">{{ key }}</dt>
          <dd class="mt-1 flex flex-wrap gap-2">
            <span v-for="(n, s) in obj" :key="s" class="flex items-center gap-1"><StatusBadge :status="String(s)" />{{ n }}</span>
            <span v-if="!Object.keys(obj).length" class="text-slate-400">none yet</span>
          </dd>
        </div>
      </dl>
    </section>
  </div>
</template>
