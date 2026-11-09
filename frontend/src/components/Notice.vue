<script setup lang="ts">
defineProps<{ notice?: string | null }>()
</script>

<template>
  <span v-if="notice" class="text-sm text-emerald-700">{{ notice }}</span>
</template>
