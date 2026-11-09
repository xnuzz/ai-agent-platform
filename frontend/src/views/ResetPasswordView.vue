<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import ErrorBanner from '@/components/ErrorBanner.vue'
import { useAction } from '@/components/useAction'

const route = useRoute()
const uid = computed(() => (route.query.uid as string) ?? '')
const token = computed(() => (route.query.token as string) ?? '')
const password = ref('')
const confirm = ref('')
const done = ref(false)
const { busy, error, run } = useAction()

const submit = () => run(async () => {
  if (password.value !== confirm.value) throw new Error('Passwords do not match.')
  await api.public.post('auth/password-reset/confirm/', { uid: uid.value, token: token.value, new_password: password.value })
  done.value = true
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center px-4">
    <form class="card w-full max-w-sm space-y-4" @submit.prevent="submit">
      <h1 class="text-xl font-semibold">Choose a new password</h1>
      <template v-if="done">
        <p class="text-sm">Your password was changed and all other sessions were signed out.</p>
        <RouterLink to="/login" class="btn-primary w-full justify-center">Sign in</RouterLink>
      </template>
      <template v-else-if="!uid || !token">
        <p class="text-sm text-rose-700">This link is incomplete. Request a new one from the sign-in page.</p>
      </template>
      <template v-else>
        <ErrorBanner :message="error" />
        <div><label class="label">New password</label><input v-model="password" type="password" required minlength="10" autocomplete="new-password" class="input" /></div>
        <div><label class="label">Repeat password</label><input v-model="confirm" type="password" required autocomplete="new-password" class="input" /></div>
        <button class="btn-primary w-full justify-center" :disabled="busy">Set password</button>
      </template>
    </form>
  </div>
</template>
