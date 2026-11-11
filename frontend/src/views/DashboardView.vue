<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import type { DashboardSummary, Paginated, ResearchTask } from '@/api/types'
import PageHeader from '@/components/PageHeader.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StatTile from '@/components/StatTile.vue'
import BarList from '@/components/charts/BarList.vue'
import DonutChart from '@/components/charts/DonutChart.vue'
import { monoShade } from '@/components/charts/palette'
import { agentLabel, taskLabel } from '@/components/format'
import { usePolling } from '@/components/usePolling'

const summary = ref<DashboardSummary | null>(null)
const active = ref<ResearchTask[]>([])
const sum = (o?: Record<string, number>) => Object.values(o ?? {}).reduce((a, b) => a + b, 0)
const pretty = (s: string) => s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, ' ')
const rows = (o?: Record<string, number>) => Object.entries(o ?? {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: pretty(k), value: v }))

usePolling(async () => {
  summary.value = await api.get<DashboardSummary>('dashboard/summary/')
  active.value = (await api.get<Paginated<ResearchTask>>('research-tasks/', { status: 'RUNNING' })).results
})

const tiles = computed(() => {
  const s = summary.value
  const qualified = ['QUALIFIED', 'CONTACTED', 'REPLIED', 'WON'].reduce((n, k) => n + (s?.leads?.[k] ?? 0), 0)
  const pending = s?.pending_approvals ?? {}
  return [
    { label: 'Total leads', value: sum(s?.leads), sub: `${qualified} qualified`, icon: 'leads', to: '/leads' },
    { label: 'Software opportunities', value: sum(s?.opportunities), sub: `${s?.opportunities?.SHORTLISTED ?? 0} shortlisted · ${sum(s?.software_ideas)} ideas`, icon: 'ideas', to: '/ideas' },
    { label: 'Research tasks', value: sum(s?.research_tasks), sub: `${sum(s?.active_tasks_by_agent)} active agent tasks`, icon: 'tasks', to: '/tasks' },
    { label: 'Pending approvals', value: sum(pending), sub: Object.entries(pending).map(([k, v]) => `${v} ${pretty(k).toLowerCase()}`).join(' · ') || 'nothing waiting', icon: 'approvals', to: '/approvals' },
    { label: 'Active campaigns', value: s?.campaigns?.ACTIVE ?? 0, sub: `${s?.outreach_messages?.SENT ?? 0} messages sent`, icon: 'campaigns', to: '/campaigns' },
  ] as const
})
const pipeline = computed(() => {
  const s = summary.value
  if (!s) return []
  return ([['Software ideas', s.software_ideas], ['Project briefs', s.project_briefs], ['Campaigns', s.campaigns], ['Outreach messages', s.outreach_messages]] as const)
    .map(([label, o]) => ({ label, total: sum(o), parts: rows(o) }))
})
</script>

<template>
  <PageHeader title="Dashboard" subtitle="Both agents, one pipeline. Nothing is sent without your approval." />

  <div class="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
    <StatTile v-for="(t, i) in tiles" :key="t.label" v-bind="t" class="fade-in" :class="i === 4 ? 'col-span-2 md:col-span-1' : ''" :style="{ animationDelay: `${i * 40}ms` }" />
  </div>

  <div class="grid gap-4 lg:grid-cols-3">
    <section class="card lg:col-span-2" aria-labelledby="activity-h">
      <div class="mb-4 flex items-center justify-between">
        <h2 id="activity-h" class="section-title">Agent activity</h2>
        <span class="flex items-center gap-1.5 text-xs text-silver">
          <span class="h-1.5 w-1.5 rounded-full" :class="active.length ? 'live-dot bg-white' : 'bg-muted'" />{{ active.length ? `${active.length} running` : 'idle' }}
        </span>
      </div>
      <p v-if="!active.length" class="py-6 text-center text-sm text-silver">No agent is working right now.</p>
      <ul class="space-y-3">
        <li v-for="t in active" :key="t.id">
          <RouterLink :to="`/tasks/${t.id}`" class="lift block rounded-[var(--radius)] border border-line bg-white/[0.02] p-3">
            <div class="flex justify-between gap-2 text-sm"><span class="font-medium text-ink">{{ taskLabel(t.task_type) }}</span><span class="text-silver tabular-nums">{{ t.progress }}%</span></div>
            <div class="mt-0.5 mb-2 truncate text-xs text-silver">{{ agentLabel(t.agent) }} · {{ (t.stage || 'starting').replace(/_/g, ' ').toLowerCase() }} {{ t.progress_message }}</div>
            <ProgressBar :value="t.progress ?? 0" />
          </RouterLink>
        </li>
      </ul>
    </section>

    <section class="card" aria-labelledby="tasks-h">
      <h2 id="tasks-h" class="section-title mb-4">Research tasks</h2>
      <DonutChart title="Research tasks by status" :items="rows(summary?.research_tasks)" />
    </section>

    <section class="card lg:col-span-2" aria-labelledby="pipeline-h">
      <h2 id="pipeline-h" class="section-title mb-4">Pipeline</h2>
      <div v-if="summary" class="space-y-4">
        <div v-for="p in pipeline" :key="p.label">
          <div class="mb-1.5 flex justify-between text-xs"><span class="text-silver">{{ p.label }}</span><span class="text-ink tabular-nums">{{ p.total }}</span></div>
          <div class="flex h-2 gap-[2px] overflow-hidden rounded-full bg-[var(--viz-track)]" role="img" :aria-label="`${p.label}: ${p.parts.map((x) => `${x.label} ${x.value}`).join(', ') || 'none'}`">
            <div v-for="(x, i) in p.parts" :key="x.label" class="h-full first:rounded-l-full last:rounded-r-full transition-[width] duration-700 ease-out-soft"
              :style="{ width: `${(x.value / Math.max(1, p.total)) * 100}%`, background: monoShade(i) }" />
          </div>
          <div class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
            <span v-for="(x, i) in p.parts" :key="x.label" class="flex items-center gap-1"><span class="h-1.5 w-1.5 rounded-full" :style="{ background: monoShade(i) }" />{{ x.label }} <span class="text-soft tabular-nums">{{ x.value }}</span></span>
            <span v-if="!p.parts.length">none yet</span>
          </div>
        </div>
      </div>
      <div v-else class="space-y-3"><div v-for="i in 4" :key="i" class="skeleton h-8" /></div>
    </section>

    <section class="card" aria-labelledby="sources-h">
      <h2 id="sources-h" class="section-title mb-4">Leads by source</h2>
      <BarList :items="Object.entries(summary?.leads_by_source ?? {}).map(([k, v]) => ({ label: agentLabel(k), value: v }))" />
    </section>
  </div>
</template>

<style scoped>
.live-dot { box-shadow: 0 0 8px 1px rgb(255 255 255 / 0.8); animation: blink 1.6s ease-in-out infinite; }
@keyframes blink { 50% { opacity: 0.3; } }
</style>
