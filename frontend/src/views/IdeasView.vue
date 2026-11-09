<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '@/api/client'
import type { Opportunity, Paginated, SoftwareIdea } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAction } from '@/components/useAction'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const ideas = ref<SoftwareIdea[]>([])
const opps = ref<Opportunity[]>([])
const oppFilter = ref('')
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
  <PageHeader title="Software ideas" subtitle="Agent 1 output: evidence-backed opportunities and product ideas." />
  <ErrorBanner :message="error" />
  <div class="grid gap-4 lg:grid-cols-2">
    <section class="space-y-3">
      <h2 class="font-medium">Ideas</h2>
      <RouterLink v-for="i in ideas" :key="i.id" :to="`/ideas/${i.id}`" class="card block hover:border-indigo-300">
        <div class="flex items-start justify-between gap-2"><h3 class="font-semibold">{{ i.name }}</h3><StatusBadge :status="i.status" /></div>
        <p class="mt-1 text-sm text-slate-600">{{ i.summary }}</p>
        <div class="mt-2 text-xs text-slate-500">Score {{ i.score ?? '—' }} · {{ i.evidence_ids.length }} source(s) · {{ i.pricing_model }}</div>
      </RouterLink>
      <p v-if="!ideas.length" class="card text-sm text-slate-500">No ideas yet — start an Agent 1 task.</p>
    </section>
    <section class="space-y-3">
      <div class="flex items-center justify-between gap-2">
        <h2 class="font-medium">Opportunities</h2>
        <select v-model="oppFilter" class="input w-40"><option value="">All</option><option>NEW</option><option>SHORTLISTED</option><option>DISMISSED</option></select>
      </div>
      <article v-for="o in opps" :key="o.id" class="card">
        <div class="flex items-start justify-between gap-2"><h3 class="font-medium">{{ o.title }}</h3><StatusBadge :status="o.status" /></div>
        <p class="mt-1 text-sm text-slate-600">{{ o.problem_statement }}</p>
        <div class="mt-2 flex flex-wrap items-center justify-between gap-2">
          <span class="text-xs text-slate-500">{{ o.industry }} · severity {{ o.pain_severity ?? '—' }}/5 · score {{ o.score ?? '—' }}</span>
          <span v-if="auth.canWrite()" class="flex gap-2">
            <button v-if="o.status === 'NEW'" class="btn-secondary" @click="setStatus(o, 'SHORTLISTED')">Shortlist</button>
            <button v-if="o.status !== 'DISMISSED'" class="btn-secondary" @click="setStatus(o, 'DISMISSED')">Dismiss</button>
            <button v-if="o.status !== 'NEW'" class="btn-secondary" @click="setStatus(o, 'NEW')">Reset</button>
          </span>
        </div>
      </article>
      <p v-if="!opps.length" class="card text-sm text-slate-500">None.</p>
    </section>
  </div>
</template>
