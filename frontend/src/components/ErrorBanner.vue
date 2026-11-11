<script setup lang="ts">
defineProps<{ message: string | null }>()
</script>

<template>
  <Transition name="pop">
    <div v-if="message" class="mb-4 rounded-[var(--radius)] border border-bad/30 bg-bad/10 px-4 py-2.5 text-sm text-bad" role="alert">{{ message }}</div>
  </Transition>
</template>
