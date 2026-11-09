/**
 * Live transport for the Local Business Finder: polling over the documented REST API (the platform's only
 * live mechanism today — no SSE/WebSocket endpoint exists). Adaptive cadence:
 *   - a task QUEUED/RUNNING → task list + that task's leads/briefs every 3 s
 *   - idle → every 15 s (picks up runs started elsewhere, e.g. the Tasks page or a teammate)
 *   - full lead/brief refresh every 30 s and whenever a task changes status (catches edits by others)
 *   - tab hidden → 30 s; back to visible / browser online → immediate tick
 *   - errors → exponential backoff (2 s … 30 s), connection shown as "reconnecting"
 */
import { ApiError, errorText } from '@/api/client'
import { localFinderApi as api } from '@/api/localFinder'
import type { useLocalFinderStore } from '@/stores/localFinder'
import { isActive } from './model'

type Store = ReturnType<typeof useLocalFinderStore>

const ACTIVE_MS = 3000
const IDLE_MS = 15_000
const HIDDEN_MS = 30_000
const FULL_MS = 30_000
const MAX_BACKOFF_MS = 30_000

export type LiveFeed = { stop: () => void; refresh: () => void }

export function startLiveFeed(store: Store): LiveFeed {
  let stopped = false
  let timer: number | undefined
  let failures = 0
  let lastFull = 0
  let running = false
  let again = false
  let lastStatuses = ''

  async function full() {
    const [leads, briefs] = await Promise.all([api.allLeads(), api.allBriefs()])
    store.replaceLeads(leads.items)
    store.ingestBriefs(briefs.items)
    store.truncated = leads.truncated
    lastFull = Date.now()
  }

  async function tick() {
    if (stopped) return
    if (running) { again = true; return }
    running = true
    window.clearTimeout(timer)
    try {
      const tasks = await api.tasks()
      const statuses = tasks.map((t) => `${t.id}:${t.status}`).join(',')
      store.ingestTasks(tasks)
      if (!store.loaded) {
        await full()
        store.markLoaded()
      } else {
        // Stream the active run's results first so discoveries appear as soon as a batch lands.
        for (const t of tasks.filter((x) => x.status === 'RUNNING')) {
          const [leads, briefs] = await Promise.all([api.taskLeads(t.id), api.taskBriefs(t.id)])
          store.ingestBriefs(briefs.items)
          store.ingestLeads(leads.items)
        }
        if (statuses !== lastStatuses || Date.now() - lastFull > FULL_MS) await full()
      }
      lastStatuses = statuses
      failures = 0
      store.connection = 'live'
      store.syncError = null
      store.lastSyncAt = Date.now()
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { stopped = true; return } // client redirects to login
      failures++
      store.connection = store.loaded || failures > 1 ? 'reconnecting' : 'connecting'
      store.syncError = errorText(e)
    } finally {
      running = false
      store.tick()
      if (again && !stopped) { again = false; void tick() } else schedule()
    }
  }

  function schedule() {
    if (stopped) return
    const base = document.hidden ? HIDDEN_MS : store.tasks.some(isActive) ? ACTIVE_MS : IDLE_MS
    const delay = failures ? Math.min(MAX_BACKOFF_MS, 2000 * 2 ** (failures - 1)) : base
    timer = window.setTimeout(tick, delay)
  }

  const wake = () => { if (!document.hidden) void tick() }
  document.addEventListener('visibilitychange', wake)
  window.addEventListener('online', wake)
  void tick()

  return {
    stop() {
      stopped = true
      window.clearTimeout(timer)
      document.removeEventListener('visibilitychange', wake)
      window.removeEventListener('online', wake)
    },
    /** Poll now (after a user action) instead of waiting for the next tick. */
    refresh: () => void tick(),
  }
}
