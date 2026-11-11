<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon, { type IconName } from '@/components/AppIcon.vue'
import BrandMark from '@/components/BrandMark.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const NAV_KEY = 'platform.nav.collapsed'
const nav: { to: string; label: string; icon: IconName; admin?: boolean }[] = [
  { to: '/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/local-finder', label: 'Local Business Finder', icon: 'finder' },
  { to: '/tasks', label: 'Agent tasks', icon: 'tasks' },
  { to: '/approvals', label: 'Approval center', icon: 'approvals' },
  { to: '/ideas', label: 'Software ideas', icon: 'ideas' },
  { to: '/leads', label: 'Leads & briefs', icon: 'leads' },
  { to: '/campaigns', label: 'Campaigns', icon: 'campaigns' },
  { to: '/suppression', label: 'Suppression list', icon: 'suppression' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
  { to: '/audit', label: 'Audit log', icon: 'audit', admin: true },
]
const collapsed = ref(read())
const drawer = ref(false) // mobile
function read() { try { return localStorage.getItem(NAV_KEY) === '1' } catch { return false } }
function toggle() {
  collapsed.value = !collapsed.value
  try { localStorage.setItem(NAV_KEY, collapsed.value ? '1' : '0') } catch { /* storage unavailable */ }
}
watch(() => route.fullPath, () => { drawer.value = false })

const wsId = computed({
  get: () => auth.current?.id ?? '',
  set: (id: string) => auth.selectWorkspace(auth.workspaces.find((w) => w.id === id) ?? null),
})
const initials = computed(() => (auth.user?.full_name || auth.user?.email || '?').split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join(''))
const isActive = (to: string) => (to === '/' ? route.path === '/' : route.path.startsWith(to))
async function logout() { await auth.logout(true); router.push({ name: 'login' }) }
</script>

<template>
  <div class="min-h-dvh">
    <!-- mobile bar -->
    <header class="glass-nav sticky top-0 z-30 flex h-14 items-center gap-3 border-x-0 border-t-0 px-4 lg:hidden">
      <button type="button" class="btn-ghost -ml-2 px-2" aria-label="Open navigation" :aria-expanded="drawer" @click="drawer = true"><AppIcon name="menu" /></button>
      <span class="text-sm font-semibold text-ink">Agent Platform</span>
    </header>
    <Transition name="fade"><div v-if="drawer" class="fixed inset-0 z-40 bg-black/60 lg:hidden" aria-hidden="true" @click="drawer = false" /></Transition>

    <aside class="glass-nav max-lg:bg-panel-3 fixed top-3 bottom-3 left-3 z-50 flex flex-col rounded-[var(--radius-lg)] p-3 transition-[width,transform] duration-300 ease-out-soft lg:translate-x-0"
      :class="[collapsed ? 'lg:w-[76px]' : 'lg:w-[248px]', drawer ? 'w-[264px] translate-x-0' : 'w-[264px] -translate-x-[calc(100%+1rem)]']" aria-label="Primary">
      <div class="mb-5 flex items-center gap-2.5 px-1.5 pt-1" :class="{ 'lg:flex-col lg:px-0': collapsed && !drawer }">
        <BrandMark />
        <span v-show="!collapsed || drawer" class="truncate text-[15px] font-semibold tracking-tight text-ink">Agent Platform</span>
        <button type="button" class="btn-ghost hidden px-1.5 lg:inline-flex" :class="collapsed ? 'lg:ml-0' : 'ml-auto'" :aria-label="collapsed ? 'Expand sidebar' : 'Collapse sidebar'" :title="collapsed ? 'Expand' : 'Collapse'" @click="toggle">
          <AppIcon :name="collapsed ? 'expand' : 'collapse'" :size="16" />
        </button>
        <button type="button" class="btn-ghost ml-auto px-1.5 lg:hidden" aria-label="Close navigation" @click="drawer = false"><AppIcon name="close" :size="16" /></button>
      </div>

      <div v-show="!collapsed || drawer" class="mb-4 px-1">
        <label class="label px-1" for="ws-select">Workspace</label>
        <select id="ws-select" v-model="wsId" class="input py-1.5">
          <option v-for="w in auth.workspaces" :key="w.id" :value="w.id">{{ w.name }}</option>
        </select>
      </div>

      <nav class="flex flex-1 flex-col gap-0.5 overflow-y-auto">
        <RouterLink v-for="n in nav.filter((x) => !x.admin || auth.isAdmin())" :key="n.to" :to="n.to" :title="collapsed ? n.label : undefined"
          class="nav-link group relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm" :class="isActive(n.to) ? 'is-active' : ''"
          :aria-current="isActive(n.to) ? 'page' : undefined">
          <AppIcon :name="n.icon" />
          <span :class="collapsed && !drawer ? 'sr-only' : 'truncate'">{{ n.label }}</span>
        </RouterLink>
      </nav>

      <div class="mt-3 border-t border-line pt-3">
        <div class="flex items-center gap-2.5 px-1">
          <span class="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white text-[11px] font-semibold text-black" aria-hidden="true">{{ initials }}</span>
          <div v-show="!collapsed || drawer" class="min-w-0 text-xs">
            <div class="truncate text-ink">{{ auth.user?.email }}</div>
            <div class="text-muted">{{ auth.current?.role }}</div>
          </div>
        </div>
        <button type="button" class="btn-secondary mt-3 w-full justify-center" :class="collapsed && !drawer ? 'px-0' : ''" :title="collapsed ? 'Sign out' : undefined" @click="logout">
          <AppIcon name="logout" :size="16" /><span :class="collapsed && !drawer ? 'sr-only' : ''">Sign out</span>
        </button>
      </div>
    </aside>

    <main class="min-w-0 px-4 py-6 transition-[padding] duration-300 ease-out-soft sm:px-6 lg:py-8 lg:pr-8" :class="collapsed ? 'lg:pl-[112px]' : 'lg:pl-[284px]'">
      <div class="mx-auto max-w-[1400px]">
        <div v-if="!auth.current" class="card">No workspace. Ask an admin for access.</div>
        <RouterView v-else v-slot="{ Component, route: r }">
          <Transition name="page" mode="out-in"><div :key="`${auth.current.id}:${r.fullPath}`"><component :is="Component" /></div></Transition>
        </RouterView>
      </div>
    </main>
  </div>
</template>

<style scoped>
.nav-link { color: var(--silver); transition: color var(--dur-1), background-color var(--dur-2) var(--ease); }
.nav-link:hover { color: var(--ink); background: var(--glass-hover); }
.nav-link.is-active {
  color: var(--ink);
  background: linear-gradient(180deg, rgb(255 255 255 / 0.11), rgb(255 255 255 / 0.05));
  box-shadow: inset 0 0 0 1px rgb(255 255 255 / 0.12), 0 0 18px -6px rgb(255 255 255 / 0.3);
}
.nav-link.is-active::before {
  content: ''; position: absolute; left: -12px; top: 50%; width: 3px; height: 18px; transform: translateY(-50%);
  border-radius: 9999px; background: #fff; box-shadow: 0 0 10px 1px rgb(255 255 255 / 0.7);
}
.fade-enter-active, .fade-leave-active { transition: opacity var(--dur-2) var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
