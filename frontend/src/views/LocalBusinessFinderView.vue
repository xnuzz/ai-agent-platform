<script setup lang="ts">
/**
 * Agent 2 · Local Business Finder dashboard (route /local-finder).
 * Left: discovered businesses · Centre: live map + charts · Right: agent status, KPIs, activity.
 * Data: live REST polling (features/localFinder/liveFeed.ts). `?demo=1` loads clearly labelled mock data,
 * in development builds only (the demo module is not part of production bundles).
 */
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AnalyticsCharts from '@/components/localFinder/AnalyticsCharts.vue'
import BusinessDetailPanel from '@/components/localFinder/BusinessDetailPanel.vue'
import BusinessMap from '@/components/localFinder/BusinessMap.vue'
import BusinessSidebar from '@/components/localFinder/BusinessSidebar.vue'
import DiscoveryNotification from '@/components/localFinder/DiscoveryNotification.vue'
import FinderTopNav from '@/components/localFinder/FinderTopNav.vue'
import ResearchAnalytics from '@/components/localFinder/ResearchAnalytics.vue'
import ResearchControls from '@/components/localFinder/ResearchControls.vue'
import ResearchProgress from '@/components/localFinder/ResearchProgress.vue'
import { startLiveFeed } from '@/features/localFinder/liveFeed'
import { useAuthStore } from '@/stores/auth'
import { useLocalFinderStore } from '@/stores/localFinder'

const auth = useAuthStore()
const store = useLocalFinderStore()
const route = useRoute()
let stop: (() => void) | null = null
let clock: number | undefined

async function connect() {
  stop?.()
  stop = null
  store.reset()
  if (!auth.current) return
  if (import.meta.env.DEV && route.query.demo === '1') {
    const { startDemoFeed } = await import('@/features/localFinder/demo/demoFeed')
    stop = startDemoFeed(store)
    return
  }
  const feed = startLiveFeed(store)
  store.setSyncHook(feed.refresh)
  stop = feed.stop
}

/** One Escape handler for the page, innermost layer first: details → map picking → configuration → popup. */
function onEscape(e: KeyboardEvent) {
  if (e.key !== 'Escape' || e.defaultPrevented) return
  if (store.detailId) store.closeDetail()
  else if (store.picking) store.picking = false
  else if (store.configOpen) store.configOpen = false
  else if (store.selectedId) store.select(null)
}

onMounted(() => {
  void connect()
  clock = window.setInterval(() => store.tick(), 10_000)
  window.addEventListener('keydown', onEscape)
})
watch(() => auth.current?.id, () => void connect())
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onEscape)
  stop?.()
  window.clearInterval(clock)
  store.reset()
})
</script>

<template>
  <div class="min-h-dvh text-soft">
    <FinderTopNav />
    <div v-if="store.demo" class="border-b border-warn/30 bg-warn/10 px-4 py-1 text-center text-xs font-semibold text-warn" role="status">
      DEMO DATA — development mock feed, not real research. Actions are disabled. Remove <code>?demo=1</code> for live data.
    </div>
    <div v-if="!auth.current" class="card m-6 text-sm">No workspace. Ask an admin for access.</div>
    <!-- Grid areas: phone map → list → status → charts; tablet list | map+charts, status below; desktop 3 columns. -->
    <main v-else class="lbf-grid grid gap-3 p-3" :class="{ 'lbf-grid-demo': store.demo }">
      <BusinessSidebar class="h-[520px] [grid-area:list] md:h-0 md:min-h-full" />
      <div class="relative h-[56vh] min-h-[340px] min-w-0 [grid-area:map] md:h-[60vh] xl:h-auto">
        <BusinessMap><DiscoveryNotification /></BusinessMap>
      </div>
      <AnalyticsCharts class="min-w-0 [grid-area:charts]" />
      <div class="grid min-h-0 gap-3 [grid-area:side] md:grid-cols-2 xl:flex xl:flex-col xl:overflow-y-auto">
        <ResearchProgress />
        <ResearchAnalytics />
      </div>
    </main>
    <ResearchControls />
    <BusinessDetailPanel />
  </div>
</template>

<style scoped>
.lbf-grid { grid-template-columns: minmax(0, 1fr); grid-template-areas: 'map' 'list' 'side' 'charts'; }
@media (min-width: 768px) {
  .lbf-grid { grid-template-columns: 300px minmax(0, 1fr); grid-template-areas: 'list map' 'list charts' 'side side'; }
}
@media (min-width: 1280px) {
  .lbf-grid {
    height: calc(100dvh - 3.5rem); grid-template-columns: 300px minmax(0, 1fr) 320px;
    grid-template-rows: minmax(0, 1fr) auto; grid-template-areas: 'list map side' 'list charts side';
  }
  .lbf-grid-demo { height: calc(100dvh - 5rem); }
}
@media (min-width: 1536px) { .lbf-grid { grid-template-columns: 340px minmax(0, 1fr) 360px; } }
</style>
