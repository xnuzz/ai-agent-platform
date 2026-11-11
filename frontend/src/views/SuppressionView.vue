<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, errorText } from '@/api/client'
import type { Paginated, SuppressionEntry } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import PageHeader from '@/components/PageHeader.vue'
import { fmtDate } from '@/components/format'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const entries = ref<SuppressionEntry[]>([])
const form = ref({ type: 'EMAIL', value: '', reason: 'MANUAL', note: '' })
const error = ref<string | null>(null)
const load = async () => { entries.value = (await api.get<Paginated<SuppressionEntry>>('suppression-entries/', { page_size: 100 })).results }
onMounted(load)

async function add() {
  error.value = null
  try { await api.post('suppression-entries/', form.value); form.value.value = ''; form.value.note = ''; await load() }
  catch (e) { error.value = errorText(e) }
}
async function remove(id: string) {
  if (!confirm('Allow contacting this recipient again? This is audited.')) return
  try { await api.del(`suppression-entries/${id}/`); await load() } catch (e) { error.value = errorText(e) }
}
</script>

<template>
  <PageHeader title="Suppression list" subtitle="Never contacted again. Checked when drafts are created and right before every send." />
  <ErrorBanner :message="error" />
  <form v-if="auth.canWrite()" class="card mb-6 grid gap-3 md:grid-cols-5" @submit.prevent="add">
    <select v-model="form.type" class="input"><option>EMAIL</option><option>DOMAIN</option><option>PHONE</option></select>
    <input v-model="form.value" required class="input md:col-span-2" placeholder="person@company.com / company.com / +359…" />
    <select v-model="form.reason" class="input"><option>MANUAL</option><option>OPT_OUT</option><option>LEGAL_REQUEST</option><option>COMPLAINT</option><option>BOUNCE</option></select>
    <button class="btn-primary justify-center">Add</button>
  </form>
  <div class="card overflow-x-auto p-0">
    <table class="table">
      <thead><tr><th>Type</th><th>Value</th><th>Reason</th><th>Source</th><th>Added</th><th /></tr></thead>
      <tbody>
        <tr v-for="e in entries" :key="e.id">
          <td>{{ e.type }}</td><td class="font-mono text-xs">{{ e.value }}</td><td>{{ e.reason }}</td><td class="text-xs">{{ e.source }}</td><td class="text-silver">{{ fmtDate(e.created_at) }}</td>
          <td><button v-if="auth.isAdmin()" class="text-xs text-bad" @click="remove(e.id)">Remove</button></td>
        </tr>
        <tr v-if="!entries.length"><td colspan="6" class="py-8 text-center text-silver">Empty.</td></tr>
      </tbody>
    </table>
  </div>
</template>
