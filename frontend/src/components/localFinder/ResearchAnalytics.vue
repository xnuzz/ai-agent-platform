<script setup lang="ts">
import { computed } from 'vue'
import { compact } from '@/features/localFinder/model'
import { useLocalFinderStore, type ActivityKind } from '@/stores/localFinder'

const store = useLocalFinderStore()
const k = computed(() => store.kpis)
const pct = (n: number) => (k.value.discovered ? Math.round((n / k.value.discovered) * 100) : 0)

/** Six KPI tiles. Every number is computed from leads returned by the API for the current scope. */
const tiles = computed(() => [
  { id: 'scanned', label: 'Businesses scanned', value: k.value.scanned, share: pct(k.value.scanned), note: 'with a website to analyse' },
  { id: 'discovered', label: 'Businesses discovered', value: k.value.discovered, share: null, note: k.value.discovered24h ? `+${k.value.discovered24h} in 24 h` : 'none in 24 h', trend: k.value.discovered24h > 0 },
  { id: 'qualified', label: 'Qualified leads', value: k.value.qualified, share: k.value.qualifiedRate, note: k.value.qualified24h ? `+${k.value.qualified24h} in 24 h` : `${k.value.qualifiedRate}% of discovered`, trend: k.value.qualified24h > 0 },
  { id: 'high', label: 'High-potential leads', value: k.value.high, share: pct(k.value.high), note: 'score ≥ 75' },
  { id: 'gaps', label: 'Websites missing / outdated', value: k.value.websiteGaps, share: pct(k.value.websiteGaps), note: 'no site, down, outdated or not mobile' },
  { id: 'opps', label: 'Technical opportunities', value: k.value.opportunities, share: null, note: k.value.discovered ? `${(k.value.opportunities / k.value.discovered).toFixed(1)} per business` : 'problems found' },
])
const R = 14
const C = 2 * Math.PI * R

const ICON: Record<ActivityKind, string> = {
  discovered: 'bg-white', qualified: 'bg-soft', updated: 'bg-muted', started: 'bg-silver', progress: 'bg-muted',
  completed: 'bg-ok', failed: 'bg-bad', cancelled: 'bg-muted',
}
const ago = (t: number) => {
  const s = Math.max(0, Math.round((store.now - t) / 1000))
  return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.floor(s / 60)}m ago` : new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <section class="card p-4" aria-labelledby="kpi-h">
    <div class="flex items-center justify-between">
      <h2 id="kpi-h" class="text-sm font-semibold text-ink">Research analytics</h2>
      <span class="text-[11px] text-muted">{{ store.taskFilter ? 'this run' : 'all runs' }}</span>
    </div>
    <div class="mt-3 grid grid-cols-2 gap-2">
      <div v-for="t in tiles" :key="t.id" class="lift rounded-[var(--radius)] border border-line bg-white/[0.025] px-2.5 py-2" :data-testid="`kpi-${t.id}`" :title="t.note">
        <div class="line-clamp-2 min-h-[2.4em] text-[10px] leading-tight font-medium tracking-wide text-silver uppercase">{{ t.label }}</div>
        <div class="mt-0.5 flex items-center justify-between gap-1">
          <span class="text-xl font-semibold text-ink" data-value>{{ compact(t.value) }}</span>
          <svg v-if="t.share != null" viewBox="0 0 36 36" class="h-6 w-6 shrink-0 -rotate-90" role="img" :aria-label="`${t.share}% of discovered`">
            <circle cx="18" cy="18" :r="R" fill="none" stroke="var(--viz-track)" stroke-width="5" />
            <circle cx="18" cy="18" :r="R" fill="none" stroke="var(--viz-1)" stroke-width="5" stroke-linecap="round" :stroke-dasharray="C" :stroke-dashoffset="C * (1 - t.share / 100)" class="transition-[stroke-dashoffset] duration-700" />
          </svg>
        </div>
        <div class="flex items-center gap-1 truncate text-[10px]" :class="t.trend ? 'text-ok' : 'text-muted'">
          <svg v-if="t.trend" viewBox="0 0 12 12" class="h-2.5 w-2.5 shrink-0" fill="currentColor" aria-hidden="true"><path d="M6 2 11 8H1z" /></svg><span class="truncate">{{ t.note }}</span>
        </div>
      </div>
    </div>
  </section>

  <section class="flex min-h-[200px] flex-1 flex-col card p-4" aria-labelledby="activity-h">
    <div class="flex items-center justify-between">
      <h2 id="activity-h" class="text-sm font-semibold text-ink">Agent activity</h2>
      <span class="flex items-center gap-1.5 text-[11px]" :class="store.connection === 'live' ? 'text-ok' : 'text-warn'" data-testid="connection">
        <span class="h-1.5 w-1.5 rounded-full" :class="store.connection === 'live' ? 'bg-ok' : 'bg-warn'" />
        {{ store.demo ? 'demo data' : store.connection === 'live' ? 'connected' : store.connection === 'connecting' ? 'connecting…' : 'reconnecting…' }}
      </span>
    </div>
    <p v-if="store.connection === 'reconnecting' && store.syncError" class="mt-2 rounded-lg bg-warn/10 px-2.5 py-1.5 text-[11px] text-warn" role="status">
      Connection lost ({{ store.syncError }}). Retrying automatically — the data shown may be out of date.
    </p>
    <ol class="mt-2 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1" aria-live="polite" aria-relevant="additions">
      <li v-for="a in store.activity" :key="a.id" class="flex gap-2 text-xs">
        <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" :class="ICON[a.kind]" />
        <div class="min-w-0 flex-1">
          <button v-if="a.leadId && store.leads[a.leadId]" type="button" class="block w-full truncate text-left text-soft hover:text-ink" @click="store.select(a.leadId)">{{ a.text }}</button>
          <span v-else class="block truncate text-soft">{{ a.text }}</span>
          <span class="text-[10px] text-muted">{{ ago(a.at) }}</span>
        </div>
      </li>
      <li v-if="!store.activity.length" class="py-4 text-center text-xs text-muted">Live events appear here while Agent 2 works.</li>
    </ol>
  </section>
</template>
