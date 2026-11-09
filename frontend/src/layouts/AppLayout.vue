<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const nav = [
  { to: '/', label: 'Dashboard' },
  { to: '/local-finder', label: 'Local Business Finder' },
  { to: '/tasks', label: 'Agent tasks' },
  { to: '/approvals', label: 'Approval center' },
  { to: '/ideas', label: 'Software ideas' },
  { to: '/leads', label: 'Leads & briefs' },
  { to: '/campaigns', label: 'Campaigns' },
  { to: '/suppression', label: 'Suppression list' },
  { to: '/settings', label: 'Settings' },
  { to: '/audit', label: 'Audit log', admin: true },
]
const wsId = computed({
  get: () => auth.current?.id ?? '',
  set: (id: string) => auth.selectWorkspace(auth.workspaces.find((w) => w.id === id) ?? null),
})
async function logout() { await auth.logout(true); router.push({ name: 'login' }) }
</script>

<template>
  <div class="flex min-h-screen">
    <aside class="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white px-4 py-6">
      <div class="mb-6 px-2 text-lg font-semibold">Agent Platform</div>
      <label class="label px-2">Workspace</label>
      <select v-model="wsId" class="input mb-6">
        <option v-for="w in auth.workspaces" :key="w.id" :value="w.id">{{ w.name }}</option>
      </select>
      <nav class="flex flex-1 flex-col gap-1">
        <RouterLink v-for="n in nav.filter((x) => !x.admin || auth.isAdmin())" :key="n.to" :to="n.to"
          class="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
          :active-class="n.to === '/' ? '' : 'bg-indigo-50 font-medium text-indigo-700'" exact-active-class="bg-indigo-50 font-medium text-indigo-700">{{ n.label }}</RouterLink>
      </nav>
      <div class="border-t border-slate-200 pt-4 text-xs text-slate-500">
        <div class="truncate">{{ auth.user?.email }}</div>
        <div class="mb-2">Role: {{ auth.current?.role }}</div>
        <button class="btn-secondary w-full justify-center" @click="logout">Sign out</button>
      </div>
    </aside>
    <main class="min-w-0 flex-1 px-8 py-8">
      <div v-if="!auth.current" class="card">No workspace. Ask an admin for access.</div>
      <RouterView v-else :key="auth.current.id" />
    </main>
  </div>
</template>
