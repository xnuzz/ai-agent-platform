<script setup lang="ts">
import { computed } from 'vue'
import { potentialOf } from '@/features/localFinder/model'

/** Circular lead-quality score (0–100). Colour = potential tier; the number is always printed. */
const props = withDefaults(defineProps<{ score: number | null | undefined; size?: number; dark?: boolean }>(), { size: 40, dark: false })
const STROKE = 3.5
const r = computed(() => props.size / 2 - STROKE)
const circ = computed(() => 2 * Math.PI * r.value)
const value = computed(() => Math.max(0, Math.min(100, props.score ?? 0)))
const tone = computed(() => ({ high: '#7c3aed', medium: '#a78bfa', low: '#cbd5e1', unscored: '#e2e8f0' })[potentialOf(props.score)])
</script>

<template>
  <div class="relative inline-grid shrink-0 place-items-center" :style="{ width: `${size}px`, height: `${size}px` }"
    role="img" :aria-label="score == null ? 'Not scored' : `Lead score ${score} of 100`">
    <svg :width="size" :height="size" class="-rotate-90" aria-hidden="true">
      <circle :cx="size / 2" :cy="size / 2" :r="r" fill="none" :stroke="dark ? '#2a2e40' : '#f1f0fb'" :stroke-width="STROKE" />
      <circle :cx="size / 2" :cy="size / 2" :r="r" fill="none" :stroke="tone" :stroke-width="STROKE" stroke-linecap="round"
        :stroke-dasharray="circ" :stroke-dashoffset="circ * (1 - value / 100)" class="transition-[stroke-dashoffset] duration-500" />
    </svg>
    <span class="absolute font-semibold tabular-nums" :class="dark ? 'text-white' : 'text-slate-800'" :style="{ fontSize: `${Math.round(size * 0.3)}px` }">
      {{ score ?? '–' }}
    </span>
  </div>
</template>
