<script setup lang="ts">
import { computed, ref } from 'vue'
import { monoShade } from './palette'

/**
 * Part-to-whole donut on the monochrome ramp (white → grey), 2px surface gaps, total in the centre,
 * legend with values (identity never relies on shade alone) and an sr-only table.
 */
const props = defineProps<{ items: { label: string; value: number }[]; title: string }>()
const R = 42, STROKE = 10, C = 2 * Math.PI * R, GAP = 2
const hover = ref<number | null>(null)
const total = computed(() => props.items.reduce((a, b) => a + b.value, 0))
const segs = computed(() => {
  let acc = 0
  return props.items.map((it, i) => {
    const len = total.value ? (it.value / total.value) * C : 0
    const s = { ...it, color: monoShade(i), dash: `${Math.max(0, len - (len > GAP ? GAP : 0))} ${C}`, offset: -acc }
    acc += len
    return s
  })
})
</script>

<template>
  <div class="flex items-center gap-5">
    <svg viewBox="0 0 100 100" class="h-28 w-28 shrink-0 -rotate-90" role="img" :aria-label="`${title}: ${total} total`">
      <circle cx="50" cy="50" :r="R" fill="none" stroke="var(--viz-track)" :stroke-width="STROKE" />
      <circle v-for="(s, i) in segs" :key="s.label" cx="50" cy="50" :r="R" fill="none" :stroke="s.color" :stroke-width="hover === i ? STROKE + 3 : STROKE"
        :stroke-dasharray="s.dash" :stroke-dashoffset="s.offset" class="transition-[stroke-width] duration-200"
        :style="i === 0 ? 'filter: drop-shadow(0 0 4px rgb(255 255 255 / .45))' : ''" @pointerenter="hover = i" @pointerleave="hover = null" />
      <text x="50" y="50" text-anchor="middle" dominant-baseline="central" class="rotate-90 fill-white text-[18px] font-semibold" style="transform-origin: 50px 50px">{{ total }}</text>
    </svg>
    <ul class="min-w-0 flex-1 space-y-1.5 text-xs">
      <li v-for="(s, i) in segs" :key="s.label" class="flex items-center gap-2 rounded-md px-1.5 py-0.5 transition-colors" :class="{ 'bg-white/[0.06]': hover === i }"
        @pointerenter="hover = i" @pointerleave="hover = null">
        <span class="h-2 w-2 shrink-0 rounded-full" :style="{ background: s.color }" />
        <span class="truncate text-silver">{{ s.label }}</span>
        <span class="ml-auto font-medium text-ink tabular-nums">{{ s.value }}</span>
      </li>
      <li v-if="!items.length" class="text-muted">No data yet</li>
    </ul>
    <table class="sr-only"><caption>{{ title }}</caption><tbody><tr v-for="s in segs" :key="s.label"><td>{{ s.label }}</td><td>{{ s.value }}</td></tr></tbody></table>
  </div>
</template>
