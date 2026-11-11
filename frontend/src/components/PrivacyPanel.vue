<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'
import ErrorBanner from './ErrorBanner.vue'
import Notice from './Notice.vue'
import { useAction } from './useAction'
import { useAuthStore } from '@/stores/auth'

type EraseResult = { leads_anonymized: number; messages_redacted: number; businesses_updated: number }
const auth = useAuthStore()
const exportEmail = ref('')
const eraseEmail = ref('')
const eraseConfirm = ref('')
const result = ref<EraseResult | null>(null)
const { busy, error, notice, run } = useAction()

const doExport = () => run(async () => {
  const data = await api.post<Record<string, unknown>>('privacy/export/', { email: exportEmail.value })
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `personal-data-export-${Date.now()}.json` })
  a.click()
  URL.revokeObjectURL(a.href)
}, 'Export downloaded.')

const doErase = () => run(async () => {
  result.value = await api.post<EraseResult>('privacy/erase/', { email: eraseEmail.value, confirm: true })
  eraseEmail.value = eraseConfirm.value = ''
}, 'Erasure completed.')
</script>

<template>
  <section class="max-w-2xl space-y-4">
    <ErrorBanner :message="error" />
    <p v-if="!auth.isAdmin()" class="card text-sm text-silver">Only workspace admins can handle data-subject requests.</p>
    <template v-else>
      <form class="card space-y-3" @submit.prevent="doExport">
        <h3 class="font-semibold">Access request (export)</h3>
        <p class="text-sm text-silver">Downloads every lead, outreach message, business record and suppression entry in this workspace that contains the address.</p>
        <div class="flex gap-3"><input v-model="exportEmail" type="email" required class="input" placeholder="person@company.com" />
          <button class="btn-primary whitespace-nowrap" :disabled="busy">Export JSON</button></div>
      </form>
      <form class="card space-y-3 border-bad/30" @submit.prevent="doErase">
        <h3 class="font-semibold text-bad">Erasure request</h3>
        <p class="text-sm text-silver">Anonymizes lead contact data, redacts messages, clears the address from businesses and cancels pending outreach.
          The address is kept <strong>only</strong> on the suppression list so it is never contacted again. This cannot be undone.</p>
        <input v-model="eraseEmail" type="email" required class="input" placeholder="person@company.com" />
        <input v-model="eraseConfirm" type="email" required class="input" placeholder="Type the address again to confirm" />
        <div class="flex items-center gap-3">
          <button class="btn-danger" :disabled="busy || !eraseEmail || eraseEmail.toLowerCase() !== eraseConfirm.toLowerCase()">Erase personal data</button>
          <span v-if="result" class="text-sm text-silver">{{ result.leads_anonymized }} lead(s), {{ result.messages_redacted }} message(s), {{ result.businesses_updated }} business(es) updated.</span>
        </div>
      </form>
      <Notice :notice="notice" />
      <p class="text-xs text-silver">Both actions are recorded in the audit log by a pseudonymous reference, never the address itself.</p>
    </template>
  </section>
</template>
