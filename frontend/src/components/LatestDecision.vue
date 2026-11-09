<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/api/client'
import type { Approval, Paginated } from '@/api/types'
import StatusBadge from './StatusBadge.vue'
import { fmtDate } from './format'

/** Shows the most recent approval for a target, so editors see why changes were requested. */
const props = defineProps<{ targetId: string; refreshKey?: unknown }>()
const latest = ref<Approval | null>(null)
let seq = 0
watch(() => `${props.targetId}:${String(props.refreshKey ?? "")}`, async () => {
  const mine = ++seq
  const r = await api.get<Paginated<Approval>>('approvals/', { target_id: props.targetId, page_size: 1, ordering: '-created_at' })
  if (mine === seq) latest.value = r.results[0] ?? null  // ignore out-of-order responses
}, { immediate: true })
</script>

<template>
  <div v-if="latest" class="rounded-lg border p-3 text-sm"
    :class="latest.status === 'CHANGES_REQUESTED' ? 'border-orange-200 bg-orange-50' : latest.status === 'REJECTED' ? 'border-rose-200 bg-rose-50' : 'border-slate-200 bg-slate-50'">
    <div class="flex items-center gap-2"><span class="font-medium">Latest review</span><StatusBadge :status="latest.status" />
      <span class="text-xs text-slate-500">{{ latest.decided_by_email ?? 'awaiting decision' }} · {{ fmtDate(latest.decided_at ?? latest.created_at) }}</span></div>
    <p v-if="latest.decision_comment" class="mt-1 whitespace-pre-wrap">“{{ latest.decision_comment }}”</p>
  </div>
</template>
