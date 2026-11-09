<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { errorText } from '@/api/client'
import ErrorBanner from '@/components/ErrorBanner.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const mode = ref<'login' | 'register'>('login')
const form = ref({ email: '', password: '', full_name: '', workspace_name: '' })
const error = ref<string | null>(null)
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = null
  try {
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
  <div class="flex min-h-screen items-center justify-center px-4">
    <form class="card w-full max-w-sm space-y-4" @submit.prevent="submit">
      <h1 class="text-xl font-semibold">{{ mode === 'login' ? 'Sign in' : 'Create account' }}</h1>
      <ErrorBanner :message="error" />
      <div><label class="label">Email</label><input v-model="form.email" type="email" required class="input" autocomplete="email" /></div>
      <div><label class="label">Password</label><input v-model="form.password" type="password" required class="input" autocomplete="current-password" /></div>
      <template v-if="mode === 'register'">
        <div><label class="label">Full name</label><input v-model="form.full_name" class="input" /></div>
        <div><label class="label">Workspace name</label><input v-model="form.workspace_name" required class="input" /></div>
      </template>
      <button class="btn-primary w-full justify-center" :disabled="busy">{{ mode === 'login' ? 'Sign in' : 'Create account' }}</button>
      <button type="button" class="w-full text-center text-sm text-indigo-600" @click="mode = mode === 'login' ? 'register' : 'login'">
        {{ mode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in' }}
      </button>
    </form>
  </div>
</template>
