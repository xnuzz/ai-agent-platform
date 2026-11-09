<script setup lang="ts">
import AppIcon, { type IconName } from './AppIcon.vue'

/** KPI tile: label · value · one line of context. Optional link makes the whole tile navigable. */
defineProps<{ label: string; value: number | string; sub?: string; icon?: IconName; to?: string }>()
</script>

<template>
  <component :is="to ? 'RouterLink' : 'div'" :to="to" class="card lift group block p-4">
    <div class="flex items-center justify-between gap-2">
      <span class="kicker">{{ label }}</span>
      <AppIcon v-if="icon" :name="icon" :size="16" class="text-muted transition-colors group-hover:text-ink" />
    </div>
    <div class="mt-3 text-[32px] leading-none font-semibold tracking-tight text-ink">{{ value }}</div>
    <div v-if="sub" class="mt-2 truncate text-xs text-silver">{{ sub }}</div>
  </component>
</template>
