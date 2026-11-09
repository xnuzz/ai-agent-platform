<script setup lang="ts">
import { computed, ref } from 'vue'
import { localFinderApi as api } from '@/api/localFinder'
import { fmtDate } from '@/components/format'
import ProgressBar from '@/components/ProgressBar.vue'
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
  IDLE: { label: 'Idle', cls: 'bg-white/[0.06] text-silver', dot: 'bg-muted' },
  WAITING: { label: 'Waiting for agent', cls: 'bg-warn/10 text-warn', dot: 'bg-warn' },
  SCANNING: { label: 'Scanning', cls: 'bg-white/10 text-ink', dot: 'bg-white lbf-pulse' },
  UNRESPONSIVE: { label: 'Agent not responding', cls: 'bg-warn/10 text-warn', dot: 'bg-warn' },
  COMPLETED: { label: 'Completed', cls: 'bg-ok/10 text-ok', dot: 'bg-ok' },
  FAILED: { label: 'Failed', cls: 'bg-bad/10 text-bad', dot: 'bg-bad' },
  STOPPED: { label: 'Stopped', cls: 'bg-white/[0.06] text-silver', dot: 'bg-muted' },
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
  <section class="card p-4" aria-labelledby="agent-status-h">
    <div class="flex items-center justify-between gap-2">
      <h2 id="agent-status-h" class="text-sm font-semibold text-ink">Agent 2 · Research</h2>
      <span class="flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase" :class="state.cls" data-testid="agent-state">
        <span class="h-1.5 w-1.5 rounded-full" :class="state.dot" />{{ state.label }}
      </span>
    </div>

    <div class="mt-3 flex items-center gap-4">
      <div class="relative h-16 w-16 shrink-0" role="img" :aria-label="`Research progress ${progress}%`">
        <svg viewBox="0 0 64 64" class="ring-glow h-16 w-16 -rotate-90" aria-hidden="true">
          <circle cx="32" cy="32" :r="ringR" fill="none" stroke="var(--viz-track)" stroke-width="6" />
          <circle cx="32" cy="32" :r="ringR" fill="none" stroke="var(--viz-1)" stroke-width="6" stroke-linecap="round" :stroke-dasharray="ringC"
            :stroke-dashoffset="ringC * (1 - progress / 100)" class="transition-[stroke-dashoffset] duration-700" />
        </svg>
        <span class="absolute inset-0 grid place-items-center text-sm font-semibold text-ink" data-testid="progress-pct">{{ progress }}%</span>
      </div>
      <dl class="min-w-0 flex-1 space-y-1 text-xs">
        <div class="flex justify-between gap-2"><dt class="text-silver">Country</dt><dd class="truncate font-medium text-ink">{{ loc ? countryName(loc.country_code) : '—' }}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-silver">City / region</dt><dd class="truncate font-medium text-ink">{{ loc ? [loc.city, loc.region].filter(Boolean).join(', ') : '—' }}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-silver">Radius</dt><dd class="font-medium text-ink">{{ loc ? `${loc.radius_km ?? 10} km` : '—' }}</dd></div>
      </dl>
    </div>

    <div class="mt-3 rounded-xl bg-white/[0.03] px-3 py-2 text-xs">
      <div class="text-[10px] font-semibold tracking-wider text-muted uppercase">Current task</div>
      <p class="mt-0.5 line-clamp-2 text-soft" data-testid="current-task">
        <template v-if="!task">No research yet.</template>
        <template v-else-if="task.status === 'QUEUED'">Queued {{ fmtDate(task.created_at) }} — waiting for an Agent 2 worker to claim it.</template>
        <template v-else>{{ (task.stage || task.status).replace(/_/g, ' ').toLowerCase() }}<template v-if="task.progress_message"> · {{ task.progress_message }}</template></template>
      </p>
      <div class="mt-2"><ProgressBar :value="progress" /></div>
    </div>

    <p v-if="unclaimed" class="mt-2 rounded-lg bg-warn/10 px-3 py-2 text-[11px] text-warn" role="status">No Agent 2 worker has claimed this task yet. Check that the <code>agent2</code> service is running.</p>
    <p v-else-if="store.agentState === 'UNRESPONSIVE'" class="mt-2 rounded-lg bg-warn/10 px-3 py-2 text-[11px] text-warn" role="status">No heartbeat since {{ fmtDate(task?.heartbeat_at) }}. The lease expires automatically and the task is re-queued or failed.</p>
    <p v-if="failure" class="mt-2 rounded-lg bg-bad/10 px-3 py-2 text-[11px] text-bad" role="alert">{{ failure.code }}: {{ failure.message || 'The agent reported a failure.' }}</p>
    <p v-if="task?.cancel_requested && task.status === 'RUNNING'" class="mt-2 text-[11px] text-silver">Stop requested — the agent stops at its next checkpoint.</p>
    <p v-if="error" class="mt-2 text-[11px] text-bad" role="alert">{{ error }}</p>

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
    <p id="pause-note" class="mt-1.5 text-[10px] leading-snug text-muted">Pause/resume needs platform support (requested). Stop keeps submitted results.</p>
  </section>
</template>

<style scoped>
.lbf-pulse { animation: pulse 1.4s ease-in-out infinite; box-shadow: 0 0 8px 1px rgb(255 255 255 / 0.8); }
.ring-glow { filter: drop-shadow(0 0 6px rgb(255 255 255 / 0.35)); }
@keyframes pulse { 50% { opacity: .3; } }
@media (prefers-reduced-motion: reduce) { .lbf-pulse { animation: none; } }
</style>
