<script setup lang="ts">
import { ref, watch } from 'vue'
import { api, errorText } from '@/api/client'
import type { Approval, ApprovalDecision, Paginated } from '@/api/types'
import StatusBadge from './StatusBadge.vue'
import { fmtDate } from './format'

/**
 * Shows the most recent approval for a target, so editors see why changes were requested.
 * While that approval is PENDING and `canDecide` is set, reviewers can decide it in place
 * (same endpoint as the Approval center; the backend still enforces role + stale-content checks).
 */
const props = defineProps<{ targetId: string; refreshKey?: unknown; canDecide?: boolean; approveHint?: string }>()
const emit = defineEmits<{ decided: [Approval] }>()
const latest = ref<Approval | null>(null)
const comment = ref('')
const busy = ref(false)
const error = ref<string | null>(null)
let seq = 0

watch(() => `${props.targetId}:${String(props.refreshKey ?? '')}`, async () => {
  const mine = ++seq
  error.value = null
  const r = await api.get<Paginated<Approval>>('approvals/', { target_id: props.targetId, page_size: 1, ordering: '-created_at' })
  if (mine === seq) latest.value = r.results[0] ?? null  // ignore out-of-order responses
}, { immediate: true })

async function decide(decision: ApprovalDecision) {
  if (!latest.value) return
  busy.value = true
  error.value = null
  try {
    const decided = await api.post<Approval>(`approvals/${latest.value.id}/decide/`, { decision, comment: comment.value.trim() })
    seq++  // a list fetch still in flight would be older than this response
    latest.value = decided
    comment.value = ''
    emit('decided', decided)
  } catch (e) { error.value = errorText(e) } finally { busy.value = false }
}
</script>

<template>
  <section v-if="latest" aria-label="Latest review" class="rounded-lg border p-3 text-sm"
    :class="latest.status === 'CHANGES_REQUESTED' ? 'border-warn/30 bg-warn/10' : latest.status === 'REJECTED' ? 'border-bad/30 bg-bad/10' : 'border-line bg-white/[0.03]'">
    <div class="flex items-center gap-2"><span class="font-medium">Latest review</span><StatusBadge :status="latest.status" />
      <span class="text-xs text-silver">{{ latest.decided_by_email ?? 'awaiting decision' }} · {{ fmtDate(latest.decided_at ?? latest.created_at) }}</span></div>
    <p v-if="latest.summary && latest.status === 'PENDING'" class="mt-1 whitespace-pre-wrap text-soft">{{ latest.summary }}</p>
    <p v-if="latest.decision_comment" class="mt-1 whitespace-pre-wrap">“{{ latest.decision_comment }}”</p>
    <div v-if="canDecide && latest.status === 'PENDING'" class="mt-3 space-y-2 border-t border-line pt-3">
      <textarea v-model="comment" class="input" rows="2" maxlength="5000" placeholder="Comment (optional)" aria-label="Review comment" />
      <div class="flex flex-wrap items-center gap-2">
        <button type="button" class="btn-primary" :disabled="busy" @click="decide('APPROVED')">Approve</button>
        <button type="button" class="btn-secondary" :disabled="busy" @click="decide('CHANGES_REQUESTED')">Request changes</button>
        <button type="button" class="btn-danger" :disabled="busy" @click="decide('REJECTED')">Reject</button>
        <span v-if="approveHint" class="text-xs text-silver">{{ approveHint }}</span>
      </div>
      <p v-if="error" role="alert" class="text-bad">{{ error }}</p>
    </div>
  </section>
</template>
