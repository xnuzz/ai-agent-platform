<script setup lang="ts">
import { computed, ref } from 'vue'
import { POTENTIAL_LABEL, type Potential, type ScoreBucket } from '@/features/localFinder/model'

/** Lead score distribution: 10 columns on one baseline, sequential purple by tier (legend + table + tooltip). */
const props = defineProps<{ buckets: ScoreBucket[] }>()
const max = computed(() => Math.max(1, ...props.buckets.map((b) => b.count)))
const hover = ref<number | null>(null)
const FILL: Record<Potential, string> = { low: '#c4b5fd', medium: '#8b5cf6', high: '#5b21b6', unscored: '#e2e8f0' }
const legend: Potential[] = ['low', 'medium', 'high']
</script>

<template>
  <div class="relative">
    <div class="flex h-24 items-end gap-0.5" aria-hidden="true">
      <div v-for="(b, i) in buckets" :key="b.from" class="flex h-full flex-1 flex-col items-center justify-end outline-none focus-visible:ring-2 focus-visible:ring-violet-300"
        tabindex="0" @pointerenter="hover = i" @pointerleave="hover = null" @focus="hover = i" @blur="hover = null">
        <span v-if="b.count" class="mb-0.5 text-[9px] font-medium text-slate-500 tabular-nums">{{ b.count }}</span>
        <span class="w-full max-w-6 rounded-t transition-all duration-500" :style="{ height: `${(b.count / max) * 78}%`, minHeight: b.count ? '3px' : '0', background: FILL[b.potential], opacity: hover == null || hover === i ? 1 : 0.55 }" />
      </div>
    </div>
    <div class="relative mt-1 h-4 border-t border-slate-100 text-[10px] text-slate-400 tabular-nums" aria-hidden="true">
      <span v-for="t in [0, 50, 75, 100]" :key="t" class="absolute top-0.5" :style="{ left: `${t}%`, transform: t === 0 ? 'none' : t === 100 ? 'translateX(-100%)' : 'translateX(-50%)' }">{{ t }}</span>
    </div>
    <div class="mt-1 flex gap-3 text-[10px] text-slate-500">
      <span v-for="p in legend" :key="p" class="flex items-center gap-1"><span class="h-2 w-2 rounded-sm" :style="{ background: FILL[p] }" />{{ POTENTIAL_LABEL[p].replace(' potential', '') }}</span>
    </div>
    <div v-if="hover != null && buckets[hover]" class="pointer-events-none absolute right-0 -top-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] shadow-lg" role="status">
      <div class="font-semibold text-slate-900">{{ buckets[hover]!.count }} lead(s)</div>
      <div class="text-slate-500">Score {{ buckets[hover]!.from }}–{{ buckets[hover]!.to }} · {{ POTENTIAL_LABEL[buckets[hover]!.potential] }}</div>
    </div>
    <table class="sr-only">
      <caption>Lead quality distribution</caption>
      <thead><tr><th>Score range</th><th>Leads</th></tr></thead>
      <tbody><tr v-for="b in buckets" :key="b.from"><td>{{ b.from }}–{{ b.to }}</td><td>{{ b.count }}</td></tr></tbody>
    </table>
  </div>
</template>
