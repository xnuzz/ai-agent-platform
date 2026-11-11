<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import type { ProjectBrief } from '@/api/types'
import ErrorBanner from './ErrorBanner.vue'
import LatestDecision from './LatestDecision.vue'
import LinesInput from './LinesInput.vue'
import Notice from './Notice.vue'
import StatusBadge from './StatusBadge.vue'
import { clone } from './format'
import { useAction } from './useAction'

const props = defineProps<{ brief: ProjectBrief; canWrite: boolean }>()
const emit = defineEmits<{ changed: [ProjectBrief] }>()
const FIELDS = ['title', 'summary', 'proposed_solution', 'scope_items', 'tech_stack', 'estimated_effort_hours_min',
  'estimated_effort_hours_max', 'estimated_budget_min', 'estimated_budget_max', 'currency'] as const
const pick = (b: ProjectBrief) => Object.fromEntries(FIELDS.map((f) => [f, clone((b as any)[f])]))
const form = ref<Record<string, any>>(pick(props.brief))
const note = ref('')
const reviewKey = ref(0)
const { busy, error, notice, run } = useAction()
const editable = computed(() => props.canWrite && ['DRAFT', 'CHANGES_REQUESTED'].includes(props.brief.status ?? ''))
const dirty = computed(() => FIELDS.some((f) => JSON.stringify(form.value[f]) !== JSON.stringify((props.brief as any)[f])))

function payload() {
  const p = { ...form.value }
  for (const k of ['estimated_effort_hours_min', 'estimated_effort_hours_max', 'estimated_budget_min', 'estimated_budget_max']) {
    if (p[k] === '' || p[k] === undefined) p[k] = null
  }
  p.currency = (p.currency ?? '').toUpperCase()
  return p
}
async function persist() {
  const b = await api.patch<ProjectBrief>(`project-briefs/${props.brief.id}/`, payload())
  form.value = pick(b)
  emit('changed', b)
  return b
}
const save = () => run(persist, 'Saved.')
const submit = () => run(async () => {
  if (dirty.value) await persist()
  await api.post(`project-briefs/${props.brief.id}/submit/`, { summary: note.value })
  emit('changed', await api.get<ProjectBrief>(`project-briefs/${props.brief.id}/`))
  note.value = ''
  reviewKey.value++
}, 'Submitted for approval.')
const decided = () => run(async () => {
  const b = await api.get<ProjectBrief>(`project-briefs/${props.brief.id}/`)
  form.value = pick(b)
  emit('changed', b)
}, 'Decision recorded.')
</script>

<template>
  <form class="card space-y-4" @submit.prevent="save">
    <div class="flex items-center justify-between gap-2">
      <h3 class="font-semibold">Project brief</h3>
      <span class="flex items-center gap-3"><Notice :notice="notice" /><StatusBadge :status="brief.status" /></span>
    </div>
    <LatestDecision :target-id="brief.id" :refresh-key="reviewKey" :can-decide="canWrite" @decided="decided" />
    <ErrorBanner :message="error" />
    <fieldset :disabled="!editable" class="space-y-4">
      <div><label class="label">Title</label><input v-model="form.title" class="input" required maxlength="300" /></div>
      <div><label class="label">Summary</label><textarea v-model="form.summary" class="input" rows="3" required /></div>
      <div><label class="label">Proposed solution</label><textarea v-model="form.proposed_solution" class="input" rows="3" /></div>
      <div class="grid gap-4 md:grid-cols-2">
        <div><label class="label">Scope items</label><LinesInput v-model="form.scope_items" :disabled="!editable" /></div>
        <div><label class="label">Tech stack</label><LinesInput v-model="form.tech_stack" :disabled="!editable" /></div>
      </div>
      <div class="grid gap-4 md:grid-cols-5">
        <div><label class="label">Effort min (h)</label><input v-model.number="form.estimated_effort_hours_min" type="number" min="0" class="input" /></div>
        <div><label class="label">Effort max (h)</label><input v-model.number="form.estimated_effort_hours_max" type="number" min="0" class="input" /></div>
        <div><label class="label">Budget min</label><input v-model="form.estimated_budget_min" type="number" min="0" step="0.01" class="input" /></div>
        <div><label class="label">Budget max</label><input v-model="form.estimated_budget_max" type="number" min="0" step="0.01" class="input" /></div>
        <div><label class="label">Currency</label><input v-model="form.currency" maxlength="3" class="input uppercase" placeholder="EUR" /></div>
      </div>
    </fieldset>
    <div v-if="(brief.problems as any[]).length" class="text-sm">
      <div class="label">Detected problems (from agent)</div>
      <ul class="space-y-1"><li v-for="p in (brief.problems as any[])" :key="p.code"><StatusBadge :status="p.severity" /> <span class="font-mono text-xs">{{ p.code }}</span> {{ p.title }}</li></ul>
    </div>
    <div v-if="editable" class="flex flex-wrap items-center gap-3 border-t border-line pt-4">
      <button class="btn-secondary" :disabled="busy || !dirty">Save draft</button>
      <input v-model="note" class="input max-w-xs" placeholder="Note for the reviewer (optional)" />
      <button type="button" class="btn-primary" :disabled="busy" @click="submit">Save &amp; submit for approval</button>
    </div>
    <p v-else-if="canWrite" class="text-xs text-silver">Locked — only DRAFT or CHANGES_REQUESTED briefs can be edited.</p>
  </form>
</template>
