<script setup lang="ts">
/**
 * Deep-space backdrop. Cheap by design:
 *  - two canvases (far / near) painted ONCE per resize — no animation loop;
 *  - ~20 twinkling stars are tiny DOM nodes with a CSS opacity animation (compositor only);
 *  - optional slow drift (CSS transform) only where few glass panels sit on top (auth pages),
 *    because a moving backdrop forces backdrop-filter re-blurs every frame.
 * Decorative: aria-hidden, pointer-events none, z-index −1 (paints above the page background, below content).
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

defineProps<{ drift?: boolean }>()
const far = ref<HTMLCanvasElement>()
const near = ref<HTMLCanvasElement>()
let timer: number | undefined

/** Deterministic PRNG so the sky does not reshuffle on every resize. */
function rng(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function paint(canvas: HTMLCanvasElement, seed: number, density: number, cap: number, sizes: [number, number], alpha: [number, number], bright = 0) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const w = canvas.clientWidth, h = canvas.clientHeight
  canvas.width = Math.round(w * dpr)
  canvas.height = Math.round(h * dpr)
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, w, h)
  const rand = rng(seed)
  const n = Math.min(cap, Math.round((w * h) / density))
  for (let i = 0; i < n; i++) {
    const x = rand() * w, y = rand() * h
    // skew towards tiny + dim: most stars are barely there, a few are clearly visible
    const k = rand() ** 2.4
    const r = sizes[0] + (sizes[1] - sizes[0]) * k
    ctx.globalAlpha = alpha[0] + (alpha[1] - alpha[0]) * (0.35 * rand() + 0.65 * k)
    ctx.fillStyle = '#fff'
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fill()
  }
  for (let i = 0; i < bright; i++) {
    const x = rand() * w, y = rand() * h, r = 1 + rand() * 0.6
    const g = ctx.createRadialGradient(x, y, 0, x, y, r * 6)
    g.addColorStop(0, 'rgba(255,255,255,0.55)')
    g.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.globalAlpha = 1
    ctx.fillStyle = g
    ctx.fillRect(x - r * 6, y - r * 6, r * 12, r * 12)
    ctx.fillStyle = '#fff'
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fill()
  }
}

function draw() {
  if (far.value) paint(far.value, 7, 2600, 650, [0.25, 0.8], [0.15, 0.6])
  if (near.value) paint(near.value, 99, 16000, 120, [0.5, 1.2], [0.35, 0.9], 6)
}
const onResize = () => { window.clearTimeout(timer); timer = window.setTimeout(draw, 150) }

// Twinkling stars: fixed pseudo-random positions/timings (percent of the viewport).
const twinkles = Array.from({ length: 20 }, (_, i) => {
  const r = rng(1000 + i)
  return { left: `${(r() * 100).toFixed(2)}%`, top: `${(r() * 100).toFixed(2)}%`, size: r() > 0.75 ? 2 : 1.5, dur: `${(4 + r() * 5).toFixed(1)}s`, delay: `${(-r() * 8).toFixed(1)}s` }
})

onMounted(() => { draw(); window.addEventListener('resize', onResize) })
onBeforeUnmount(() => { window.removeEventListener('resize', onResize); window.clearTimeout(timer) })
</script>

<template>
  <div class="starfield" :class="{ 'starfield-drift': drift }" aria-hidden="true">
    <div class="nebula" />
    <canvas ref="far" class="layer layer-far" />
    <canvas ref="near" class="layer layer-near" />
    <span v-for="(t, i) in twinkles" :key="i" class="twinkle"
      :style="{ left: t.left, top: t.top, width: `${t.size}px`, height: `${t.size}px`, animationDuration: t.dur, animationDelay: t.delay }" />
  </div>
</template>

<style scoped>
.starfield { position: fixed; inset: 0; z-index: -1; overflow: hidden; pointer-events: none; background: radial-gradient(ellipse at 50% -10%, #111114 0%, var(--bg) 55%); }
.nebula {
  position: absolute; inset: -20%;
  background:
    radial-gradient(40% 30% at 78% 18%, rgb(255 255 255 / 0.035), transparent 70%),
    radial-gradient(35% 25% at 12% 80%, rgb(255 255 255 / 0.025), transparent 70%);
}
.layer { position: absolute; inset: -4%; width: 108%; height: 108%; }
.twinkle { position: absolute; border-radius: 9999px; background: #fff; box-shadow: 0 0 6px 1px rgb(255 255 255 / 0.5); opacity: 0.25; animation: twinkle ease-in-out infinite; will-change: opacity; }
.starfield-drift .layer-far { animation: drift-far 240s linear infinite alternate; }
.starfield-drift .layer-near { animation: drift-near 160s linear infinite alternate; }
@keyframes twinkle { 0%, 100% { opacity: 0.15; } 50% { opacity: 0.95; } }
@keyframes drift-far { to { transform: translate3d(-2%, -1.5%, 0); } }
@keyframes drift-near { to { transform: translate3d(-3%, -2.5%, 0); } }
@media (prefers-reduced-motion: reduce) { .twinkle, .layer { animation: none !important; } }
</style>
