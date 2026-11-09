<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <div class="mb-7 flex flex-wrap items-end justify-between gap-3">
    <div class="min-w-0">
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="subtitle" class="mt-1.5 max-w-2xl text-sm text-silver">{{ subtitle }}</p>
    </div>
    <div class="flex flex-wrap gap-2"><slot /></div>
  </div>
</template>
