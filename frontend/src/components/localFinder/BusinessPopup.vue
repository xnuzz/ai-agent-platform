<script setup lang="ts">
import { computed } from 'vue'
import { locationLabel, problemLabel, REVIEW_LABEL, type LeadRow } from '@/features/localFinder/model'
import LeadScore from './LeadScore.vue'

/** Map popup for one business (rendered into a MapLibre popup by BusinessMap). */
const props = defineProps<{ row: LeadRow; onOpen: () => void }>()
const b = computed(() => props.row.lead.business)
const blurb = computed(() => (b.value.description || props.row.lead.qualification_notes || '').trim())
</script>

<template>
  <div class="w-72 text-slate-800" data-testid="business-popup">
    <div class="flex items-start gap-3">
      <div class="min-w-0 flex-1">
        <div class="truncate text-[15px] font-semibold leading-tight">{{ b.name }}</div>
        <div class="mt-0.5 truncate text-xs text-slate-500">{{ b.category || 'Uncategorised' }} · {{ locationLabel(row.lead) }}</div>
      </div>
      <LeadScore :score="row.lead.score" :size="40" />
    </div>
    <a v-if="b.website" :href="b.website" target="_blank" rel="noopener noreferrer"
      class="mt-2 block truncate text-xs font-medium text-violet-700 hover:underline">{{ b.domain || b.website }}</a>
    <p v-else class="mt-2 text-xs text-slate-400">No website listed</p>
    <div v-if="row.problem" class="mt-3 rounded-lg bg-violet-50 px-2.5 py-2 text-xs">
      <div class="text-[10px] font-semibold tracking-wider text-violet-600 uppercase">Identified problem</div>
      <div class="mt-0.5 text-slate-700">{{ problemLabel(row.problem) }}</div>
    </div>
    <p v-if="blurb" class="mt-2 line-clamp-3 text-xs text-slate-600">{{ blurb }}</p>
    <div class="mt-3 flex items-center justify-between gap-2">
      <span class="text-[11px] font-medium text-slate-500">{{ REVIEW_LABEL[row.review] }}</span>
      <button type="button" class="btn-accent px-2.5 py-1 text-xs" @click="onOpen">Open details</button>
    </div>
  </div>
</template>
