<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Opportunity, Paginated, SoftwareIdea } from '@/api/types'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'

const ideas = ref<SoftwareIdea[]>([])
const opps = ref<Opportunity[]>([])
onMounted(async () => {
  ideas.value = (await api.get<Paginated<SoftwareIdea>>('software-ideas/', { ordering: '-score' })).results
  opps.value = (await api.get<Paginated<Opportunity>>('opportunities/', { ordering: '-score' })).results
})
</script>

<template>
  <PageHeader title="Software ideas" subtitle="Agent 1 output: evidence-backed opportunities and product ideas." />
  <div class="grid gap-4 lg:grid-cols-2">
    <section class="space-y-3">
      <h2 class="font-medium">Ideas</h2>
      <article v-for="i in ideas" :key="i.id" class="card">
        <div class="flex items-start justify-between gap-2"><h3 class="font-semibold">{{ i.name }}</h3><StatusBadge :status="i.status" /></div>
        <p class="mt-1 text-sm text-slate-600">{{ i.summary }}</p>
        <div class="mt-2 text-xs text-slate-500">Score {{ i.score ?? '—' }} · {{ i.evidence_ids.length }} source(s) · {{ i.pricing_model }}</div>
      </article>
      <p v-if="!ideas.length" class="card text-sm text-slate-500">No ideas yet — start an Agent 1 task.</p>
    </section>
    <section class="space-y-3">
      <h2 class="font-medium">Opportunities</h2>
      <article v-for="o in opps" :key="o.id" class="card">
        <div class="flex items-start justify-between gap-2"><h3 class="font-medium">{{ o.title }}</h3><StatusBadge :status="o.status" /></div>
        <p class="mt-1 text-sm text-slate-600">{{ o.problem_statement }}</p>
        <div class="mt-2 text-xs text-slate-500">{{ o.industry }} · severity {{ o.pain_severity ?? '—' }}/5 · score {{ o.score ?? '—' }}</div>
      </article>
    </section>
  </div>
</template>
