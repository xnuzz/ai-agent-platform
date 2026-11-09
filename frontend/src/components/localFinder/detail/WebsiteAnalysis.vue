<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Evidence } from '@/api/types'
import { fmtDate } from '@/components/format'
import { analyse, isScanEvidence, type Check } from '@/features/localFinder/analysis'

const props = defineProps<{ website: string; evidence: Evidence[] }>()
const scan = computed(() => analyse(props.evidence.find(isScanEvidence)))
const preview = ref(false) // live preview is opt-in: loading it contacts the business's server from your browser

const ICON: Record<Check['status'], { cls: string; label: string }> = {
  ok: { cls: 'bg-ok/10 text-ok', label: 'OK' }, issue: { cls: 'bg-bad/10 text-bad', label: 'Issue' },
  info: { cls: 'bg-white/[0.06] text-silver', label: 'Info' }, unmeasured: { cls: 'bg-white/[0.03] text-muted', label: 'n/a' },
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
    <section v-if="website" class="overflow-hidden rounded-xl border border-line">
      <div class="flex items-center justify-between gap-2 border-b border-line bg-white/[0.03] px-3 py-2">
        <span class="flex min-w-0 items-center gap-1.5 text-xs text-silver">
          <span class="flex gap-1" aria-hidden="true"><span class="h-2 w-2 rounded-full bg-white/25" /><span class="h-2 w-2 rounded-full bg-white/15" /><span class="h-2 w-2 rounded-full bg-white/10" /></span>
          <span class="truncate">{{ website }}</span>
        </span>
        <a :href="website" target="_blank" rel="noopener noreferrer" class="shrink-0 text-xs font-medium text-ink hover:underline">Open ↗</a>
      </div>
      <iframe v-if="preview" :src="website" title="Website preview" sandbox="" referrerpolicy="no-referrer" loading="lazy" class="h-64 w-full bg-white" />
      <div v-else class="grid h-32 place-items-center bg-white/[0.02] p-4 text-center">
        <div>
          <p class="text-xs text-silver">Live preview loads the site from your browser (sandboxed, no scripts). Some sites refuse to be embedded.</p>
          <button type="button" class="btn-secondary mt-2 text-xs" @click="preview = true">Load preview</button>
        </div>
      </div>
    </section>
    <p v-else class="rounded-xl border border-dashed border-line-strong p-4 text-center text-xs text-silver">No website listed for this business.</p>

    <p v-if="!scan" class="text-sm text-silver">No website scan evidence was submitted for this business.</p>
    <template v-else>
      <p class="text-[11px] text-muted">Scanned {{ fmtDate(scan.retrievedAt) }} by Agent 2<template v-if="!scan.scanned"> · <span class="text-warn">not completed: {{ scan.skippedReason || 'unreachable' }}</span></template></p>
      <section v-for="g in groups" :key="g.title">
        <h4 class="mb-1.5 text-[11px] font-semibold tracking-wider text-silver uppercase">{{ g.title }}</h4>
        <ul class="divide-y divide-line rounded-xl border border-line">
          <li v-for="(c, i) in g.checks" :key="i" class="flex items-start gap-3 px-3 py-2 text-xs">
            <span class="mt-0.5 w-11 shrink-0 rounded px-1 py-0.5 text-center text-[10px] font-semibold" :class="ICON[c.status].cls">{{ ICON[c.status].label }}</span>
            <span class="w-36 shrink-0 font-medium text-soft">{{ c.label }}</span>
            <span class="min-w-0 flex-1 text-silver">{{ c.detail }}</span>
          </li>
          <li v-if="!g.checks.length" class="px-3 py-2 text-xs text-muted">Nothing recorded.</li>
        </ul>
      </section>
      <section>
        <h4 class="mb-1.5 text-[11px] font-semibold tracking-wider text-silver uppercase">Broken links</h4>
        <p v-if="scan.brokenLinks.checked == null" class="text-xs text-muted">Not measured in this scan.</p>
        <p v-else-if="!scan.brokenLinks.broken.length" class="text-xs text-ok">None of {{ scan.brokenLinks.checked }} sampled internal links are broken.</p>
        <ul v-else class="space-y-1 text-xs">
          <li v-for="l in scan.brokenLinks.broken" :key="l.url" class="flex gap-2"><span class="shrink-0 font-mono text-bad">{{ l.status ?? 'ERR' }}</span><span class="truncate text-silver">{{ l.url }}</span></li>
          <li class="text-muted">{{ scan.brokenLinks.broken.length }} of {{ scan.brokenLinks.checked }} sampled links</li>
        </ul>
      </section>
    </template>
  </div>
</template>
