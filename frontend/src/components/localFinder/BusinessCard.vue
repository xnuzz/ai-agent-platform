<script setup lang="ts">
import { computed } from 'vue'
import { locationLabel, POTENTIAL_LABEL, problemLabel, REVIEW_LABEL, type LeadRow } from '@/features/localFinder/model'
import LeadScore from './LeadScore.vue'

const props = defineProps<{ row: LeadRow; selected: boolean; fresh: boolean }>()
defineEmits<{ select: []; open: [] }>()

const b = computed(() => props.row.lead.business)
const initials = computed(() => b.value.name.split(/\s+/).filter((w) => /\p{L}/u.test(w)).slice(0, 2).map((w) => w.match(/\p{L}/u)![0].toUpperCase()).join('') || '?')
const reviewTone: Record<string, string> = {
  new: 'bg-white/10 text-ink', reviewed: 'bg-white/[0.06] text-silver', approved: 'bg-ok/10 text-ok', rejected: 'bg-bad/10 text-bad',
}
</script>

<template>
  <div class="lbf-card group relative rounded-[var(--radius)] border" :class="[selected ? 'is-selected' : 'border-line', fresh && !selected ? 'lbf-card-fresh' : '']">
    <button type="button" class="block w-full rounded-[var(--radius)] p-3 text-left"
      :aria-pressed="selected" :data-lead-id="row.lead.id" data-card @click="$emit('select')" @dblclick="$emit('open')">
      <div class="flex items-start gap-3">
        <div class="avatar grid h-10 w-10 shrink-0 place-items-center rounded-xl text-sm font-semibold" aria-hidden="true">{{ initials }}</div>
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm font-semibold leading-tight text-ink">{{ b.name }}</div>
          <div class="mt-0.5 truncate text-xs text-silver">{{ b.category || 'Uncategorised' }}</div>
          <div class="mt-0.5 flex items-center gap-1 truncate text-xs text-silver">
            <svg viewBox="0 0 20 20" class="h-3 w-3 shrink-0" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 18s6-5.2 6-10A6 6 0 0 0 4 8c0 4.8 6 10 6 10Zm0-8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" clip-rule="evenodd" /></svg>
            <span class="truncate">{{ locationLabel(row.lead) }}</span>
            <span v-if="!row.coords" class="shrink-0 rounded px-1 text-[10px] bg-warn/10 text-warn" title="No coordinates supplied — not shown on the map">no map pin</span>
          </div>
        </div>
        <LeadScore :score="row.lead.score" :size="38" />
      </div>
      <p v-if="row.problem" class="mt-2 line-clamp-2 text-xs text-silver">
        <span class="font-medium text-ink">Problem:</span> {{ problemLabel(row.problem) }}
      </p>
      <div class="mt-2 flex items-center gap-1.5 pr-16">
        <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap" :class="reviewTone[row.review]">{{ REVIEW_LABEL[row.review] }}</span>
        <span class="truncate text-[11px] text-muted">{{ POTENTIAL_LABEL[row.potential] }}</span>
      </div>
    </button>
    <button type="button" class="absolute right-2 bottom-2 rounded-full px-2.5 py-1 text-[11px] font-medium text-ink transition hover:bg-white/10"
      :aria-label="`Open details for ${b.name}`" @click="$emit('open')">Details →</button>
  </div>
</template>

<style scoped>
.lbf-card { background: rgb(255 255 255 / 0.025); transition: background-color var(--dur-2) var(--ease), border-color var(--dur-2) var(--ease), box-shadow var(--dur-2) var(--ease), transform var(--dur-2) var(--ease); }
.lbf-card:hover { background: rgb(255 255 255 / 0.05); border-color: rgb(255 255 255 / 0.18); }
.lbf-card.is-selected {
  border-color: rgb(255 255 255 / 0.55); background: linear-gradient(180deg, rgb(255 255 255 / 0.12), rgb(255 255 255 / 0.05));
  box-shadow: 0 0 0 1px rgb(255 255 255 / 0.15), 0 0 28px -6px rgb(255 255 255 / 0.35);
}
.avatar { color: #0a0a0a; background: radial-gradient(circle at 30% 25%, #fafafa, #a1a1aa 55%, #52525b); }
.lbf-card-fresh { animation: card-fresh 2.4s var(--ease); }
@keyframes card-fresh { 0%, 30% { background: rgb(255 255 255 / 0.14); border-color: rgb(255 255 255 / 0.6); } 100% { background: rgb(255 255 255 / 0.025); } }
</style>