<script setup lang="ts">
import { ref } from 'vue'
import { api, errorText } from '@/api/client'
import type { OperationsReport, OutreachMessage, Paginated } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import Notice from '@/components/Notice.vue'
import PageHeader from '@/components/PageHeader.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import { agentLabel, fmtDate, taskLabel } from '@/components/format'
import { useAction } from '@/components/useAction'
import { usePolling } from '@/components/usePolling'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const ops = ref<OperationsReport | null>(null)
const sending = ref<OutreachMessage[]>([])
const loadError = ref<string | null>(null)
const { busy, error, notice, run } = useAction()

// Every value below is read from the backend; nothing is computed or assumed client-side except "x min ago".
async function load() {
  try {
    ops.value = await api.get<OperationsReport>('dashboard/operations/')
    sending.value = ops.value.messages_stuck_sending
      ? (await api.get<Paginated<OutreachMessage>>('outreach-messages/', { status: 'SENDING' })).results : []
    loadError.value = null
  } catch (e) {
    loadError.value = `Could not load operations data: ${errorText(e)}`
  }
}
usePolling(load, 10000)

const ago = (v?: string | null) => {
  if (!v) return 'never'
  const m = Math.round((Date.now() - new Date(v).getTime()) / 60000)
  return m < 1 ? 'just now' : m < 120 ? `${m} min ago` : fmtDate(v)
}
const STATE: Record<string, { label: string; cls: string; hint: string }> = {
  RUNNING: { label: 'Running', cls: 'text-ok', hint: 'Working on a task and heartbeating.' },
  IDLE: { label: 'Idle', cls: 'text-silver', hint: 'Worker online, nothing queued.' },
  WAITING: { label: 'Waiting', cls: 'text-warn', hint: 'Worker online, tasks queued but not claimed yet.' },
  STALLED: { label: 'Stalled', cls: 'text-bad', hint: 'A running task stopped heartbeating (lease expired).' },
  OFFLINE: { label: 'Offline', cls: 'text-muted', hint: 'No worker has called the API in the last 10 minutes.' },
}
function resolve(m: OutreachMessage, outcome: 'SENT' | 'FAILED') {
  const note = outcome === 'FAILED' ? (window.prompt('What did the mail provider report? (optional)') ?? '') : ''
  if (outcome === 'SENT' && !window.confirm('Mark as SENT only if the provider log shows it was delivered or accepted. Continue?')) return
  run(async () => { await api.post(`outreach-messages/${m.id}/resolve-sending/`, { outcome, note }); await load() }, `Message marked ${outcome}.`)
}
</script>

<template>
  <PageHeader title="Operations" subtitle="Live agent health from tasks, leases, heartbeats and worker activity. Refreshes every 10 s." />
  <ErrorBanner :message="loadError" />
  <ErrorBanner :message="error" />

  <section v-if="ops?.alerts.length" class="card mb-4" aria-labelledby="alerts-h">
    <h2 id="alerts-h" class="section-title mb-3">Alerts</h2>
    <ul class="space-y-2">
      <li v-for="(a, i) in ops.alerts" :key="i" class="flex gap-2 text-sm" :class="a.level === 'critical' ? 'text-bad' : 'text-warn'">
        <span class="chip shrink-0 uppercase">{{ a.level }}</span><span>{{ a.message }}</span>
      </li>
    </ul>
  </section>
  <p v-else-if="ops" class="mb-4 text-sm text-silver" role="status">No alerts.</p>

  <div v-if="ops" class="grid gap-4 lg:grid-cols-2">
    <section v-for="a in ops.agents" :key="a.agent" class="card" :aria-label="agentLabel(a.agent)">
      <div class="mb-3 flex items-baseline justify-between gap-2">
        <h2 class="section-title">{{ agentLabel(a.agent) }}</h2>
        <span class="text-sm font-medium" :class="STATE[a.state]?.cls" :title="STATE[a.state]?.hint">{{ STATE[a.state]?.label ?? a.state }}</span>
      </div>
      <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        <div><dt class="text-xs text-muted">Worker last seen</dt><dd class="text-ink">{{ ago(a.worker_last_seen_at) }}</dd></div>
        <div><dt class="text-xs text-muted">Last heartbeat</dt><dd class="text-ink">{{ ago(a.last_heartbeat_at) }}</dd></div>
        <div><dt class="text-xs text-muted">Last successful run</dt><dd class="text-ink">{{ ago(a.last_success_at) }}</dd></div>
        <div><dt class="text-xs text-muted">Queued</dt><dd class="text-ink tabular-nums">{{ a.queued }}<span v-if="a.oldest_queued_at" class="text-xs text-silver"> · oldest {{ ago(a.oldest_queued_at) }}</span></dd></div>
        <div><dt class="text-xs text-muted">Stuck tasks</dt><dd class="tabular-nums" :class="a.stuck ? 'text-bad' : 'text-ink'">{{ a.stuck }}</dd></div>
        <div><dt class="text-xs text-muted">Failed (24 h)</dt><dd class="tabular-nums" :class="a.failed_24h ? 'text-warn' : 'text-ink'">{{ a.failed_24h }}</dd></div>
        <div><dt class="text-xs text-muted">Retries (24 h)</dt><dd class="text-ink tabular-nums">{{ a.retries_24h }}</dd></div>
        <div><dt class="text-xs text-muted">Businesses found</dt><dd class="text-ink tabular-nums">{{ a.businesses }}</dd></div>
        <div><dt class="text-xs text-muted">Leads · qualified</dt><dd class="text-ink tabular-nums">{{ a.leads }} · {{ a.qualified_leads }}</dd></div>
      </dl>

      <div class="mt-4">
        <h3 class="mb-2 text-xs font-medium text-silver">Current task</h3>
        <p v-if="!a.current_tasks.length" class="text-sm text-muted">None.</p>
        <RouterLink v-for="t in a.current_tasks" :key="t.id" :to="`/tasks/${t.id}`" class="lift mb-2 block rounded-[var(--radius)] border border-line bg-white/[0.02] p-3">
          <div class="flex justify-between gap-2 text-sm"><span class="text-ink">{{ taskLabel(t.task_type) }} · attempt {{ t.attempt }}</span><span class="text-silver tabular-nums">{{ t.progress }}%</span></div>
          <div class="mt-0.5 mb-2 truncate text-xs text-silver">{{ (t.stage || 'starting').replace(/_/g, ' ').toLowerCase() }} {{ t.progress_message }} · heartbeat {{ ago(t.heartbeat_at) }}</div>
          <ProgressBar :value="t.progress" />
        </RouterLink>
      </div>

      <div v-if="a.recent_errors.length" class="mt-4">
        <h3 class="mb-2 text-xs font-medium text-silver">Recent errors (24 h)</h3>
        <ul class="space-y-1 text-xs">
          <li v-for="e in a.recent_errors" :key="e.task_id + e.at">
            <RouterLink :to="`/tasks/${e.task_id}`" class="text-soft hover:text-ink">{{ ago(e.at) }} · {{ e.status }} · <span class="font-mono">{{ e.code || 'error' }}</span></RouterLink>
            <span class="text-muted"> {{ e.message }}</span>
          </li>
        </ul>
      </div>
    </section>
  </div>
  <div v-else-if="!loadError" class="grid gap-4 lg:grid-cols-2"><div v-for="i in 2" :key="i" class="skeleton h-64" /></div>

  <section v-if="sending.length" class="card mt-4" aria-labelledby="sending-h">
    <div class="mb-3 flex items-center justify-between gap-2">
      <h2 id="sending-h" class="section-title">Messages stuck in SENDING</h2><Notice :notice="notice" />
    </div>
    <p class="mb-3 text-xs text-silver">The worker stopped mid-send. Outreach is at-most-once: check the mail provider log, then record what happened. Nothing is resent automatically.</p>
    <table class="table">
      <thead><tr><th>Recipient</th><th>Subject</th><th>Since</th><th /></tr></thead>
      <tbody>
        <tr v-for="m in sending" :key="m.id">
          <td class="text-sm">{{ m.to_email }}</td><td class="text-sm">{{ m.subject }}</td><td class="text-xs text-silver">{{ ago(m.updated_at) }}</td>
          <td class="whitespace-nowrap text-right">
            <template v-if="auth.isAdmin()">
              <button class="btn-secondary mr-2" :disabled="busy" @click="resolve(m, 'SENT')">Mark sent</button>
              <button class="btn-secondary" :disabled="busy" @click="resolve(m, 'FAILED')">Mark failed</button>
            </template>
            <span v-else class="text-xs text-muted">Admin required</span>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
