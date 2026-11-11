<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { Opportunity } from '@/api/types'

/**
 * Agent 1 market map: each opportunity is a node — x = pain severity (1–5), y = score (0–100),
 * size = evidence count, brightness = curation status (shortlisted brightest, dismissed faint).
 * Hover/focus shows details; click/Enter selects (the page scrolls to the card). Overlaps get a
 * deterministic horizontal jitter. Opportunities without score or severity are listed below the chart.
 */
const props = defineProps<{ items: Opportunity[]; selected: string | null }>()
const emit = defineEmits<{ select: [id: string] }>()
const box = ref<HTMLDivElement>()
const width = ref(600)
const H = 260
const PAD = { l: 36, r: 16, t: 16, b: 30 }
const hover = ref<string | null>(null)
let ro: ResizeObserver | undefined
onMounted(() => { ro = new ResizeObserver(([e]) => { width.value = Math.max(260, e!.contentRect.width) }); ro.observe(box.value!) })
onBeforeUnmount(() => ro?.disconnect())

const hash = (s: string) => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7)
const x = (sev: number) => PAD.l + ((sev - 0.5) / 5) * (width.value - PAD.l - PAD.r)
const y = (score: number) => PAD.t + (1 - score / 100) * (H - PAD.t - PAD.b)
const nodes = computed(() => props.items.filter((o) => o.score != null && o.pain_severity != null).map((o) => {
  const jitter = ((hash(o.id) % 1000) / 1000 - 0.5) * 0.5
  return { o, cx: x(o.pain_severity! + jitter), cy: y(o.score!), r: 5 + Math.min(7, o.evidence_ids.length * 1.5) }
}))
const unplotted = computed(() => props.items.length - nodes.value.length)
const hovered = computed(() => nodes.value.find((n) => n.o.id === hover.value) ?? null)
const tone = (status?: string) => (status === 'SHORTLISTED' ? 'hot' : status === 'DISMISSED' ? 'dim' : 'base')
</script>

<template>
  <div ref="box" class="relative">
    <svg :width="width" :height="H" class="block" role="img" :aria-label="`Opportunity map: ${nodes.length} opportunities by pain severity and score`">
      <defs>
        <radialGradient id="opp-glow"><stop offset="0%" stop-color="#fff" stop-opacity="0.5" /><stop offset="100%" stop-color="#fff" stop-opacity="0" /></radialGradient>
      </defs>
      <!-- quadrant of interest: high pain, high score -->
      <rect :x="x(3.5)" :y="PAD.t" :width="width - PAD.r - x(3.5)" :height="y(60) - PAD.t" fill="#fff" fill-opacity="0.025" rx="10" />
      <text :x="width - PAD.r - 8" :y="PAD.t + 14" text-anchor="end" class="fill-muted text-[10px] tracking-wider uppercase">High pain · high score</text>
      <g v-for="v in [0, 25, 50, 75, 100]" :key="`y${v}`">
        <line :x1="PAD.l" :x2="width - PAD.r" :y1="y(v)" :y2="y(v)" stroke="var(--line)" />
        <text :x="PAD.l - 8" :y="y(v) + 3" text-anchor="end" class="fill-muted text-[10px] tabular-nums">{{ v }}</text>
      </g>
      <text v-for="sv in [1, 2, 3, 4, 5]" :key="`x${sv}`" :x="x(sv)" :y="H - 10" text-anchor="middle" class="fill-muted text-[10px]">{{ sv }}</text>
      <text :x="PAD.l" :y="H - 10" class="fill-muted text-[10px]" text-anchor="start" dx="-28">pain</text>
      <g v-for="n in nodes" :key="n.o.id" class="node" :data-tone="tone(n.o.status)" :class="{ on: n.o.id === selected || n.o.id === hover }"
        tabindex="0" role="button" :aria-label="`${n.o.title}: score ${n.o.score}, severity ${n.o.pain_severity}, ${n.o.status}`" :aria-pressed="n.o.id === selected"
        @pointerenter="hover = n.o.id" @pointerleave="hover = null" @focus="hover = n.o.id" @blur="hover = null"
        @click="emit('select', n.o.id)" @keydown.enter.prevent="emit('select', n.o.id)" @keydown.space.prevent="emit('select', n.o.id)">
        <circle v-if="tone(n.o.status) === 'hot' || n.o.id === selected" :cx="n.cx" :cy="n.cy" :r="n.r * 3" fill="url(#opp-glow)" />
        <circle :cx="n.cx" :cy="n.cy" :r="Math.max(12, n.r + 6)" fill="transparent" />
        <circle class="core" :cx="n.cx" :cy="n.cy" :r="n.r" />
      </g>
    </svg>
    <div v-if="hovered" class="glass-pop pointer-events-none absolute z-10 w-60 rounded-[var(--radius-sm)] px-3 py-2 text-xs"
      :style="{ left: `${Math.min(width - 248, Math.max(0, hovered.cx - 120))}px`, top: `${Math.max(0, hovered.cy - 92)}px` }" role="status">
      <div class="font-semibold text-ink">{{ hovered.o.title }}</div>
      <div class="mt-0.5 text-silver">{{ hovered.o.industry || '—' }} · score {{ hovered.o.score }} · pain {{ hovered.o.pain_severity }}/5</div>
      <div class="mt-0.5 text-muted">{{ hovered.o.evidence_ids.length }} source(s) · {{ (hovered.o.status ?? 'NEW').toLowerCase() }}</div>
    </div>
    <p v-if="unplotted" class="mt-1 text-[11px] text-muted">{{ unplotted }} opportunit{{ unplotted === 1 ? 'y' : 'ies' }} without score or severity — listed below only.</p>
    <table class="sr-only">
      <caption>Opportunities by pain severity and score</caption>
      <thead><tr><th>Opportunity</th><th>Score</th><th>Pain severity</th><th>Status</th></tr></thead>
      <tbody><tr v-for="n in nodes" :key="n.o.id"><td>{{ n.o.title }}</td><td>{{ n.o.score }}</td><td>{{ n.o.pain_severity }}</td><td>{{ n.o.status }}</td></tr></tbody>
    </table>
  </div>
</template>

<style scoped>
.node { cursor: pointer; outline: none; }
.node .core { fill: #c4c4ca; stroke: #050505; stroke-width: 2; transition: r var(--dur-2) var(--ease), fill var(--dur-2); }
.node[data-tone='hot'] .core { fill: #fff; filter: drop-shadow(0 0 6px rgb(255 255 255 / 0.9)); }
.node[data-tone='dim'] .core { fill: #4a4a51; }
.node.on .core { stroke: #fff; stroke-width: 2.5; filter: drop-shadow(0 0 8px rgb(255 255 255 / 0.9)); }
.node:focus-visible .core { stroke: #fff; stroke-width: 3; }
</style>
