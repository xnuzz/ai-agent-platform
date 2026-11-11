<script setup lang="ts">
defineProps<{ value: number }>()
</script>

<template>
  <div class="track" role="progressbar" :aria-valuenow="value" aria-valuemin="0" aria-valuemax="100">
    <div class="fill" :class="{ moving: value > 0 && value < 100 }" :style="{ width: `${value}%` }" />
  </div>
</template>

<style scoped>
.track { height: 4px; width: 100%; overflow: hidden; border-radius: 9999px; background: var(--viz-track); }
.fill { position: relative; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #a1a1aa, #fff); box-shadow: 0 0 10px rgb(255 255 255 / 0.45); transition: width 0.7s var(--ease); }
.fill.moving::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgb(255 255 255 / 0.7), transparent); animation: sheen 1.8s ease-in-out infinite; }
@keyframes sheen { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
</style>
