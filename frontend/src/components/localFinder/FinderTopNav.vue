<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { localFinderApi as api } from '@/api/localFinder'
import type { DashboardSummary } from '@/api/types'
import { usePolling } from '@/components/usePolling'
import { locationLabel, matchesSearch } from '@/features/localFinder/model'
import { useAuthStore } from '@/stores/auth'
import { useLocalFinderStore } from '@/stores/localFinder'

const store = useLocalFinderStore()
const auth = useAuthStore()
const router = useRouter()
const root = ref<HTMLElement>()
const open = ref<'search' | 'bell' | 'profile' | 'menu' | null>(null)
const query = ref('')
const active = ref(0)
const summary = ref<DashboardSummary | null>(null)

usePolling(async () => { if (!store.demo) summary.value = await api.summary().catch(() => summary.value) }, 30_000)

const pending = computed(() => summary.value?.pending_approvals ?? {})
const pendingTotal = computed(() => Object.values(pending.value).reduce((a, b) => a + b, 0))
const results = computed(() => (query.value.trim() ? store.rows.filter((r) => matchesSearch(r, query.value.trim())).slice(0, 8) : []))
const LINKS = [
  { to: '/', label: 'Dashboard' },
  { to: '/local-finder', label: 'Local Business Finder' },
  { to: '/ideas', label: 'SaaS Opportunity Research' },
  { to: '/approvals', label: 'Approvals' },
]
const STATE: Record<string, { label: string; dot: string }> = {
  IDLE: { label: 'Agent idle', dot: 'bg-slate-400' }, WAITING: { label: 'Waiting for agent', dot: 'bg-amber-500' },
  SCANNING: { label: 'Scanning', dot: 'bg-violet-500 animate-pulse' }, UNRESPONSIVE: { label: 'Agent not responding', dot: 'bg-amber-500' },
  COMPLETED: { label: 'Run completed', dot: 'bg-emerald-500' }, FAILED: { label: 'Run failed', dot: 'bg-rose-500' }, STOPPED: { label: 'Run stopped', dot: 'bg-slate-400' },
}
const initials = computed(() => (auth.user?.full_name || auth.user?.email || '?').split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join(''))
const wsId = computed({
  get: () => auth.current?.id ?? '',
  set: (id: string) => auth.selectWorkspace(auth.workspaces.find((w) => w.id === id) ?? null),
})

function pick(i = active.value) {
  const r = results.value[i]
  if (!r) return
  store.select(r.lead.id)
  query.value = ''
  open.value = null
}
function onSearchKey(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') { e.preventDefault(); active.value = Math.min(results.value.length - 1, active.value + 1) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); active.value = Math.max(0, active.value - 1) }
  else if (e.key === 'Enter') { e.preventDefault(); pick() }
  else if (e.key === 'Escape') { query.value = ''; open.value = null }
}
const toggle = (k: NonNullable<typeof open.value>) => { open.value = open.value === k ? null : k }
const outside = (e: MouseEvent) => { if (!root.value?.contains(e.target as Node)) open.value = null }
onMounted(() => document.addEventListener('mousedown', outside))
onBeforeUnmount(() => document.removeEventListener('mousedown', outside))
async function logout() { await auth.logout(true); router.push({ name: 'login' }) }
</script>

<template>
  <header ref="root" class="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur" @keydown.esc.stop="open = null">
    <div class="flex h-14 items-center gap-3 px-4">
      <RouterLink to="/" class="flex shrink-0 items-center gap-2 font-semibold text-slate-900">
        <span class="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-violet-500 to-violet-700 text-white shadow-sm shadow-violet-600/30" aria-hidden="true">
          <svg viewBox="0 0 20 20" class="h-4 w-4" fill="currentColor"><path d="M10 2 3 6v8l7 4 7-4V6l-7-4Zm0 2.3L14.8 7 10 9.7 5.2 7 10 4.3Z" /></svg>
        </span>
        <span class="hidden sm:inline">Agent Platform</span>
      </RouterLink>

      <nav class="ml-2 hidden items-center gap-1 xl:flex" aria-label="Main">
        <RouterLink v-for="l in LINKS" :key="l.to" :to="l.to" class="relative rounded-lg px-3 py-1.5 text-sm whitespace-nowrap text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
          exact-active-class="bg-violet-50 font-medium text-violet-700">
          {{ l.label }}<span v-if="l.to === '/approvals' && pendingTotal" class="ml-1.5 rounded-full bg-violet-600 px-1.5 text-[10px] font-semibold text-white tabular-nums">{{ pendingTotal }}</span>
        </RouterLink>
      </nav>

      <div class="relative ml-auto w-full max-w-xs">
        <label class="sr-only" for="top-search">Search discovered businesses</label>
        <svg viewBox="0 0 20 20" class="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="9" cy="9" r="6" /><path d="m14 14 4 4" /></svg>
        <input id="top-search" v-model="query" type="search" role="combobox" :aria-expanded="open === 'search' && results.length > 0" aria-controls="top-search-results" autocomplete="off"
          class="input bg-slate-50 py-1.5 pl-8 text-sm" placeholder="Search businesses…" @focus="open = 'search'" @input="open = 'search'; active = 0" @keydown="onSearchKey" />
        <ul v-if="open === 'search' && query.trim()" id="top-search-results" role="listbox" class="absolute top-full right-0 left-0 mt-1 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-xl">
          <li v-for="(r, i) in results" :key="r.lead.id" role="option" :aria-selected="i === active">
            <button type="button" class="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm" :class="i === active ? 'bg-violet-50' : 'hover:bg-slate-50'" @mouseenter="active = i" @click="pick(i)">
              <span class="min-w-0"><span class="block truncate font-medium text-slate-800">{{ r.lead.business.name }}</span><span class="block truncate text-xs text-slate-500">{{ r.lead.business.category }} · {{ locationLabel(r.lead) }}</span></span>
              <span class="shrink-0 text-xs font-semibold text-violet-700 tabular-nums">{{ r.lead.score ?? '–' }}</span>
            </button>
          </li>
          <li v-if="!results.length" class="px-3 py-2 text-sm text-slate-500">No matching businesses.</li>
        </ul>
      </div>

      <span class="hidden items-center gap-1.5 rounded-full border border-slate-200 px-2.5 py-1 text-xs font-medium whitespace-nowrap text-slate-600 md:flex" data-testid="top-agent-state">
        <span class="h-2 w-2 rounded-full" :class="STATE[store.agentState]!.dot" />{{ STATE[store.agentState]!.label }}
      </span>

      <div class="relative">
        <button type="button" class="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800" :aria-expanded="open === 'bell'" aria-label="Notifications" @click="toggle('bell')">
          <svg viewBox="0 0 20 20" class="h-5 w-5" fill="currentColor" aria-hidden="true"><path d="M10 2a6 6 0 0 0-6 6v3l-1.7 2.6A1 1 0 0 0 3.1 15h13.8a1 1 0 0 0 .8-1.4L16 11V8a6 6 0 0 0-6-6Zm0 16a2.5 2.5 0 0 0 2.4-2h-4.8A2.5 2.5 0 0 0 10 18Z" /></svg>
          <span v-if="pendingTotal" class="absolute top-1 right-1 h-2 w-2 rounded-full bg-violet-600 ring-2 ring-white" />
        </button>
        <div v-if="open === 'bell'" class="absolute right-0 mt-1 w-80 rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
          <div class="text-xs font-semibold text-slate-900">Waiting for your approval</div>
          <RouterLink to="/approvals" class="mt-2 flex items-center justify-between rounded-lg bg-violet-50 px-3 py-2 text-sm text-violet-800 hover:bg-violet-100">
            <span>{{ pending.PROJECT_BRIEF ?? 0 }} project briefs · {{ pending.CAMPAIGN ?? 0 }} campaigns</span><span aria-hidden="true">→</span>
          </RouterLink>
          <div class="mt-3 text-xs font-semibold text-slate-900">Recent agent activity</div>
          <ul class="mt-1 max-h-60 space-y-1 overflow-y-auto">
            <li v-for="a in store.activity.slice(0, 8)" :key="a.id" class="truncate text-xs text-slate-600">{{ a.text }}</li>
            <li v-if="!store.activity.length" class="text-xs text-slate-400">Nothing yet in this session.</li>
          </ul>
        </div>
      </div>

      <div class="relative">
        <button type="button" class="grid h-8 w-8 place-items-center rounded-full bg-slate-900 text-xs font-semibold text-white" :aria-expanded="open === 'profile'" aria-label="Account menu" @click="toggle('profile')">{{ initials }}</button>
        <div v-if="open === 'profile'" class="absolute right-0 mt-1 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
          <div class="truncate text-sm font-medium text-slate-900">{{ auth.user?.full_name || auth.user?.email }}</div>
          <div class="truncate text-xs text-slate-500">{{ auth.user?.email }} · {{ auth.current?.role }}</div>
          <label class="label mt-3" for="ws-switch">Workspace</label>
          <select id="ws-switch" v-model="wsId" class="input py-1.5 text-sm"><option v-for="w in auth.workspaces" :key="w.id" :value="w.id">{{ w.name }}</option></select>
          <div class="mt-3 flex gap-2">
            <RouterLink to="/settings" class="btn-secondary flex-1 justify-center">Settings</RouterLink>
            <button type="button" class="btn-secondary flex-1 justify-center" @click="logout">Sign out</button>
          </div>
        </div>
      </div>

      <button type="button" class="rounded-lg p-2 text-slate-500 hover:bg-slate-100 xl:hidden" :aria-expanded="open === 'menu'" aria-label="Open navigation" @click="toggle('menu')">
        <svg viewBox="0 0 20 20" class="h-5 w-5" fill="currentColor" aria-hidden="true"><path d="M3 5h14v2H3zm0 4h14v2H3zm0 4h14v2H3z" /></svg>
      </button>
    </div>
    <nav v-if="open === 'menu'" class="flex flex-col gap-1 border-t border-slate-100 px-4 py-2 xl:hidden" aria-label="Main (mobile)">
      <RouterLink v-for="l in LINKS" :key="l.to" :to="l.to" class="rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100" exact-active-class="bg-violet-50 font-medium text-violet-700" @click="open = null">{{ l.label }}</RouterLink>
    </nav>
  </header>
</template>
