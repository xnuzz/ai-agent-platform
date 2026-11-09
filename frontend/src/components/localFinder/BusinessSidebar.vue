<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { fmtDate } from '@/components/format'
import { taskArea, type LeadFilter, type LeadSort } from '@/features/localFinder/model'
import { useLocalFinderStore } from '@/stores/localFinder'
import BusinessCard from './BusinessCard.vue'

const store = useLocalFinderStore()
const list = ref<HTMLElement>()
const FILTERS: { id: LeadFilter; label: string }[] = [
  { id: 'all', label: 'All leads' }, { id: 'high', label: 'High potential' }, { id: 'medium', label: 'Medium' }, { id: 'low', label: 'Low' },
  { id: 'new', label: 'New discoveries' }, { id: 'reviewed', label: 'Reviewed' }, { id: 'approved', label: 'Approved' }, { id: 'rejected', label: 'Rejected' },
]
const SORTS: { id: LeadSort; label: string }[] = [
  { id: 'recent', label: 'Newest first' }, { id: 'score', label: 'Highest score' }, { id: 'problems', label: 'Most problems' }, { id: 'name', label: 'Name A–Z' },
]

// Keep the selected card visible when the selection comes from the map or a notification.
watch(() => store.selectedId, async (id) => {
  await nextTick()
  if (id) list.value?.querySelector<HTMLElement>(`[data-lead-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
})

/** Arrow keys move through the cards (and select), Home/End jump, Enter on a card opens details. */
function onKey(e: KeyboardEvent) {
  const cards = [...(list.value?.querySelectorAll<HTMLButtonElement>('[data-card]') ?? [])]
  const i = cards.indexOf(document.activeElement as HTMLButtonElement)
  if (i < 0) return
  let next = -1
  if (e.key === 'ArrowDown') next = Math.min(cards.length - 1, i + 1)
  else if (e.key === 'ArrowUp') next = Math.max(0, i - 1)
  else if (e.key === 'Home') next = 0
  else if (e.key === 'End') next = cards.length - 1
  else if (e.key === 'Enter' && cards[i]!.getAttribute('aria-pressed') === 'true') { e.preventDefault(); store.openDetail(cards[i]!.dataset.leadId!); return }
  if (next < 0) return
  e.preventDefault()
  cards[next]!.focus()
  store.select(cards[next]!.dataset.leadId!)
}
</script>

<template>
  <aside class="flex h-full min-h-0 flex-col card p-0" aria-label="Discovered businesses">
    <div class="space-y-3 border-b border-line p-4">
      <div class="flex items-center justify-between gap-2">
        <h2 class="text-sm font-semibold text-ink">Discovered businesses</h2>
        <span class="rounded-full bg-white/[0.05] px-2 py-0.5 text-xs font-semibold text-ink tabular-nums" data-testid="visible-count">{{ store.visibleRows.length }}</span>
      </div>
      <label class="relative block">
        <span class="sr-only">Search businesses</span>
        <svg viewBox="0 0 20 20" class="pointer-events-none absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-muted" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="9" cy="9" r="6" /><path d="m14 14 4 4" /></svg>
        <input v-model="store.search" type="search" class="input py-1.5 pl-8 text-xs" placeholder="Search name, category, problem…" />
      </label>
      <div class="flex gap-2">
        <select v-model="store.taskFilter" class="input min-w-0 flex-1 py-1.5 text-xs" aria-label="Research run">
          <option :value="null">All research runs</option>
          <option v-for="t in store.tasks" :key="t.id" :value="t.id">{{ taskArea(t) }} · {{ fmtDate(t.created_at) }} · {{ t.status }}</option>
        </select>
        <select v-model="store.sort" class="input w-28 shrink-0 py-1.5 text-xs" aria-label="Sort businesses">
          <option v-for="s in SORTS" :key="s.id" :value="s.id">{{ s.label }}</option>
        </select>
      </div>
      <div class="-mx-1 flex flex-wrap gap-1.5 px-1" role="radiogroup" aria-label="Filter leads">
        <button v-for="f in FILTERS" :key="f.id" type="button" role="radio" :aria-checked="store.filter === f.id"
          class="chip" :class="{ 'chip-on': store.filter === f.id }"
          @click="store.filter = f.id">
          {{ f.label }} <span class="tabular-nums opacity-70">{{ store.filterCounts[f.id] }}</span>
        </button>
      </div>
    </div>

    <p v-if="store.truncated" class="mx-4 mt-3 rounded-lg bg-warn/10 px-3 py-2 text-[11px] text-warn">Showing the newest 1,000 leads. Filter by research run to see older ones.</p>

    <div ref="list" class="min-h-0 flex-1 space-y-2 overflow-y-auto p-3" role="list" @keydown="onKey">
      <template v-if="!store.loaded">
        <div v-for="i in 5" :key="i" class="skeleton h-28" />
      </template>
      <div v-for="r in store.visibleRows" v-else :key="r.lead.id" role="listitem">
        <BusinessCard :row="r" :selected="r.lead.id === store.selectedId" :fresh="!!store.fresh[r.lead.id]"
          @select="store.select(r.lead.id)" @open="store.openDetail(r.lead.id)" />
      </div>
      <div v-if="store.loaded && !store.visibleRows.length" class="px-4 py-10 text-center text-sm text-silver">
        <template v-if="store.scopedRows.length">No businesses match this filter.
          <button type="button" class="mt-2 block w-full text-xs font-medium text-ink hover:underline" @click="store.filter = 'all'; store.search = ''">Clear filters</button>
        </template>
        <template v-else-if="store.agentState === 'SCANNING' || store.agentState === 'WAITING'">Waiting for the first results…</template>
        <template v-else>No businesses yet. Start a research run to discover local leads.</template>
      </div>
    </div>
  </aside>
</template>
