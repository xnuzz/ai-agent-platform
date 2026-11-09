<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { TimePoint } from '@/features/localFinder/model'

/** Cumulative discoveries over time: 2px line + 10% area wash, crosshair + tooltip, sr-only table. */
const props = defineProps<{ points: TimePoint[] }>()
const box = ref<HTMLDivElement>()
const width = ref(300)
const H = 132
const PAD = { l: 28, r: 10, t: 10, b: 20 }
const hover = ref<number | null>(null)
let ro: ResizeObserver | undefined
onMounted(() => { ro = new ResizeObserver(([e]) => { width.value = Math.max(160, e!.contentRect.width) }); ro.observe(box.value!) })
onBeforeUnmount(() => ro?.disconnect())

const max = computed(() => niceMax(Math.max(1, ...props.points.map((p) => p.cumulative))))
const x = (i: number) => PAD.l + (props.points.length <= 1 ? (width.value - PAD.l - PAD.r) / 2 : (i / (props.points.length - 1)) * (width.value - PAD.l - PAD.r))
const y = (v: number) => PAD.t + (1 - v / max.value) * (H - PAD.t - PAD.b)
const line = computed(() => props.points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.cumulative).toFixed(1)}`).join(''))
const area = computed(() => props.points.length ? `${line.value}L${x(props.points.length - 1).toFixed(1)},${y(0)}L${x(0).toFixed(1)},${y(0)}Z` : '')
const ticks = computed(() => [0, max.value / 2, max.value])
const xLabels = computed(() => {
  const n = props.points.length
  if (!n) return []
  const idx = n <= 2 ? [...Array(n).keys()] : [0, Math.floor((n - 1) / 2), n - 1]
  return idx.map((i) => ({ i, label: props.points[i]!.label, anchor: i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle' }))
})
function niceMax(v: number) {
  const p = 10 ** Math.floor(Math.log10(v))
  return ([1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v) ?? v)
}
function onMove(e: PointerEvent) {
  const n = props.points.length
  if (!n) return
  const rect = (e.currentTarget as SVGElement).getBoundingClientRect()
  const px = e.clientX - rect.left
  const step = n <= 1 ? 1 : (width.value - PAD.l - PAD.r) / (n - 1)
  hover.value = Math.max(0, Math.min(n - 1, Math.round((px - PAD.l) / step)))
}
const hp = computed(() => (hover.value != null ? props.points[hover.value] : null))
</script>

<template>
  <div ref="box" class="relative w-full">
    <svg :width="width" :height="H" class="block touch-none" role="img" :aria-label="`Businesses discovered over time, ${points[points.length - 1]?.cumulative ?? 0} in total`"
      tabindex="0" @pointermove="onMove" @pointerleave="hover = null" @focus="hover = points.length - 1" @blur="hover = null"
      @keydown.left.prevent="hover = Math.max(0, (hover ?? points.length) - 1)" @keydown.right.prevent="hover = Math.min(points.length - 1, (hover ?? -1) + 1)">
      <g v-for="t in ticks" :key="t">
        <line :x1="PAD.l" :x2="width - PAD.r" :y1="y(t)" :y2="y(t)" stroke="#eef0f4" />
        <text :x="PAD.l - 6" :y="y(t) + 3" text-anchor="end" class="fill-slate-400 text-[10px] tabular-nums">{{ Math.round(t) }}</text>
      </g>
      <path :d="area" fill="#7c3aed" fill-opacity="0.1" />
      <path :d="line" fill="none" stroke="#7c3aed" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
      <circle v-if="points.length" :cx="x(points.length - 1)" :cy="y(points[points.length - 1]!.cumulative)" r="4" fill="#7c3aed" stroke="#fff" stroke-width="2" />
      <text v-for="l in xLabels" :key="l.i" :x="x(l.i)" :y="H - 5" :text-anchor="l.anchor" class="fill-slate-400 text-[10px]">{{ l.label }}</text>
      <g v-if="hp && hover != null">
        <line :x1="x(hover)" :x2="x(hover)" :y1="PAD.t" :y2="H - PAD.b" stroke="#c4b5fd" />
        <circle :cx="x(hover)" :cy="y(hp.cumulative)" r="4.5" fill="#7c3aed" stroke="#fff" stroke-width="2" />
      </g>
    </svg>
    <div v-if="hp && hover != null" class="pointer-events-none absolute top-0 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] shadow-lg"
      :style="{ left: `${Math.min(width - 130, Math.max(0, x(hover) - 60))}px` }" role="status">
      <div class="font-semibold text-slate-900 tabular-nums">{{ hp.cumulative }} total</div>
      <div class="text-slate-500">+{{ hp.count }} · {{ hp.label }}</div>
    </div>
    <table class="sr-only">
      <caption>Businesses discovered over time</caption>
      <thead><tr><th>Period</th><th>Discovered</th><th>Total</th></tr></thead>
      <tbody><tr v-for="p in points" :key="p.t"><td>{{ p.label }}</td><td>{{ p.count }}</td><td>{{ p.cumulative }}</td></tr></tbody>
    </table>
  </div>
</template>
