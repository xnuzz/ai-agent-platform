<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Membership, Paginated, Role } from '@/api/types'
import ErrorBanner from './ErrorBanner.vue'
import Notice from './Notice.vue'
import { useAction } from './useAction'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const members = ref<Membership[]>([])
const ROLES: Role[] = ['VIEWER', 'DEVELOPER', 'ADMIN', 'OWNER']
const form = ref<{ email: string; role: Role }>({ email: '', role: 'DEVELOPER' })
const { busy, error, notice, run } = useAction()
const load = async () => { members.value = (await api.get<Paginated<Membership>>('members/', { page_size: 100 })).results }
onMounted(load)

const add = () => run(async () => { await api.post('members/', form.value); form.value.email = ''; await load() }, 'Member added.')
const setRole = (m: Membership, role: Role) => run(async () => { await api.patch(`members/${m.id}/`, { role }); await load() }, 'Role updated.')
const remove = (m: Membership) => {
  if (!confirm(`Remove ${m.user.email} from this workspace?`)) return
  run(async () => { await api.del(`members/${m.id}/`); await load() }, 'Member removed.')
}
</script>

<template>
  <section class="card max-w-3xl space-y-4">
    <ErrorBanner :message="error" />
    <table class="table">
      <thead><tr><th>Member</th><th>Role</th><th /></tr></thead>
      <tbody>
        <tr v-for="m in members" :key="m.id">
          <td><div>{{ m.user.email }}</div><div class="text-xs text-silver">{{ m.user.full_name }}</div></td>
          <td>
            <select v-if="auth.isAdmin() && m.user.id !== auth.user?.id" :value="m.role" class="input w-36" :disabled="busy"
              @change="setRole(m, ($event.target as HTMLSelectElement).value as Role)">
              <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
            </select>
            <span v-else class="text-sm">{{ m.role }}<span v-if="m.user.id === auth.user?.id" class="text-xs text-muted"> (you)</span></span>
          </td>
          <td class="text-right"><button v-if="auth.isAdmin() && m.user.id !== auth.user?.id" class="text-xs text-bad" @click="remove(m)">Remove</button></td>
        </tr>
      </tbody>
    </table>
    <form v-if="auth.isAdmin()" class="flex flex-wrap items-end gap-3 border-t border-line pt-4" @submit.prevent="add">
      <div class="min-w-64 flex-1"><label class="label">Add existing user by email</label><input v-model="form.email" type="email" required class="input" /></div>
      <div><label class="label">Role</label><select v-model="form.role" class="input w-36"><option v-for="r in ROLES" :key="r">{{ r }}</option></select></div>
      <button class="btn-primary" :disabled="busy">Add member</button>
      <Notice :notice="notice" />
    </form>
    <p class="text-xs text-silver">VIEWER: read-only · DEVELOPER: run agents, edit, approve, launch · ADMIN: + settings, members, integrations, audit log · OWNER: + ownership. Email invitations are not available yet — the person must register first.</p>
  </section>
</template>
