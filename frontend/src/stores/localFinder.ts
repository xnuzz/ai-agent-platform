/**
 * Local Business Finder (Agent 2 dashboard) state.
 *
 * Data enters only through `ingest*` (from the live feed, or the dev-only demo feed). Ingesting a newer
 * snapshot diffs it against the known one and turns the differences into DiscoveryEvents, which drive
 * notifications, the activity feed and marker animations. The first snapshot is a silent baseline.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { Lead, ProjectBrief, ResearchTask } from '@/api/types'
import { diffLeads, diffTask, type DiscoveryEvent } from '@/features/localFinder/events'
import {
  agentStateOf, isActive, kpis as computeKpis, locationLabel, matchesFilter, matchesSearch, problemLabel, sortRows, toRow, topProblem,
  type LeadFilter, type LeadRow, type LeadSort,
} from '@/features/localFinder/model'

export type Connection = 'connecting' | 'live' | 'reconnecting'
export type ActivityKind = 'discovered' | 'qualified' | 'updated' | 'started' | 'progress' | 'completed' | 'failed' | 'cancelled'
export interface ActivityItem { id: number; at: number; kind: ActivityKind; text: string; leadId?: string }
export interface Toast { id: number; kind: 'discovery' | 'summary' | 'task'; title: string; lines: string[]; leadId?: string; tone?: 'ok' | 'error' }

const MAX_ACTIVITY = 40
const MAX_TOASTS = 3
const TOAST_MS = 6500
const FRESH_MS = 4000

let seq = 0

export const useLocalFinderStore = defineStore('localFinder', () => {
  const leads = ref<Record<string, Lead>>({})
  const briefs = ref<Record<string, ProjectBrief>>({}) // keyed by lead id: the lead's most recent brief
  const tasks = ref<ResearchTask[]>([])
  const loaded = ref(false)
  const truncated = ref(false)
  const connection = ref<Connection>('connecting')
  const lastSyncAt = ref<number | null>(null)
  const syncError = ref<string | null>(null)
  const demo = ref(false)

  const taskFilter = ref<string | null>(null)
  const filter = ref<LeadFilter>('all')
  const search = ref('')
  const sort = ref<LeadSort>('recent')
  const selectedId = ref<string | null>(null)
  const focusSeq = ref(0) // bumped on every explicit selection so the map re-centres even on the same id
  const detailId = ref<string | null>(null)
  const configOpen = ref(false)
  /** Research configuration ↔ map: "pick the search centre on the map" mode and the draft search area. */
  const picking = ref(false)
  const draftCenter = ref<[number, number] | null>(null) // [lng, lat], chosen by the user on the map
  const draftRadiusKm = ref(10)

  const activity = ref<ActivityItem[]>([])
  const toasts = ref<Toast[]>([])
  const fresh = ref<Record<string, number>>({})
  const now = ref(Date.now())
  const timers = new Set<number>()

  // ------------------------------------------------------------------ derived
  const rows = computed<LeadRow[]>(() => Object.values(leads.value).map((l) => toRow(l, briefs.value[l.id] ?? null)))
  const scopedRows = computed(() => (taskFilter.value ? rows.value.filter((r) => r.lead.research_task === taskFilter.value) : rows.value))
  const searchedRows = computed(() => scopedRows.value.filter((r) => matchesSearch(r, search.value.trim())))
  const visibleRows = computed(() => sortRows(searchedRows.value.filter((r) => matchesFilter(r, filter.value)), sort.value))
  const filterCounts = computed(() => {
    const keys: LeadFilter[] = ['all', 'high', 'medium', 'low', 'new', 'reviewed', 'approved', 'rejected']
    return Object.fromEntries(keys.map((k) => [k, searchedRows.value.filter((r) => matchesFilter(r, k)).length])) as Record<LeadFilter, number>
  })
  const selectedRow = computed(() => rows.value.find((r) => r.lead.id === selectedId.value) ?? null)
  const detailRow = computed(() => rows.value.find((r) => r.lead.id === detailId.value) ?? null)
  /** The task the right panel reports on: the filtered run, else the newest Agent 2 task. */
  const currentTask = computed<ResearchTask | null>(() =>
    (taskFilter.value ? tasks.value.find((t) => t.id === taskFilter.value) : tasks.value[0]) ?? null)
  const activeTask = computed(() => tasks.value.find(isActive) ?? null)
  const agentState = computed(() => agentStateOf(activeTask.value ?? currentTask.value, now.value))
  const kpis = computed(() => computeKpis(scopedRows.value, now.value))

  // ------------------------------------------------------------------ ingestion
  function ingestTasks(list: ResearchTask[], emit = true) {
    const prev = Object.fromEntries(tasks.value.map((t) => [t.id, t]))
    if (emit && loaded.value) list.forEach((t) => handle(diffTask(prev[t.id], t)))
    tasks.value = list
  }

  function ingestLeads(list: Lead[], emit = true) {
    const events = emit && loaded.value ? diffLeads(leads.value, list) : []
    const next = { ...leads.value }
    for (const l of list) next[l.id] = l
    leads.value = next
    handle(events)
  }

  /** Replaces the full lead set (periodic full refresh): also drops leads deleted/erased server-side. */
  function replaceLeads(list: Lead[], emit = true) {
    const events = emit && loaded.value ? diffLeads(leads.value, list) : []
    leads.value = Object.fromEntries(list.map((l) => [l.id, l]))
    if (selectedId.value && !leads.value[selectedId.value]) selectedId.value = null
    handle(events)
  }

  function ingestBriefs(list: ProjectBrief[]) {
    const next = { ...briefs.value }
    for (const b of list) {
      const cur = next[b.lead]
      if (!cur || cur.created_at <= b.created_at) next[b.lead] = b
    }
    briefs.value = next
  }

  function markLoaded() { loaded.value = true }

  // ------------------------------------------------------------------ events → UI
  function handle(events: DiscoveryEvent[]) {
    if (!events.length) return
    const discovered: Lead[] = []
    for (const e of events) {
      switch (e.type) {
        case 'business.discovered':
          discovered.push(e.lead)
          markFresh(e.lead.id)
          log('discovered', `Discovered ${e.lead.business.name} · ${locationLabel(e.lead)}`, e.lead.id)
          break
        case 'business.qualified':
          log('qualified', `Qualified ${e.lead.business.name} (score ${e.lead.score ?? '—'})`, e.lead.id)
          break
        case 'business.updated':
          if (e.previous.status !== e.lead.status) log('updated', `${e.lead.business.name}: ${e.previous.status} → ${e.lead.status}`, e.lead.id)
          break
        case 'research.started':
          log('started', `Research started · ${e.task.progress_message || 'agent claimed the task'}`)
          break
        case 'research.progress': {
          const last = activity.value[0]
          const text = `${(e.task.stage || 'Working').replace(/_/g, ' ').toLowerCase()} · ${e.task.progress_message || `${e.task.progress}%`}`
          if (!(last?.kind === 'progress' && last.text === text)) log('progress', text)
          break
        }
        case 'research.completed':
          log('completed', 'Research completed')
          toast({ kind: 'task', title: 'Research completed', lines: [e.task.progress_message || 'All results submitted.'], tone: 'ok' })
          break
        case 'research.failed': {
          const err = (e.task.error ?? {}) as { code?: string; message?: string }
          log('failed', `Research failed · ${err.code ?? 'error'}`)
          toast({ kind: 'task', title: 'Research failed', lines: [err.message || err.code || 'The agent reported a failure.'], tone: 'error' })
          break
        }
        case 'research.cancelled':
          log('cancelled', 'Research stopped')
          break
      }
    }
    // A batch arrives at once (Agent 2 submits every 10 businesses): show a few, summarise the rest.
    discovered.slice(0, 2).forEach((l) => toast({
      kind: 'discovery', title: 'New business discovered', leadId: l.id,
      lines: [l.business.name, locationLabel(l), ...(topProblem(l) ? [`Potential opportunity: ${problemLabel(topProblem(l))}`] : [])],
    }))
    if (discovered.length > 2) toast({ kind: 'summary', title: `+${discovered.length - 2} more discovered`, lines: ['Shown in the list and on the map.'] })
  }

  function log(kind: ActivityKind, text: string, leadId?: string) {
    activity.value = [{ id: ++seq, at: Date.now(), kind, text, leadId }, ...activity.value].slice(0, MAX_ACTIVITY)
  }

  function toast(t: Omit<Toast, 'id'>) {
    const id = ++seq
    toasts.value = [...toasts.value, { ...t, id }].slice(-MAX_TOASTS)
    later(() => dismissToast(id), TOAST_MS)
  }
  function dismissToast(id: number) { toasts.value = toasts.value.filter((t) => t.id !== id) }

  function markFresh(id: string) {
    fresh.value = { ...fresh.value, [id]: Date.now() }
    later(() => { const { [id]: _, ...rest } = fresh.value; fresh.value = rest }, FRESH_MS)
  }

  function later(fn: () => void, ms: number) {
    const t = window.setTimeout(() => { timers.delete(t); fn() }, ms)
    timers.add(t)
  }

  // ------------------------------------------------------------------ selection
  function select(id: string | null) {
    selectedId.value = id
    if (id) focusSeq.value++
  }
  function openDetail(id: string) {
    selectedId.value = id
    detailId.value = id
  }
  function closeDetail() { detailId.value = null }

  /** After a user action: replace one lead (+ its brief) with fresh server data. */
  function upsert(lead: Lead, brief?: ProjectBrief | null) {
    leads.value = { ...leads.value, [lead.id]: lead }
    if (brief) briefs.value = { ...briefs.value, [lead.id]: brief }
  }

  function tick() { now.value = Date.now() }

  // The view wires the live feed's "poll now" here so actions can refresh without importing the feed.
  let syncHook: () => void = () => {}
  function setSyncHook(fn: () => void) { syncHook = fn }
  function syncNow() { syncHook() }

  function reset() {
    timers.forEach((t) => window.clearTimeout(t))
    timers.clear()
    leads.value = {}; briefs.value = {}; tasks.value = []; activity.value = []; toasts.value = []; fresh.value = {}
    loaded.value = false; truncated.value = false; connection.value = 'connecting'; lastSyncAt.value = null; syncError.value = null
    selectedId.value = null; detailId.value = null; taskFilter.value = null; configOpen.value = false; demo.value = false
    picking.value = false; draftCenter.value = null
  }

  return {
    leads, briefs, tasks, loaded, truncated, connection, lastSyncAt, syncError, demo,
    taskFilter, filter, search, sort, selectedId, focusSeq, detailId, configOpen, picking, draftCenter, draftRadiusKm, activity, toasts, fresh, now,
    rows, scopedRows, visibleRows, filterCounts, selectedRow, detailRow, currentTask, activeTask, agentState, kpis,
    ingestTasks, ingestLeads, replaceLeads, ingestBriefs, markLoaded, select, openDetail, closeDetail, upsert, dismissToast, tick, reset, log, setSyncHook, syncNow,
  }
})
