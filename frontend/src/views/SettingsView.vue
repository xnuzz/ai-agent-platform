<script setup lang="ts">
import { ref } from 'vue'
import { api, errorText } from '@/api/client'
import ErrorBanner from '@/components/ErrorBanner.vue'
import IntegrationsPanel from '@/components/IntegrationsPanel.vue'
import MembersPanel from '@/components/MembersPanel.vue'
import PrivacyPanel from '@/components/PrivacyPanel.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const ws = auth.current!
const form = ref({
  name: ws.name, sender_name: ws.sender_name ?? '', sender_email: ws.sender_email ?? '', reply_to_email: ws.reply_to_email ?? '',
  sender_company: ws.sender_company ?? '', sender_postal_address: ws.sender_postal_address ?? '',
  consent_required_countries: ((ws.consent_required_countries as string[] | undefined) ?? []).join(', '),
  daily_send_limit: ws.daily_send_limit ?? 100,
  data_retention_days: ws.data_retention_days ?? 365,
})
const error = ref<string | null>(null)
const saved = ref(false)
const tab = ref<'workspace' | 'members' | 'integrations' | 'privacy'>('workspace')

async function save() {
  error.value = null
  saved.value = false
  try {
    await api.patch(`workspaces/${ws.id}/`, {
      ...form.value,
      consent_required_countries: form.value.consent_required_countries.split(',').map((s) => s.trim()).filter(Boolean),
    })
    await auth.refreshWorkspace()
    saved.value = true
  } catch (e) { error.value = errorText(e) }
}
</script>

<template>
  <PageHeader title="Settings" subtitle="Sender identity is required before any campaign can launch." />
  <div class="mb-4 flex gap-2">
    <button v-for="t in (['workspace', 'members', 'integrations', 'privacy'] as const)" :key="t" :class="tab === t ? 'btn-primary' : 'btn-secondary'" class="capitalize" @click="tab = t">{{ t }}</button>
  </div>
  <MembersPanel v-if="tab === 'members'" />
  <IntegrationsPanel v-else-if="tab === 'integrations'" />
  <PrivacyPanel v-else-if="tab === 'privacy'" />
  <ErrorBanner v-if="tab === 'workspace'" :message="error" />
  <form v-if="tab === 'workspace'" class="card max-w-2xl space-y-4" @submit.prevent="save">
    <fieldset :disabled="!auth.isAdmin()" class="grid gap-4 md:grid-cols-2">
      <div class="md:col-span-2"><label class="label">Workspace name</label><input v-model="form.name" class="input" /></div>
      <div><label class="label">Sender name</label><input v-model="form.sender_name" class="input" /></div>
      <div><label class="label">Sender email</label><input v-model="form.sender_email" type="email" class="input" /></div>
      <div><label class="label">Reply-to email</label><input v-model="form.reply_to_email" type="email" class="input" /></div>
      <div><label class="label">Company (legal name)</label><input v-model="form.sender_company" class="input" /></div>
      <div class="md:col-span-2"><label class="label">Postal address (shown in every email)</label><textarea v-model="form.sender_postal_address" rows="2" class="input" /></div>
      <div><label class="label">Countries requiring consent (ISO, comma)</label><input v-model="form.consent_required_countries" class="input" placeholder="DE, AT" /></div>
      <div><label class="label">Daily send limit</label><input v-model.number="form.daily_send_limit" type="number" min="0" class="input" /></div>
      <div><label class="label">Data retention (days, 0 = off)</label><input v-model.number="form.data_retention_days" type="number" min="0" class="input" />
        <p class="mt-1 text-xs text-slate-500">Contact data on idle leads that were never contacted is anonymized after this period.</p></div>
    </fieldset>
    <div class="flex items-center gap-3">
      <button v-if="auth.isAdmin()" class="btn-primary">Save</button>
      <span v-else class="text-sm text-slate-500">Only admins can change settings.</span>
      <span v-if="saved" class="text-sm text-emerald-700">Saved.</span>
      <span class="text-xs" :class="auth.current?.sender_identity_complete ? 'text-emerald-700' : 'text-amber-700'">
        Sender identity {{ auth.current?.sender_identity_complete ? 'complete' : 'incomplete' }}
      </span>
    </div>
  </form>
</template>
