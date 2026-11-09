<script setup lang="ts">
import { computed, ref } from 'vue'
import { localFinderApi as api } from '@/api/localFinder'
import { fmtDate } from '@/components/format'
import { useAction } from '@/components/useAction'
import { countryName, isUnclaimed, taskInput, type AgentState } from '@/features/localFinder/model'
import { useAuthStore } from '@/stores/auth'
import { useLocalFinderStore } from '@/stores/localFinder'

const store = useLocalFinderStore()
const auth = useAuthStore()
const { busy, error, run } = useAction()

const task = computed(() => store.activeTask ?? store.currentTask)
const loc = computed(() => taskInput(task.value)?.location)
const progress = computed(() => (task.value?.status === 'COMPLETED' ? 100 : task.value?.progress ?? 0))
const STATE: Record<AgentState, { label: string; cls: string; dot: string }> = {
  IDLE: { label: 'Idle', cls: 'bg-slate-100 text-slate-600', dot: 'bg-slate-400' },
  WAITING: { label: 'Waiting for agent', cls: 'bg-amber-50 text-amber-700', dot: 'bg-amber-500' },
  SCANNING: { label: 'Scanning', cls: 'bg-violet-100 text-violet-700', dot: 'bg-violet-500 lbf-pulse' },
  UNRESPONSIVE: { label: 'Agent not responding', cls: 'bg-amber-50 text-amber-700', dot: 'bg-amber-500' },
  COMPLETED: { label: 'Completed', cls: 'bg-emerald-50 text-emerald-700', dot: 'bg-emerald-500' },
  FAILED: { label: 'Failed', cls: 'bg-rose-50 text-rose-700', dot: 'bg-rose-500' },
  STOPPED: { label: 'Stopped', cls: 'bg-slate-100 text-slate-600', dot: 'bg-slate-400' },
}
const state = computed(() => STATE[store.agentState])
const failure = computed(() => (task.value?.status === 'FAILED' ? (task.value.error ?? {}) as { code?: string; message?: string } : null))
const unclaimed = computed(() => isUnclaimed(task.value, store.now))
const canStop = computed(() => auth.canWrite() && !store.demo && (task.value?.status === 'QUEUED' || task.value?.status === 'RUNNING') && !task.value.cancel_requested)
const ringR = 26
const ringC = 2 * Math.PI * ringR

// Two-step stop (no native dialog): the first click arms the button for a few seconds.
const armed = ref(false)
let disarm: number | undefined
function stop() {
  if (!armed.value) {
    armed.value = true
    disarm = window.setTimeout(() => { armed.value = false }, 4000)
    return
  }
  window.clearTimeout(disarm)
  armed.value = false
  void run(async () => { if (task.value) { await api.cancelTask(task.value.id); store.syncNow() } })
}
const retry = () => run(async () => { if (task.value) { await api.retryTask(task.value.id); store.syncNow() } })
</script>

<template>
  <section class="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm" aria-labelledby="agent-status-h">
    <div class="flex items-center justify-between gap-2">
      <h2 id="agent-status-h" class="text-sm font-semibold text-slate-900">Agent 2 · Research</h2>
      <span class="flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase" :class="state.cls" data-testid="agent-state">
        <span class="h-1.5 w-1.5 rounded-full" :class="state.dot" />{{ state.label }}
      </span>
    </div>

    <div class="mt-3 flex items-center gap-4">
      <div class="relative h-16 w-16 shrink-0" role="img" :aria-label="`Research progress ${progress}%`">
        <svg viewBox="0 0 64 64" class="h-16 w-16 -rotate-90" aria-hidden="true">
          <circle cx="32" cy="32" :r="ringR" fill="none" stroke="#f1f0fb" stroke-width="6" />
          <circle cx="32" cy="32" :r="ringR" fill="none" stroke="#7c3aed" stroke-width="6" stroke-linecap="round" :stroke-dasharray="ringC"
            :stroke-dashoffset="ringC * (1 - progress / 100)" class="transition-[stroke-dashoffset] duration-700" />
        </svg>
        <span class="absolute inset-0 grid place-items-center text-sm font-semibold text-slate-800" data-testid="progress-pct">{{ progress }}%</span>
      </div>
      <dl class="min-w-0 flex-1 space-y-1 text-xs">
        <div class="flex justify-between gap-2"><dt class="text-slate-500">Country</dt><dd class="truncate font-medium text-slate-800">{{ loc ? countryName(loc.country_code) : '—' }}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-slate-500">City / region</dt><dd class="truncate font-medium text-slate-800">{{ loc ? [loc.city, loc.region].filter(Boolean).join(', ') : '—' }}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-slate-500">Radius</dt><dd class="font-medium text-slate-800">{{ loc ? `${loc.radius_km ?? 10} km` : '—' }}</dd></div>
      </dl>
    </div>

    <div class="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-xs">
      <div class="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">Current task</div>
      <p class="mt-0.5 line-clamp-2 text-slate-700" data-testid="current-task">
        <template v-if="!task">No research yet.</template>
        <template v-else-if="task.status === 'QUEUED'">Queued {{ fmtDate(task.created_at) }} — waiting for an Agent 2 worker to claim it.</template>
        <template v-else>{{ (task.stage || task.status).replace(/_/g, ' ').toLowerCase() }}<template v-if="task.progress_message"> · {{ task.progress_message }}</template></template>
      </p>
      <div class="mt-2 h-1 overflow-hidden rounded-full bg-slate-200"><div class="h-full rounded-full bg-violet-500 transition-all duration-700" :style="{ width: `${progress}%` }" /></div>
    </div>

    <p v-if="unclaimed" class="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-800" role="status">No Agent 2 worker has claimed this task yet. Check that the <code>agent2</code> service is running.</p>
    <p v-else-if="store.agentState === 'UNRESPONSIVE'" class="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-800" role="status">No heartbeat since {{ fmtDate(task?.heartbeat_at) }}. The lease expires automatically and the task is re-queued or failed.</p>
    <p v-if="failure" class="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-[11px] text-rose-800" role="alert">{{ failure.code }}: {{ failure.message || 'The agent reported a failure.' }}</p>
    <p v-if="task?.cancel_requested && task.status === 'RUNNING'" class="mt-2 text-[11px] text-slate-500">Stop requested — the agent stops at its next checkpoint.</p>
    <p v-if="error" class="mt-2 text-[11px] text-rose-700" role="alert">{{ error }}</p>

    <button type="button" class="btn-accent mt-3 w-full justify-center" :disabled="!auth.canWrite() || store.demo" @click="store.configOpen = true">
      <svg viewBox="0 0 20 20" class="h-4 w-4" fill="currentColor" aria-hidden="true"><path d="M10 3a1 1 0 0 1 1 1v5h5a1 1 0 1 1 0 2h-5v5a1 1 0 1 1-2 0v-5H4a1 1 0 1 1 0-2h5V4a1 1 0 0 1 1-1Z" /></svg>New research
    </button>
    <div class="mt-2 grid grid-cols-3 gap-2">
      <button v-if="task?.status === 'FAILED'" type="button" class="btn-secondary justify-center px-2 text-xs" :disabled="busy || !auth.canWrite() || store.demo" @click="retry">Retry</button>
      <button v-else type="button" class="justify-center px-2 text-xs" :class="armed ? 'btn-danger' : 'btn-secondary'" :disabled="busy || !canStop" @click="stop">
        <svg viewBox="0 0 20 20" class="h-3 w-3" fill="currentColor" aria-hidden="true"><rect x="5" y="5" width="10" height="10" rx="2" /></svg>{{ armed ? 'Confirm' : 'Stop' }}
      </button>
      <button type="button" class="btn-secondary justify-center px-2 text-xs" disabled aria-describedby="pause-note">Pause</button>
      <button type="button" class="btn-secondary justify-center px-2 text-xs" disabled aria-describedby="pause-note">Resume</button>
    </div>
    <p id="pause-note" class="mt-1.5 text-[10px] leading-snug text-slate-400">Pause/resume needs platform support (requested). Stop keeps submitted results.</p>
  </section>
</template>

<style scoped>
.lbf-pulse { animation: pulse 1.4s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .3; } }
@media (prefers-reduced-motion: reduce) { .lbf-pulse { animation: none; } }
</style>
