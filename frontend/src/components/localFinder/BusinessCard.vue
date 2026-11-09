<script setup lang="ts">
import { computed } from 'vue'
import { locationLabel, POTENTIAL_LABEL, problemLabel, REVIEW_LABEL, type LeadRow } from '@/features/localFinder/model'
import LeadScore from './LeadScore.vue'

const props = defineProps<{ row: LeadRow; selected: boolean; fresh: boolean }>()
defineEmits<{ select: []; open: [] }>()

const b = computed(() => props.row.lead.business)
const initials = computed(() => b.value.name.split(/\s+/).filter((w) => /\p{L}/u.test(w)).slice(0, 2).map((w) => w.match(/\p{L}/u)![0].toUpperCase()).join('') || '?')
// Deterministic avatar hue per business (violet → fuchsia → indigo band); no external images are loaded.
const hue = computed(() => 250 + ([...b.value.name].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % 70))
const reviewTone: Record<string, string> = {
  new: 'bg-violet-100 text-violet-700', reviewed: 'bg-slate-100 text-slate-600', approved: 'bg-emerald-100 text-emerald-700', rejected: 'bg-rose-100 text-rose-700',
}
</script>

<template>
  <div class="group relative rounded-xl border transition duration-150"
    :class="[selected ? 'border-violet-600 bg-violet-600 text-white shadow-lg shadow-violet-600/25' : 'border-slate-200/80 bg-white hover:border-violet-300 hover:shadow-md hover:shadow-violet-500/5', fresh && !selected ? 'lbf-card-fresh' : '']">
    <button type="button" class="block w-full rounded-xl p-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500"
      :aria-pressed="selected" :data-lead-id="row.lead.id" data-card @click="$emit('select')" @dblclick="$emit('open')">
      <div class="flex items-start gap-3">
        <div class="grid h-10 w-10 shrink-0 place-items-center rounded-lg text-sm font-semibold text-white"
          :style="{ background: `linear-gradient(135deg, hsl(${hue} 70% 62%), hsl(${hue + 25} 65% 48%))` }" aria-hidden="true">{{ initials }}</div>
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm font-semibold leading-tight">{{ b.name }}</div>
          <div class="mt-0.5 truncate text-xs" :class="selected ? 'text-violet-100' : 'text-slate-500'">{{ b.category || 'Uncategorised' }}</div>
          <div class="mt-0.5 flex items-center gap-1 truncate text-xs" :class="selected ? 'text-violet-100' : 'text-slate-500'">
            <svg viewBox="0 0 20 20" class="h-3 w-3 shrink-0" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 18s6-5.2 6-10A6 6 0 0 0 4 8c0 4.8 6 10 6 10Zm0-8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" clip-rule="evenodd" /></svg>
            <span class="truncate">{{ locationLabel(row.lead) }}</span>
            <span v-if="!row.coords" class="shrink-0 rounded px-1 text-[10px]" :class="selected ? 'bg-white/15' : 'bg-amber-50 text-amber-700'" title="No coordinates supplied — not shown on the map">no map pin</span>
          </div>
        </div>
        <LeadScore :score="row.lead.score" :size="38" :dark="selected" />
      </div>
      <p v-if="row.problem" class="mt-2 line-clamp-2 text-xs" :class="selected ? 'text-white/90' : 'text-slate-600'">
        <span class="font-medium" :class="selected ? 'text-white' : 'text-violet-700'">Problem:</span> {{ problemLabel(row.problem) }}
      </p>
      <div class="mt-2 flex items-center gap-1.5 pr-16">
        <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap" :class="selected ? 'bg-white/20 text-white' : reviewTone[row.review]">{{ REVIEW_LABEL[row.review] }}</span>
        <span class="truncate text-[11px]" :class="selected ? 'text-violet-100' : 'text-slate-400'">{{ POTENTIAL_LABEL[row.potential] }}</span>
      </div>
    </button>
    <button type="button" class="absolute right-2 bottom-2 rounded-md px-2 py-1 text-[11px] font-medium transition"
      :class="selected ? 'bg-white/15 text-white hover:bg-white/25' : 'text-violet-700 hover:bg-violet-50'"
      :aria-label="`Open details for ${b.name}`" @click="$emit('open')">Details →</button>
  </div>
</template>

<style scoped>
.lbf-card-fresh { animation: card-fresh 2.4s ease-out; }
@keyframes card-fresh { 0%, 30% { background: #f5f3ff; border-color: #a78bfa; } 100% { background: #fff; } }
@media (prefers-reduced-motion: reduce) { .lbf-card-fresh { animation: none; } }
</style>
