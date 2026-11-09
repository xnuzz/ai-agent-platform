<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Integration, Paginated } from '@/api/types'
import ErrorBanner from './ErrorBanner.vue'
import Notice from './Notice.vue'
import StatusBadge from './StatusBadge.vue'
import { fmtDate } from './format'
import { useAction } from './useAction'
import { useAuthStore } from '@/stores/auth'

type Form = { id?: string; kind: string; provider: string; name: string; status: string; configText: string; secret: string }
const auth = useAuthStore()
const items = ref<Integration[]>([])
const form = ref<Form | null>(null)
const { busy, error, notice, run } = useAction()
const KINDS = ['EMAIL', 'LLM', 'SEARCH', 'MAPS', 'CRM']
const PROVIDERS = ['SMTP', 'ANTHROPIC', 'OPENAI', 'GOOGLE_PLACES', 'SERPAPI', 'HUBSPOT', 'OTHER']
const SMTP_TEMPLATE = JSON.stringify({ host: 'smtp.example.com', port: 587, username: 'user@example.com', use_tls: true }, null, 2)

const load = async () => { items.value = (await api.get<Paginated<Integration>>('integrations/', { page_size: 100 })).results }
onMounted(load)

function newForm() { form.value = { kind: 'EMAIL', provider: 'SMTP', name: '', status: 'ACTIVE', configText: SMTP_TEMPLATE, secret: '' } }
function editForm(i: Integration) {
  form.value = { id: i.id, kind: i.kind, provider: i.provider, name: i.name, status: i.status ?? 'ACTIVE', configText: JSON.stringify(i.config ?? {}, null, 2), secret: '' }
}
const save = () => run(async () => {
  const f = form.value!
  let config: unknown
  try { config = JSON.parse(f.configText || '{}') } catch { throw new Error('Config must be valid JSON.') }
  const body: Record<string, unknown> = { kind: f.kind, provider: f.provider, name: f.name, status: f.status, config }
  if (f.secret) body.secret = f.secret  // write-only; omitted = keep existing secret
  if (f.id) await api.patch(`integrations/${f.id}/`, body)
  else await api.post('integrations/', body)
  form.value = null
  await load()
}, 'Integration saved.')
const remove = (i: Integration) => {
  if (!confirm(`Delete integration "${i.name}"? Its stored secret is destroyed.`)) return
  run(async () => { await api.del(`integrations/${i.id}/`); await load() }, 'Integration deleted.')
}
</script>

<template>
  <section class="max-w-3xl space-y-4">
    <ErrorBanner :message="error" />
    <div class="card overflow-x-auto p-0">
      <table class="table">
        <thead><tr><th>Name</th><th>Kind / provider</th><th>Secret</th><th>Status</th><th>Updated</th><th /></tr></thead>
        <tbody>
          <tr v-for="i in items" :key="i.id">
            <td class="font-medium">{{ i.name }}</td><td class="text-xs">{{ i.kind }} · {{ i.provider }}</td>
            <td class="text-xs">{{ i.has_secret ? 'stored (hidden)' : 'none' }}</td><td><StatusBadge :status="i.status" /></td>
            <td class="text-xs text-slate-500">{{ fmtDate(i.updated_at) }}</td>
            <td class="text-right whitespace-nowrap"><template v-if="auth.isAdmin()">
              <button class="mr-3 text-xs text-indigo-600" @click="editForm(i)">Edit</button><button class="text-xs text-rose-600" @click="remove(i)">Delete</button></template></td>
          </tr>
          <tr v-if="!items.length"><td colspan="6" class="py-6 text-center text-slate-500">No integrations. Outreach uses the platform's default mail transport.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="flex items-center gap-3"><button v-if="auth.isAdmin() && !form" class="btn-primary" @click="newForm">Add integration</button><Notice :notice="notice" /></div>
    <form v-if="form" class="card space-y-4" @submit.prevent="save">
      <h3 class="font-semibold">{{ form.id ? 'Edit integration' : 'New integration' }}</h3>
      <div class="grid gap-4 md:grid-cols-4">
        <div class="md:col-span-2"><label class="label">Name</label><input v-model="form.name" required class="input" /></div>
        <div><label class="label">Kind</label><select v-model="form.kind" class="input"><option v-for="k in KINDS" :key="k">{{ k }}</option></select></div>
        <div><label class="label">Provider</label><select v-model="form.provider" class="input"><option v-for="p in PROVIDERS" :key="p">{{ p }}</option></select></div>
        <div><label class="label">Status</label><select v-model="form.status" class="input"><option>ACTIVE</option><option>DISABLED</option></select></div>
      </div>
      <div><label class="label">Config (JSON, non-secret only)</label><textarea v-model="form.configText" rows="6" class="input font-mono text-xs" /></div>
      <div><label class="label">Secret (password / API key) — write-only, encrypted at rest{{ form.id ? '; leave empty to keep current' : '' }}</label>
        <input v-model="form.secret" type="password" autocomplete="new-password" class="input" /></div>
      <p v-if="form.kind === 'EMAIL' && form.provider === 'SMTP'" class="text-xs text-slate-500">An ACTIVE SMTP integration is used for all outreach sent from this workspace.</p>
      <div class="flex gap-2"><button class="btn-primary" :disabled="busy">Save</button><button type="button" class="btn-secondary" @click="form = null">Cancel</button></div>
    </form>
  </section>
</template>
