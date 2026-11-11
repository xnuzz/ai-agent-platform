<script setup lang="ts">
import { computed } from 'vue'

/** Ranked horizontal bars (single series): label · thin luminous bar · value. */
const props = defineProps<{ items: { label: string; value: number }[] }>()
const max = computed(() => Math.max(1, ...props.items.map((i) => i.value)))
</script>

<template>
  <ul class="space-y-3">
    <li v-for="(it, i) in items" :key="it.label" class="text-xs">
      <div class="mb-1.5 flex justify-between gap-2"><span class="truncate text-silver">{{ it.label }}</span><span class="font-medium text-ink tabular-nums">{{ it.value }}</span></div>
      <div class="h-1.5 overflow-hidden rounded-full bg-[var(--viz-track)]">
        <div class="h-full rounded-full transition-[width] duration-700 ease-out-soft" :class="i === 0 ? 'bg-white shadow-[0_0_10px_rgb(255_255_255/0.5)]' : 'bg-silver'"
          :style="{ width: `${(it.value / max) * 100}%` }" />
      </div>
    </li>
    <li v-if="!items.length" class="text-xs text-muted">No data yet</li>
  </ul>
</template>
