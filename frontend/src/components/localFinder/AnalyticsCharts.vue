<script setup lang="ts">
import { computed } from 'vue'
import { byCategory, discoveriesOverTime, scoreDistribution } from '@/features/localFinder/model'
import { useLocalFinderStore } from '@/stores/localFinder'
import CategoryBars from './charts/CategoryBars.vue'
import ScoreHistogram from './charts/ScoreHistogram.vue'
import TrendChart from './charts/TrendChart.vue'

/** Bottom row: three charts over the same scope as the KPIs (selected run, or all runs). Real API data only. */
const store = useLocalFinderStore()
const trend = computed(() => discoveriesOverTime(store.scopedRows))
const cats = computed(() => byCategory(store.scopedRows))
const scores = computed(() => scoreDistribution(store.scopedRows))
const empty = computed(() => store.loaded && !store.scopedRows.length)
</script>

<template>
  <div class="grid gap-3 md:grid-cols-3" :class="{ 'opacity-60': !store.loaded }">
    <section class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm" aria-labelledby="ch1">
      <div class="mb-2 flex items-baseline justify-between gap-2">
        <h3 id="ch1" class="text-xs font-semibold text-slate-900">Businesses discovered over time</h3>
        <span class="text-[11px] text-slate-400 tabular-nums">{{ store.scopedRows.length }} total</span>
      </div>
      <TrendChart v-if="trend.length" :points="trend" />
      <p v-else class="grid h-32 place-items-center text-xs text-slate-400">{{ empty ? 'No discoveries yet' : 'Loading…' }}</p>
    </section>
    <section class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm" aria-labelledby="ch2">
      <div class="mb-2 flex items-baseline justify-between gap-2">
        <h3 id="ch2" class="text-xs font-semibold text-slate-900">Opportunities by business category</h3>
        <span class="text-[11px] text-slate-400">qualified leads</span>
      </div>
      <CategoryBars v-if="cats.length" :stats="cats" />
      <p v-else class="grid h-32 place-items-center text-xs text-slate-400">{{ empty ? 'No categories yet' : 'Loading…' }}</p>
    </section>
    <section class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm" aria-labelledby="ch3">
      <div class="mb-2 flex items-baseline justify-between gap-2">
        <h3 id="ch3" class="text-xs font-semibold text-slate-900">Lead quality distribution</h3>
        <span class="text-[11px] text-slate-400">score 0–100</span>
      </div>
      <ScoreHistogram v-if="!empty" :buckets="scores" />
      <p v-else class="grid h-32 place-items-center text-xs text-slate-400">No scored leads yet</p>
    </section>
  </div>
</template>
