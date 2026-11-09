<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import ErrorBanner from './ErrorBanner.vue'
import { useAction } from './useAction'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const form = ref({ current_password: '', new_password: '', repeat: '' })
const { busy, error, run } = useAction()
const change = () => run(async () => {
  if (form.value.new_password !== form.value.repeat) throw new Error('New passwords do not match.')
  await api.post('auth/password/change/', { current_password: form.value.current_password, new_password: form.value.new_password })
  auth.logout()
  router.push({ name: 'login' })
})
</script>

<template>
  <form class="card max-w-md space-y-4" @submit.prevent="change">
    <h3 class="font-semibold">Change password</h3>
    <p class="text-sm text-slate-600">Signed in as {{ auth.user?.email }}. Changing your password signs out every session, including this one.</p>
    <ErrorBanner :message="error" />
    <div><label class="label">Current password</label><input v-model="form.current_password" type="password" required autocomplete="current-password" class="input" /></div>
    <div><label class="label">New password</label><input v-model="form.new_password" type="password" required minlength="10" autocomplete="new-password" class="input" /></div>
    <div><label class="label">Repeat new password</label><input v-model="form.repeat" type="password" required autocomplete="new-password" class="input" /></div>
    <button class="btn-primary" :disabled="busy">Change password</button>
  </form>
</template>
