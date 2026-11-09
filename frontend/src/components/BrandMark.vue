<script setup lang="ts">
import AppIcon from './AppIcon.vue'

/** Platform logo: a luminous silver orb. */
withDefaults(defineProps<{ size?: number }>(), { size: 36 })
</script>

<template>
  <span class="brand grid shrink-0 place-items-center rounded-xl" :style="{ width: `${size}px`, height: `${size}px` }" aria-hidden="true">
    <AppIcon name="spark" :size="Math.round(size * 0.47)" />
  </span>
</template>

<style scoped>
.brand { background: radial-gradient(circle at 30% 25%, #fff, #bdbdc4 45%, #3f3f46); color: #0a0a0a; box-shadow: 0 0 20px -2px rgb(255 255 255 / 0.35); }
</style>
