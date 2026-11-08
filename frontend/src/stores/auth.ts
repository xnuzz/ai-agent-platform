import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, request, session } from '@/api/client'
import type { User, Workspace, Paginated } from '@/api/types'

const WS_KEY = 'platform.workspace'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const workspaces = ref<Workspace[]>([])
  const current = ref<Workspace | null>(null)

  async function login(email: string, password: string) {
    const t = await request<{ access: string; refresh: string }>('POST', 'auth/token/', { email, password }, { auth: false })
    session.setTokens(t)
    await bootstrap()
  }

  async function register(payload: { email: string; password: string; full_name?: string; workspace_name: string }) {
    await request('POST', 'auth/register/', payload, { auth: false })
    await login(payload.email, payload.password)
  }

  async function bootstrap() {
    if (!session.hasTokens()) return
    user.value = await api.get<User>('auth/me/')
    workspaces.value = (await api.get<Paginated<Workspace>>('workspaces/')).results
    const saved = localStorage.getItem(WS_KEY)
    selectWorkspace(workspaces.value.find((w) => w.id === saved) ?? workspaces.value[0] ?? null)
  }

  function selectWorkspace(ws: Workspace | null) {
    current.value = ws
    session.setWorkspace(ws?.id ?? null)
    if (ws) localStorage.setItem(WS_KEY, ws.id)
  }

  async function refreshWorkspace() {
    if (!current.value) return
    const ws = await api.get<Workspace>(`workspaces/${current.value.id}/`)
    workspaces.value = workspaces.value.map((w) => (w.id === ws.id ? ws : w))
    current.value = ws
  }

  function logout() {
    session.setTokens(null)
    user.value = null
    selectWorkspace(null)
  }

  const canWrite = () => ['OWNER', 'ADMIN', 'DEVELOPER'].includes(current.value?.role ?? '')
  const isAdmin = () => ['OWNER', 'ADMIN'].includes(current.value?.role ?? '')

  return { user, workspaces, current, login, register, bootstrap, selectWorkspace, refreshWorkspace, logout, canWrite, isAdmin }
})
