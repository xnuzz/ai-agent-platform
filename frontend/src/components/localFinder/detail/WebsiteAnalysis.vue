<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Evidence } from '@/api/types'
import { fmtDate } from '@/components/format'
import { analyse, isScanEvidence, type Check } from '@/features/localFinder/analysis'

const props = defineProps<{ website: string; evidence: Evidence[] }>()
const scan = computed(() => analyse(props.evidence.find(isScanEvidence)))
const preview = ref(false) // live preview is opt-in: loading it contacts the business's server from your browser

const ICON: Record<Check['status'], { cls: string; label: string }> = {
  ok: { cls: 'bg-emerald-100 text-emerald-700', label: 'OK' }, issue: { cls: 'bg-rose-100 text-rose-700', label: 'Issue' },
  info: { cls: 'bg-slate-100 text-slate-600', label: 'Info' }, unmeasured: { cls: 'bg-slate-50 text-slate-400', label: 'n/a' },
}
const groups = computed(() => scan.value ? [
  { title: 'Mobile responsiveness', checks: scan.value.mobile },
  { title: 'Accessibility (measured)', checks: scan.value.accessibility },
  { title: 'Missing functionality', checks: scan.value.functionality },
  { title: 'Technical issues', checks: scan.value.technical },
] : [])
</script>

<template>
  <div class="space-y-4">
    <section v-if="website" class="overflow-hidden rounded-xl border border-slate-200">
      <div class="flex items-center justify-between gap-2 border-b border-slate-100 bg-slate-50 px-3 py-2">
        <span class="flex min-w-0 items-center gap-1.5 text-xs text-slate-500">
          <span class="flex gap-1" aria-hidden="true"><span class="h-2 w-2 rounded-full bg-rose-300" /><span class="h-2 w-2 rounded-full bg-amber-300" /><span class="h-2 w-2 rounded-full bg-emerald-300" /></span>
          <span class="truncate">{{ website }}</span>
        </span>
        <a :href="website" target="_blank" rel="noopener noreferrer" class="shrink-0 text-xs font-medium text-violet-700 hover:underline">Open ↗</a>
      </div>
      <iframe v-if="preview" :src="website" title="Website preview" sandbox="" referrerpolicy="no-referrer" loading="lazy" class="h-64 w-full bg-white" />
      <div v-else class="grid h-32 place-items-center bg-gradient-to-br from-slate-50 to-violet-50/40 p-4 text-center">
        <div>
          <p class="text-xs text-slate-500">Live preview loads the site from your browser (sandboxed, no scripts). Some sites refuse to be embedded.</p>
          <button type="button" class="btn-secondary mt-2 text-xs" @click="preview = true">Load preview</button>
        </div>
      </div>
    </section>
    <p v-else class="rounded-xl border border-dashed border-slate-300 p-4 text-center text-xs text-slate-500">No website listed for this business.</p>

    <p v-if="!scan" class="text-sm text-slate-500">No website scan evidence was submitted for this business.</p>
    <template v-else>
      <p class="text-[11px] text-slate-400">Scanned {{ fmtDate(scan.retrievedAt) }} by Agent 2<template v-if="!scan.scanned"> · <span class="text-amber-700">not completed: {{ scan.skippedReason || 'unreachable' }}</span></template></p>
      <section v-for="g in groups" :key="g.title">
        <h4 class="mb-1.5 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">{{ g.title }}</h4>
        <ul class="divide-y divide-slate-100 rounded-xl border border-slate-200">
          <li v-for="(c, i) in g.checks" :key="i" class="flex items-start gap-3 px-3 py-2 text-xs">
            <span class="mt-0.5 w-11 shrink-0 rounded px-1 py-0.5 text-center text-[10px] font-semibold" :class="ICON[c.status].cls">{{ ICON[c.status].label }}</span>
            <span class="w-36 shrink-0 font-medium text-slate-700">{{ c.label }}</span>
            <span class="min-w-0 flex-1 text-slate-600">{{ c.detail }}</span>
          </li>
          <li v-if="!g.checks.length" class="px-3 py-2 text-xs text-slate-400">Nothing recorded.</li>
        </ul>
      </section>
      <section>
        <h4 class="mb-1.5 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">Broken links</h4>
        <p v-if="scan.brokenLinks.checked == null" class="text-xs text-slate-400">Not measured in this scan.</p>
        <p v-else-if="!scan.brokenLinks.broken.length" class="text-xs text-emerald-700">None of {{ scan.brokenLinks.checked }} sampled internal links are broken.</p>
        <ul v-else class="space-y-1 text-xs">
          <li v-for="l in scan.brokenLinks.broken" :key="l.url" class="flex gap-2"><span class="shrink-0 font-mono text-rose-700">{{ l.status ?? 'ERR' }}</span><span class="truncate text-slate-600">{{ l.url }}</span></li>
          <li class="text-slate-400">{{ scan.brokenLinks.broken.length }} of {{ scan.brokenLinks.checked }} sampled links</li>
        </ul>
      </section>
    </template>
  </div>
</template>
