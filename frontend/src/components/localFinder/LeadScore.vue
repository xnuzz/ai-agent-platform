<script setup lang="ts">
import { computed } from 'vue'
import { potentialOf } from '@/features/localFinder/model'

/** Circular lead-quality score (0–100). Brightness = potential tier (viz ramp); the number is always printed. */
const props = withDefaults(defineProps<{ score: number | null | undefined; size?: number }>(), { size: 40 })
const STROKE = 3
const r = computed(() => props.size / 2 - STROKE)
const circ = computed(() => 2 * Math.PI * r.value)
const value = computed(() => Math.max(0, Math.min(100, props.score ?? 0)))
const potential = computed(() => potentialOf(props.score))
const tone = computed(() => ({ high: 'var(--viz-1)', medium: 'var(--viz-2)', low: 'var(--viz-3)', unscored: 'var(--viz-3)' })[potential.value])
</script>

<template>
  <div class="relative inline-grid shrink-0 place-items-center" :style="{ width: `${size}px`, height: `${size}px` }"
    role="img" :aria-label="score == null ? 'Not scored' : `Lead score ${score} of 100`">
    <svg :width="size" :height="size" class="-rotate-90" :class="{ glow: potential === 'high' }" aria-hidden="true">
      <circle :cx="size / 2" :cy="size / 2" :r="r" fill="none" stroke="var(--viz-track)" :stroke-width="STROKE" />
      <circle :cx="size / 2" :cy="size / 2" :r="r" fill="none" :stroke="tone" :stroke-width="STROKE" stroke-linecap="round"
        :stroke-dasharray="circ" :stroke-dashoffset="circ * (1 - value / 100)" class="transition-[stroke-dashoffset] duration-700" />
    </svg>
    <span class="absolute font-semibold text-ink tabular-nums" :style="{ fontSize: `${Math.round(size * 0.3)}px` }">{{ score ?? '–' }}</span>
  </div>
</template>

<style scoped>
.glow { filter: drop-shadow(0 0 4px rgb(255 255 255 / 0.55)); }
</style>
