<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { Opportunity, Paginated, SoftwareIdea } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import OpportunityMap from '@/components/charts/OpportunityMap.vue'
import { useAction } from '@/components/useAction'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const ideas = ref<SoftwareIdea[]>([])
const opps = ref<Opportunity[]>([])
const oppFilter = ref('')
const selectedOpp = ref<string | null>(null)
async function focusOpp(id: string) {
  selectedOpp.value = id
  await nextTick()
  document.getElementById(`opp-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
const { error, run } = useAction()

const loadOpps = async () => {
  opps.value = (await api.get<Paginated<Opportunity>>('opportunities/', { ordering: '-score', status: oppFilter.value || undefined })).results
}
onMounted(async () => { ideas.value = (await api.get<Paginated<SoftwareIdea>>('software-ideas/', { ordering: '-score' })).results })
watch(oppFilter, loadOpps, { immediate: true })

const setStatus = (o: Opportunity, status: string) => run(async () => {
  await api.post(`opportunities/${o.id}/set-status/`, { status })
  await loadOpps()
})
</script>

<template>
  <PageHeader title="Software ideas" subtitle="Agent 1 · SaaS opportunity research — evidence-backed opportunities and the product ideas built on them." />
  <ErrorBanner :message="error" />

  <section class="card mb-4" aria-labelledby="map-h">
    <div class="mb-3 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 id="map-h" class="section-title">Opportunity map</h2>
        <p class="mt-0.5 text-xs text-silver">Pain severity × score. Size = evidence sources · brightest = shortlisted. Select a node to jump to it.</p>
      </div>
      <select v-model="oppFilter" class="input w-40" aria-label="Filter opportunities"><option value="">All</option><option>NEW</option><option>SHORTLISTED</option><option>DISMISSED</option></select>
    </div>
    <OpportunityMap v-if="opps.length" :items="opps" :selected="selectedOpp" @select="focusOpp" />
    <p v-else class="py-10 text-center text-sm text-silver">No opportunities yet — start an Agent 1 task.</p>
  </section>

  <div class="grid gap-4 lg:grid-cols-2">
    <section class="space-y-3">
      <h2 class="kicker">Ideas</h2>
      <RouterLink v-for="i in ideas" :key="i.id" :to="`/ideas/${i.id}`" class="card lift block">
        <div class="flex items-start justify-between gap-2"><h3 class="font-semibold">{{ i.name }}</h3><StatusBadge :status="i.status" /></div>
        <p class="mt-1.5 text-sm text-silver">{{ i.summary }}</p>
        <div class="mt-3 flex items-center gap-3 text-xs text-muted">
          <span class="h-1 w-20 overflow-hidden rounded-full bg-[var(--viz-track)]"><span class="block h-full rounded-full bg-white" :style="{ width: `${i.score ?? 0}%` }" /></span>
          <span>Score {{ i.score ?? '—' }} · {{ i.evidence_ids.length }} source(s) · {{ i.pricing_model }}</span>
        </div>
      </RouterLink>
      <p v-if="!ideas.length" class="card text-sm text-silver">No ideas yet — start an Agent 1 task.</p>
    </section>
    <section class="space-y-3">
      <h2 class="kicker">Opportunities</h2>
      <article v-for="o in opps" :id="`opp-${o.id}`" :key="o.id" class="card transition-[border-color,box-shadow] duration-300"
        :class="{ 'opp-selected': o.id === selectedOpp }" @click="selectedOpp = o.id">
        <div class="flex items-start justify-between gap-2"><h3 class="font-medium">{{ o.title }}</h3><StatusBadge :status="o.status" /></div>
        <p class="mt-1.5 text-sm text-silver">{{ o.problem_statement }}</p>
        <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
          <span class="text-xs text-muted">{{ o.industry }} · severity {{ o.pain_severity ?? '—' }}/5 · score {{ o.score ?? '—' }}</span>
          <span v-if="auth.canWrite()" class="flex gap-2">
            <button v-if="o.status === 'NEW'" class="btn-secondary" @click.stop="setStatus(o, 'SHORTLISTED')">Shortlist</button>
            <button v-if="o.status !== 'DISMISSED'" class="btn-secondary" @click.stop="setStatus(o, 'DISMISSED')">Dismiss</button>
            <button v-if="o.status !== 'NEW'" class="btn-secondary" @click.stop="setStatus(o, 'NEW')">Reset</button>
          </span>
        </div>
      </article>
      <p v-if="!opps.length" class="card text-sm text-silver">None.</p>
    </section>
  </div>
</template>

<style scoped>
.opp-selected { border-color: rgb(255 255 255 / 0.5); box-shadow: var(--shadow-1), 0 0 28px -6px rgb(255 255 255 / 0.35); }
</style>
