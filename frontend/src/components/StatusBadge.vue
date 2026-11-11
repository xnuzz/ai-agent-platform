<script setup lang="ts">
import { computed } from 'vue'

/**
 * Minimal status pill: neutral glass by default; colour only where it communicates state
 * (ok / warning / error), a white pulsing dot for work in progress. The text is always the status.
 */
const props = defineProps<{ status: string | null | undefined }>()
const TONE: Record<string, 'ok' | 'warn' | 'bad' | 'live'> = {
  COMPLETED: 'ok', APPROVED: 'ok', SENT: 'ok', QUALIFIED: 'ok', WON: 'ok',
  PENDING: 'warn', WAITING_FOR_APPROVAL: 'warn', CHANGES_REQUESTED: 'warn', SENDING: 'warn', MEDIUM: 'warn',
  FAILED: 'bad', REJECTED: 'bad', LOST: 'bad', HIGH: 'bad',
  RUNNING: 'live', ACTIVE: 'live',
}
const tone = computed(() => TONE[props.status ?? ''] ?? 'neutral')
</script>

<template>
  <span class="badge" :data-tone="tone"><span class="dot" aria-hidden="true" />{{ (status ?? '—').replace(/_/g, ' ') }}</span>
</template>

<style scoped>
.badge {
  display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; border-radius: 9999px;
  border: 1px solid var(--line); background: rgb(255 255 255 / 0.04); padding: 1px 8px 1px 7px;
  font-size: 11px; font-weight: 500; letter-spacing: 0.02em; line-height: 18px; color: var(--soft);
}
.dot { width: 6px; height: 6px; border-radius: 9999px; background: var(--muted); }
.badge[data-tone='ok'] { color: var(--ok); border-color: color-mix(in srgb, var(--ok) 25%, transparent); background: color-mix(in srgb, var(--ok) 8%, transparent); }
.badge[data-tone='ok'] .dot { background: var(--ok); }
.badge[data-tone='warn'] { color: var(--warn); border-color: color-mix(in srgb, var(--warn) 25%, transparent); background: color-mix(in srgb, var(--warn) 8%, transparent); }
.badge[data-tone='warn'] .dot { background: var(--warn); }
.badge[data-tone='bad'] { color: var(--bad); border-color: color-mix(in srgb, var(--bad) 25%, transparent); background: color-mix(in srgb, var(--bad) 8%, transparent); }
.badge[data-tone='bad'] .dot { background: var(--bad); }
.badge[data-tone='live'] { color: var(--ink); border-color: var(--line-strong); }
.badge[data-tone='live'] .dot { background: #fff; box-shadow: 0 0 8px 1px rgb(255 255 255 / 0.8); animation: live 1.6s ease-in-out infinite; }
@keyframes live { 50% { opacity: 0.35; } }
</style>
