<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string | null | undefined }>()
const tone: Record<string, string> = {
  QUEUED: 'bg-slate-100 text-slate-700', RUNNING: 'bg-sky-100 text-sky-800', COMPLETED: 'bg-emerald-100 text-emerald-800',
  FAILED: 'bg-rose-100 text-rose-800', CANCELLED: 'bg-slate-200 text-slate-600', PENDING: 'bg-amber-100 text-amber-800',
  WAITING_FOR_APPROVAL: 'bg-amber-100 text-amber-800', APPROVED: 'bg-emerald-100 text-emerald-800',
  REJECTED: 'bg-rose-100 text-rose-800', CHANGES_REQUESTED: 'bg-orange-100 text-orange-800', DRAFT: 'bg-slate-100 text-slate-700',
  ACTIVE: 'bg-indigo-100 text-indigo-800', PAUSED: 'bg-slate-200 text-slate-700', SENT: 'bg-emerald-100 text-emerald-800',
  SUPPRESSED: 'bg-slate-300 text-slate-700', QUALIFIED: 'bg-emerald-100 text-emerald-800', CONTACTED: 'bg-indigo-100 text-indigo-800',
  DISQUALIFIED: 'bg-slate-200 text-slate-600', NEW: 'bg-sky-100 text-sky-800',
}
const cls = computed(() => tone[props.status ?? ''] ?? 'bg-slate-100 text-slate-700')
</script>

<template>
  <span class="inline-block rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap" :class="cls">
    {{ (status ?? '—').replace(/_/g, ' ') }}
  </span>
</template>
