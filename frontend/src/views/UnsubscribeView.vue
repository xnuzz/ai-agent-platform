<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, errorText } from '@/api/client'

type Info = { email_masked: string; sender: string; already_unsubscribed: boolean }
const token = useRoute().params.token as string
const info = ref<Info | null>(null)
const done = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  try { info.value = await api.public.get<Info>(`public/unsubscribe/${token}/`); done.value = info.value.already_unsubscribed }
  catch (e) { error.value = errorText(e) }
})
async function confirmOptOut() {
  try { await api.public.post(`public/unsubscribe/${token}/`); done.value = true } catch (e) { error.value = errorText(e) }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center px-4">
    <div class="card w-full max-w-md space-y-4 text-center">
      <h1 class="text-xl font-semibold">Unsubscribe</h1>
      <p v-if="error" class="text-sm text-rose-700">{{ error }}</p>
      <template v-else-if="info">
        <p v-if="done" class="text-sm">{{ info.email_masked }} will not receive further messages from {{ info.sender || 'this sender' }}.</p>
        <template v-else>
          <p class="text-sm">Stop all further messages from <strong>{{ info.sender }}</strong> to {{ info.email_masked }}?</p>
          <button class="btn-primary" @click="confirmOptOut">Unsubscribe</button>
        </template>
      </template>
    </div>
  </div>
</template>
