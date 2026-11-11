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
  <div class="w-72 text-ink" data-testid="business-popup">
    <div class="flex items-start gap-3">
      <div class="min-w-0 flex-1">
        <div class="truncate text-[15px] font-semibold leading-tight">{{ b.name }}</div>
        <div class="mt-0.5 truncate text-xs text-silver">{{ b.category || 'Uncategorised' }} · {{ locationLabel(row.lead) }}</div>
      </div>
      <LeadScore :score="row.lead.score" :size="40" />
    </div>
    <a v-if="b.website" :href="b.website" target="_blank" rel="noopener noreferrer"
      class="mt-2 block truncate text-xs font-medium text-ink hover:underline">{{ b.domain || b.website }}</a>
    <p v-else class="mt-2 text-xs text-muted">No website listed</p>
    <div v-if="row.problem" class="mt-3 rounded-lg bg-white/[0.05] px-2.5 py-2 text-xs">
      <div class="text-[10px] font-semibold tracking-wider text-ink uppercase">Identified problem</div>
      <div class="mt-0.5 text-soft">{{ problemLabel(row.problem) }}</div>
    </div>
    <p v-if="blurb" class="mt-2 line-clamp-3 text-xs text-silver">{{ blurb }}</p>
    <div class="mt-3 flex items-center justify-between gap-2">
      <span class="text-[11px] font-medium text-silver">{{ REVIEW_LABEL[row.review] }}</span>
      <button type="button" class="btn-accent px-2.5 py-1 text-xs" @click="onOpen">Open details</button>
    </div>
  </div>
</template>
