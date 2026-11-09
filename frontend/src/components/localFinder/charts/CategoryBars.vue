<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CategoryStat } from '@/features/localFinder/model'

/** Qualified opportunities per category: horizontal bars, value at the tip, hover/focus tooltip, sr-only table. */
const props = defineProps<{ stats: CategoryStat[] }>()
const max = computed(() => Math.max(1, ...props.stats.map((s) => s.qualified)))
const hover = ref<number | null>(null)
</script>

<template>
  <div class="relative">
    <ul class="space-y-1.5" aria-hidden="true">
      <li v-for="(s, i) in stats" :key="s.category" class="group flex items-center gap-2 rounded-md text-[11px] outline-none focus-visible:ring-2 focus-visible:ring-white/15"
        tabindex="0" @pointerenter="hover = i" @pointerleave="hover = null" @focus="hover = i" @blur="hover = null">
        <span class="w-24 shrink-0 truncate text-silver" :title="s.category">{{ s.category }}</span>
        <span class="relative h-2.5 min-w-0 flex-1 rounded-r bg-white/[0.03]">
          <span class="absolute inset-y-0 left-0 rounded-r transition-all duration-500" :class="hover === i ? 'bg-white shadow-[0_0_10px_rgb(255_255_255/0.6)]' : 'bg-silver'"
            :style="{ width: `${(s.qualified / max) * 100}%` }" />
        </span>
        <span class="w-6 shrink-0 text-right font-medium text-soft tabular-nums">{{ s.qualified }}</span>
      </li>
    </ul>
    <div v-if="hover != null && stats[hover]" class="pointer-events-none absolute right-0 -top-1 glass-pop rounded-[var(--radius-sm)] px-2.5 py-1.5 text-[11px]" role="status">
      <div class="font-semibold text-ink">{{ stats[hover]!.qualified }} qualified</div>
      <div class="text-silver">{{ stats[hover]!.category }} · {{ stats[hover]!.discovered }} found · {{ stats[hover]!.opportunities }} problems</div>
    </div>
    <table class="sr-only">
      <caption>Qualified opportunities by business category</caption>
      <thead><tr><th>Category</th><th>Qualified</th><th>Discovered</th><th>Problems</th></tr></thead>
      <tbody><tr v-for="s in stats" :key="s.category"><td>{{ s.category }}</td><td>{{ s.qualified }}</td><td>{{ s.discovered }}</td><td>{{ s.opportunities }}</td></tr></tbody>
    </table>
  </div>
</template>
