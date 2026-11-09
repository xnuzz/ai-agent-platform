<script setup lang="ts">
import { useLocalFinderStore, type Toast } from '@/stores/localFinder'

/** Toast stack over the map (max 3, auto-dismissed). Clicking a discovery selects it on the map. */
const store = useLocalFinderStore()
function open(t: Toast) {
  if (t.leadId) store.select(t.leadId)
  store.dismissToast(t.id)
}
</script>

<template>
  <div class="pointer-events-none absolute right-3 bottom-10 z-10 flex w-72 flex-col gap-2" aria-live="polite" aria-atomic="false">
    <TransitionGroup name="lbf-toast">
      <div v-for="t in store.toasts" :key="t.id" class="glass-pop pointer-events-auto overflow-hidden rounded-[var(--radius)] text-ink"
        :class="t.tone === 'error' ? 'border-bad/40' : t.tone === 'ok' ? 'border-ok/40' : ''" data-testid="toast">
        <div class="flex items-start gap-3 p-3">
          <span class="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg"
            :class="t.tone === 'error' ? 'bg-bad/20 text-bad' : t.tone === 'ok' ? 'bg-ok/20 text-ok' : 'bg-white/10 text-ink'" aria-hidden="true">
            <svg v-if="t.kind === 'discovery'" viewBox="0 0 20 20" class="h-4 w-4" fill="currentColor"><path fill-rule="evenodd" d="M10 18s6-5.2 6-10A6 6 0 0 0 4 8c0 4.8 6 10 6 10Zm0-8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" clip-rule="evenodd" /></svg>
            <svg v-else viewBox="0 0 20 20" class="h-4 w-4" fill="currentColor"><path d="M10 2a6 6 0 0 0-6 6v3l-1.7 2.6A1 1 0 0 0 3.1 15h13.8a1 1 0 0 0 .8-1.4L16 11V8a6 6 0 0 0-6-6Zm0 16a2.5 2.5 0 0 0 2.4-2h-4.8A2.5 2.5 0 0 0 10 18Z" /></svg>
          </span>
          <button type="button" class="min-w-0 flex-1 text-left" :disabled="!t.leadId" @click="open(t)">
            <div class="text-[10px] font-semibold tracking-wider text-silver uppercase">{{ t.title }}</div>
            <div v-for="(l, i) in t.lines" :key="i" class="truncate text-xs" :class="i === 0 && t.kind === 'discovery' ? 'mt-0.5 text-sm font-semibold' : 'text-muted'">{{ l }}</div>
          </button>
          <button type="button" class="-mt-1 -mr-1 rounded p-1 text-muted hover:text-ink" aria-label="Dismiss notification" @click="store.dismissToast(t.id)">
            <svg viewBox="0 0 20 20" class="h-3.5 w-3.5" fill="currentColor" aria-hidden="true"><path d="M5.3 5.3a1 1 0 0 1 1.4 0L10 8.6l3.3-3.3a1 1 0 1 1 1.4 1.4L11.4 10l3.3 3.3a1 1 0 0 1-1.4 1.4L10 11.4l-3.3 3.3a1 1 0 0 1-1.4-1.4L8.6 10 5.3 6.7a1 1 0 0 1 0-1.4Z" /></svg>
          </button>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.lbf-toast-enter-active, .lbf-toast-leave-active { transition: all .25s ease; }
.lbf-toast-enter-from { opacity: 0; transform: translateY(8px) scale(.98); }
.lbf-toast-leave-to { opacity: 0; transform: translateX(16px); }
@media (prefers-reduced-motion: reduce) { .lbf-toast-enter-active, .lbf-toast-leave-active { transition: none; } }
</style>
