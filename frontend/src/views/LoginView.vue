<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorText } from '@/api/client'
import BrandMark from '@/components/BrandMark.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const mode = ref<'login' | 'register' | 'forgot'>('login')
const resetSent = ref(false)
const form = ref({ email: '', password: '', full_name: '', workspace_name: '' })
const error = ref<string | null>(null)
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = null
  try {
    if (mode.value === 'forgot') {
      await api.public.post('auth/password-reset/', { email: form.value.email })
      resetSent.value = true
      return
    }
    if (mode.value === 'login') await auth.login(form.value.email, form.value.password)
    else await auth.register(form.value)
    router.push((route.query.next as string) || '/')
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
    <div class="fade-in mb-8 flex flex-col items-center text-center">
      <BrandMark :size="52" />
      <h1 class="mt-5 text-[28px] font-semibold tracking-tight">Agent Platform</h1>
      <p class="mt-1.5 text-sm text-silver">Autonomous research agents. Human approval on every step.</p>
    </div>
    <form class="glass-pop fade-in w-full max-w-sm space-y-4 rounded-[var(--radius-lg)] p-6" style="animation-delay: 80ms" @submit.prevent="submit">
      <h2 class="text-lg font-semibold">{{ { login: 'Sign in', register: 'Create account', forgot: 'Reset password' }[mode] }}</h2>
      <ErrorBanner :message="error" />
      <p v-if="mode === 'forgot' && resetSent" class="text-sm text-soft">If an account exists for {{ form.email }}, a reset link is on its way. It expires in one hour.</p>
      <template v-else>
        <div><label class="label">Email</label><input v-model="form.email" type="email" required class="input" autocomplete="email" /></div>
        <div v-if="mode !== 'forgot'"><label class="label">Password</label><input v-model="form.password" type="password" required class="input" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" /></div>
        <template v-if="mode === 'register'">
          <div><label class="label">Full name</label><input v-model="form.full_name" class="input" /></div>
          <div><label class="label">Workspace name</label><input v-model="form.workspace_name" required class="input" /></div>
        </template>
        <button class="btn-primary w-full justify-center py-2" :disabled="busy">{{ { login: 'Sign in', register: 'Create account', forgot: 'Send reset link' }[mode] }}</button>
      </template>
      <div class="flex justify-between gap-3 border-t border-line pt-4 text-sm">
        <button type="button" class="text-ink hover:underline underline-offset-4" @click="mode = mode === 'login' ? 'register' : 'login'; resetSent = false">
          {{ mode === 'login' ? 'Need an account? Register' : 'Back to sign in' }}
        </button>
        <button v-if="mode === 'login'" type="button" class="text-silver hover:text-ink" @click="mode = 'forgot'">Forgot password?</button>
      </div>
    </form>
  </div>
</template>
