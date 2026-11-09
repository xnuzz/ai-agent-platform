<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { localFinderApi as api } from '@/api/localFinder'
import type { DashboardSummary } from '@/api/types'
import { usePolling } from '@/components/usePolling'
import { locationLabel, matchesSearch } from '@/features/localFinder/model'
import BrandMark from '@/components/BrandMark.vue'
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
  IDLE: { label: 'Agent idle', dot: 'bg-muted' }, WAITING: { label: 'Waiting for agent', dot: 'bg-warn' },
  SCANNING: { label: 'Scanning', dot: 'bg-white animate-pulse' }, UNRESPONSIVE: { label: 'Agent not responding', dot: 'bg-warn' },
  COMPLETED: { label: 'Run completed', dot: 'bg-ok' }, FAILED: { label: 'Run failed', dot: 'bg-bad' }, STOPPED: { label: 'Run stopped', dot: 'bg-muted' },
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
  <header ref="root" class="glass-nav sticky top-0 z-30 border-x-0 border-t-0" @keydown.esc.stop="open = null">
    <div class="flex h-14 items-center gap-3 px-4">
      <RouterLink to="/" class="flex shrink-0 items-center gap-2 font-semibold text-ink">
        <BrandMark :size="32" />
        <span class="hidden sm:inline">Agent Platform</span>
      </RouterLink>

      <nav class="ml-2 hidden items-center gap-1 xl:flex" aria-label="Main">
        <RouterLink v-for="l in LINKS" :key="l.to" :to="l.to" class="relative rounded-full px-3 py-1.5 text-sm whitespace-nowrap text-silver transition hover:bg-white/[0.06] hover:text-ink"
          exact-active-class="top-active font-medium text-ink">
          {{ l.label }}<span v-if="l.to === '/approvals' && pendingTotal" class="ml-1.5 rounded-full bg-white px-1.5 text-[10px] font-semibold text-black tabular-nums">{{ pendingTotal }}</span>
        </RouterLink>
      </nav>

      <div class="relative ml-auto w-full max-w-xs">
        <label class="sr-only" for="top-search">Search discovered businesses</label>
        <svg viewBox="0 0 20 20" class="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-muted" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="9" cy="9" r="6" /><path d="m14 14 4 4" /></svg>
        <input id="top-search" v-model="query" type="search" role="combobox" :aria-expanded="open === 'search' && results.length > 0" aria-controls="top-search-results" autocomplete="off"
          class="input rounded-full py-1.5 pl-8 text-sm" placeholder="Search businesses…" @focus="open = 'search'" @input="open = 'search'; active = 0" @keydown="onSearchKey" />
        <ul v-if="open === 'search' && query.trim()" id="top-search-results" role="listbox" class="glass-pop absolute top-full right-0 left-0 mt-2 overflow-hidden rounded-[var(--radius)] py-1">
          <li v-for="(r, i) in results" :key="r.lead.id" role="option" :aria-selected="i === active">
            <button type="button" class="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm" :class="i === active ? 'bg-white/10' : 'hover:bg-white/[0.05]'" @mouseenter="active = i" @click="pick(i)">
              <span class="min-w-0"><span class="block truncate font-medium text-ink">{{ r.lead.business.name }}</span><span class="block truncate text-xs text-silver">{{ r.lead.business.category }} · {{ locationLabel(r.lead) }}</span></span>
              <span class="shrink-0 text-xs font-semibold text-ink tabular-nums">{{ r.lead.score ?? '–' }}</span>
            </button>
          </li>
          <li v-if="!results.length" class="px-3 py-2 text-sm text-silver">No matching businesses.</li>
        </ul>
      </div>

      <span class="hidden items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs font-medium whitespace-nowrap text-silver md:flex" data-testid="top-agent-state">
        <span class="h-2 w-2 rounded-full" :class="STATE[store.agentState]!.dot" />{{ STATE[store.agentState]!.label }}
      </span>

      <div class="relative">
        <button type="button" class="relative rounded-lg p-2 text-silver hover:bg-white/[0.06] hover:text-ink" :aria-expanded="open === 'bell'" aria-label="Notifications" @click="toggle('bell')">
          <svg viewBox="0 0 20 20" class="h-5 w-5" fill="currentColor" aria-hidden="true"><path d="M10 2a6 6 0 0 0-6 6v3l-1.7 2.6A1 1 0 0 0 3.1 15h13.8a1 1 0 0 0 .8-1.4L16 11V8a6 6 0 0 0-6-6Zm0 16a2.5 2.5 0 0 0 2.4-2h-4.8A2.5 2.5 0 0 0 10 18Z" /></svg>
          <span v-if="pendingTotal" class="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-white shadow-[0_0_8px_1px_rgb(255_255_255/0.8)]" />
        </button>
        <Transition name="pop"><div v-if="open === 'bell'" class="glass-pop absolute right-0 mt-2 w-80 rounded-[var(--radius)] p-3">
          <div class="text-xs font-semibold text-ink">Waiting for your approval</div>
          <RouterLink to="/approvals" class="mt-2 flex items-center justify-between rounded-lg bg-white/[0.05] px-3 py-2 text-sm text-ink hover:bg-white/10">
            <span>{{ pending.PROJECT_BRIEF ?? 0 }} project briefs · {{ pending.CAMPAIGN ?? 0 }} campaigns</span><span aria-hidden="true">→</span>
          </RouterLink>
          <div class="mt-3 text-xs font-semibold text-ink">Recent agent activity</div>
          <ul class="mt-1 max-h-60 space-y-1 overflow-y-auto">
            <li v-for="a in store.activity.slice(0, 8)" :key="a.id" class="truncate text-xs text-silver">{{ a.text }}</li>
            <li v-if="!store.activity.length" class="text-xs text-muted">Nothing yet in this session.</li>
          </ul>
        </div></Transition>
      </div>

      <div class="relative">
        <button type="button" class="grid h-8 w-8 place-items-center rounded-full bg-white text-xs font-semibold text-black" :aria-expanded="open === 'profile'" aria-label="Account menu" @click="toggle('profile')">{{ initials }}</button>
        <Transition name="pop"><div v-if="open === 'profile'" class="glass-pop absolute right-0 mt-2 w-64 rounded-[var(--radius)] p-3">
          <div class="truncate text-sm font-medium text-ink">{{ auth.user?.full_name || auth.user?.email }}</div>
          <div class="truncate text-xs text-silver">{{ auth.user?.email }} · {{ auth.current?.role }}</div>
          <label class="label mt-3" for="ws-switch">Workspace</label>
          <select id="ws-switch" v-model="wsId" class="input py-1.5 text-sm"><option v-for="w in auth.workspaces" :key="w.id" :value="w.id">{{ w.name }}</option></select>
          <div class="mt-3 flex gap-2">
            <RouterLink to="/settings" class="btn-secondary flex-1 justify-center">Settings</RouterLink>
            <button type="button" class="btn-secondary flex-1 justify-center" @click="logout">Sign out</button>
          </div>
        </div></Transition>
      </div>

      <button type="button" class="rounded-lg p-2 text-silver hover:bg-white/[0.06] xl:hidden" :aria-expanded="open === 'menu'" aria-label="Open navigation" @click="toggle('menu')">
        <svg viewBox="0 0 20 20" class="h-5 w-5" fill="currentColor" aria-hidden="true"><path d="M3 5h14v2H3zm0 4h14v2H3zm0 4h14v2H3z" /></svg>
      </button>
    </div>
    <nav v-if="open === 'menu'" class="flex flex-col gap-1 border-t border-line px-4 py-2 xl:hidden" aria-label="Main (mobile)">
      <RouterLink v-for="l in LINKS" :key="l.to" :to="l.to" class="rounded-lg px-3 py-2 text-sm text-soft hover:bg-white/[0.06]" exact-active-class="top-active font-medium text-ink" @click="open = null">{{ l.label }}</RouterLink>
    </nav>
  </header>
</template>

<style scoped>
.top-active { background: linear-gradient(180deg, rgb(255 255 255 / 0.12), rgb(255 255 255 / 0.05)); box-shadow: inset 0 0 0 1px rgb(255 255 255 / 0.12), 0 0 16px -6px rgb(255 255 255 / 0.35); }
</style>
