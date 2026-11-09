<script setup lang="ts">
defineProps<{ notice?: string | null }>()
</script>

<template>
  <Transition name="pop"><span v-if="notice" class="text-sm text-ok" role="status">{{ notice }}</span></Transition>
</template>
