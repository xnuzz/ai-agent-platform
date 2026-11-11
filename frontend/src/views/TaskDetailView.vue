<script setup lang="ts">
import { ref } from 'vue'
import { api, errorText } from '@/api/client'
import type { ResearchTaskDetail } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import PageHeader from '@/components/PageHeader.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel, fmtDate, taskLabel } from '@/components/format'
import { usePolling } from '@/components/usePolling'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ id: string }>()
const auth = useAuthStore()
const task = ref<ResearchTaskDetail | null>(null)
const error = ref<string | null>(null)
usePolling(async () => { task.value = await api.get<ResearchTaskDetail>(`research-tasks/${props.id}/`) }, 3000)

async function act(action: 'cancel' | 'retry') {
  try { await api.post(`research-tasks/${props.id}/${action}/`); task.value = await api.get(`research-tasks/${props.id}/`) }
  catch (e) { error.value = errorText(e) }
}
</script>

<template>
  <template v-if="task">
    <PageHeader :title="taskLabel(task.task_type)" :subtitle="`${agentLabel(task.agent)} · created ${fmtDate(task.created_at)}`">
      <button v-if="auth.canWrite() && ['QUEUED', 'RUNNING'].includes(task.status ?? '') && !task.cancel_requested" class="btn-danger" @click="act('cancel')">Cancel</button>
      <button v-if="auth.canWrite() && task.status === 'FAILED'" class="btn-secondary" @click="act('retry')">Retry</button>
    </PageHeader>
    <ErrorBanner :message="error" />
    <div class="grid gap-4 lg:grid-cols-3">
      <section class="card lg:col-span-2">
        <div class="mb-3 flex items-center gap-3"><StatusBadge :status="task.status" /><span v-if="task.cancel_requested" class="text-xs text-bad">cancel requested</span></div>
        <ProgressBar :value="task.progress ?? 0" />
        <p class="mt-2 text-sm text-silver">{{ task.stage }} {{ task.progress_message }}</p>
        <div v-if="task.error && Object.keys(task.error).length" class="mt-4 rounded-lg bg-bad/10 p-3 text-sm text-bad">
          {{ (task.error as any).code }}: {{ (task.error as any).message }}
        </div>
        <h3 class="mt-6 mb-2 text-sm font-medium">Input</h3>
        <pre class="overflow-x-auto rounded-lg bg-white/[0.03] p-3 text-xs">{{ JSON.stringify(task.input, null, 2) }}</pre>
      </section>
      <section class="card">
        <h3 class="mb-3 text-sm font-medium">Results</h3>
        <dl class="space-y-1 text-sm">
          <div v-for="(n, k) in task.result_counts" :key="k" class="flex justify-between"><dt class="text-silver">{{ String(k).replace('_', ' ') }}</dt><dd class="tabular-nums">{{ n }}</dd></div>
        </dl>
        <div class="mt-4 text-xs text-silver">Attempt {{ task.attempt }} / {{ task.max_attempts }} · heartbeat {{ fmtDate(task.heartbeat_at) }}</div>
        <RouterLink to="/approvals" class="btn-secondary mt-4">Open approval center</RouterLink>
      </section>
    </div>
  </template>
</template>
