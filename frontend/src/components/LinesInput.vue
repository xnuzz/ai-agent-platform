<script setup lang="ts">
import { computed } from 'vue'

/** Edits a string[] as one item per line. */
const model = defineModel<string[]>({ default: () => [] })
defineProps<{ rows?: number; placeholder?: string; disabled?: boolean }>()
const text = computed({
  get: () => (model.value ?? []).join('\n'),
  set: (v: string) => { model.value = v.split('\n').map((s) => s.trim()).filter(Boolean) },
})
</script>

<template>
  <textarea v-model.lazy="text" class="input" :rows="rows ?? 4" :placeholder="placeholder ?? 'One item per line'" :disabled="disabled" />
</template>
