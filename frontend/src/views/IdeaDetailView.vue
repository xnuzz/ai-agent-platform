<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Approval, Evidence, Paginated, SoftwareIdea } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import LatestDecision from '@/components/LatestDecision.vue'
import LinesInput from '@/components/LinesInput.vue'
import Notice from '@/components/Notice.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { clone } from '@/components/format'
import { useAction } from '@/components/useAction'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ id: string }>()
const auth = useAuthStore()
const idea = ref<SoftwareIdea | null>(null)
const evidence = ref<Evidence[]>([])
const form = ref<Record<string, any>>({})
const summary = ref('')
const reviewKey = ref(0)
const { busy, error, notice, run } = useAction()

const FIELDS = ['name', 'summary', 'problem', 'solution', 'target_customers', 'pricing_model', 'differentiation', 'mvp_scope', 'key_features', 'risks'] as const
const editable = computed(() => auth.canWrite() && ['DRAFT', 'CHANGES_REQUESTED'].includes(idea.value?.status ?? ''))
const dirty = computed(() => idea.value != null && FIELDS.some((f) => JSON.stringify(form.value[f]) !== JSON.stringify((idea.value as any)[f])))

function reset(i: SoftwareIdea) {
  idea.value = i
  form.value = Object.fromEntries(FIELDS.map((f) => [f, clone((i as any)[f])]))
}
async function load() {
  reset(await api.get<SoftwareIdea>(`software-ideas/${props.id}/`))
  if (idea.value?.research_task) {
    evidence.value = (await api.get<Paginated<Evidence>>('evidence/', { research_task: idea.value.research_task, page_size: 100 })).results
      .filter((e) => idea.value!.evidence_ids.includes(e.id))
  }
}
onMounted(load)

const save = () => run(async () => reset(await api.patch<SoftwareIdea>(`software-ideas/${props.id}/`, form.value)), 'Saved.')
const submit = () => run(async () => {
  if (dirty.value) reset(await api.patch<SoftwareIdea>(`software-ideas/${props.id}/`, form.value))
  await api.post<Approval>(`software-ideas/${props.id}/submit/`, { summary: summary.value })
  summary.value = ''
  await load()
  reviewKey.value++
}, 'Submitted for approval.')

const labels: Record<string, string> = {
  problem: 'Problem', solution: 'Solution', target_customers: 'Target customers', pricing_model: 'Pricing model',
  differentiation: 'Differentiation', mvp_scope: 'MVP scope',
}
</script>

<template>
  <template v-if="idea">
    <PageHeader :title="idea.name" subtitle="Software idea · Agent 1">
      <RouterLink to="/ideas" class="btn-secondary">Back</RouterLink>
    </PageHeader>
    <ErrorBanner :message="error" />
    <div class="mb-4 flex flex-wrap items-center gap-3 text-sm">
      <StatusBadge :status="idea.status" /><span class="text-silver">Score {{ idea.score ?? '—' }}</span>
      <RouterLink v-if="idea.research_task" :to="`/tasks/${idea.research_task}`" class="text-ink">Source task</RouterLink>
      <span v-if="!editable && auth.canWrite()" class="text-xs text-silver">Locked — only DRAFT or CHANGES_REQUESTED ideas can be edited.</span>
      <Notice :notice="notice" />
    </div>
    <div class="grid gap-4 lg:grid-cols-3">
      <form class="card space-y-4 lg:col-span-2" @submit.prevent="save">
        <LatestDecision :target-id="idea.id" :refresh-key="reviewKey" />
        <fieldset :disabled="!editable" class="space-y-4">
          <div><label class="label">Name</label><input v-model="form.name" class="input" required maxlength="200" /></div>
          <div><label class="label">Summary</label><textarea v-model="form.summary" class="input" rows="3" required /></div>
          <div class="grid gap-4 md:grid-cols-2">
            <div v-for="(label, key) in labels" :key="key"><label class="label">{{ label }}</label><textarea v-model="form[key]" class="input" rows="3" /></div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div><label class="label">Key features</label><LinesInput v-model="form.key_features" :disabled="!editable" /></div>
            <div><label class="label">Risks</label><LinesInput v-model="form.risks" :disabled="!editable" /></div>
          </div>
        </fieldset>
        <div v-if="editable" class="flex flex-wrap items-center gap-3 border-t border-line pt-4">
          <button class="btn-secondary" :disabled="busy || !dirty">Save draft</button>
          <input v-model="summary" class="input max-w-sm" placeholder="Note for the reviewer (optional)" />
          <button type="button" class="btn-primary" :disabled="busy" @click="submit">Save &amp; submit for approval</button>
        </div>
      </form>
      <aside class="card">
        <h3 class="mb-2 text-sm font-medium">Evidence</h3>
        <ul class="space-y-2 text-sm">
          <li v-for="e in evidence" :key="e.id">
            <a :href="e.url" target="_blank" rel="noopener noreferrer" class="text-ink">{{ e.title || e.url }}</a>
            <span class="ml-1 text-xs text-muted">{{ e.source_type }}</span>
            <p v-if="e.excerpt" class="mt-0.5 text-xs text-silver">“{{ e.excerpt }}”</p>
          </li>
          <li v-if="!evidence.length" class="text-silver">No evidence linked.</li>
        </ul>
      </aside>
    </div>
  </template>
</template>
