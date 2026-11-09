<script setup lang="ts">
defineProps<{ value: number }>()
</script>

<template>
  <div class="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
    <div class="h-full rounded-full bg-indigo-500 transition-all" :style="{ width: `${value}%` }" />
  </div>
</template>
