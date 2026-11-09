<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/api/client'
import type { AuditEvent, Paginated } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import PageHeader from '@/components/PageHeader.vue'
import { fmtDate } from '@/components/format'
import { useAction } from '@/components/useAction'

const events = ref<AuditEvent[]>([])
const count = ref(0)
const page = ref(1)
const filters = ref({ actor_type: '', action: '' })
const { error, run } = useAction()
const load = () => run(async () => {
  const r = await api.get<Paginated<AuditEvent>>('audit-events/', { page: page.value, page_size: 50, actor_type: filters.value.actor_type || undefined, action: filters.value.action || undefined })
  events.value = r.results
  count.value = r.count
})
watch(filters, () => { page.value = 1; load() }, { deep: true, immediate: true })
watch(page, load)
const actor = (e: AuditEvent) => e.actor_type === 'USER' ? (e.actor_email ?? 'user') : e.actor_type === 'AGENT' ? e.actor_agent : 'system'
</script>

<template>
  <PageHeader title="Audit log" subtitle="Append-only record of every decision, state change and send. Admins only.">
    <select v-model="filters.actor_type" class="input w-36"><option value="">All actors</option><option>USER</option><option>AGENT</option><option>SYSTEM</option></select>
    <input v-model.lazy="filters.action" class="input w-56" placeholder="Exact action, e.g. approval.approved" />
  </PageHeader>
  <ErrorBanner :message="error" />
  <div class="card overflow-x-auto p-0">
    <table class="table">
      <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th><th>Details</th></tr></thead>
      <tbody>
        <tr v-for="e in events" :key="e.id">
          <td class="text-xs whitespace-nowrap text-silver">{{ fmtDate(e.created_at) }}</td>
          <td class="text-xs">{{ actor(e) }}</td>
          <td class="font-mono text-xs">{{ e.action }}</td>
          <td class="text-xs">{{ e.target_type }} <span class="text-muted">{{ e.target_id?.slice(0, 8) }}</span></td>
          <td class="max-w-md truncate font-mono text-xs text-silver" :title="JSON.stringify(e.metadata)">{{ Object.keys(e.metadata ?? {}).length ? JSON.stringify(e.metadata) : '' }}</td>
        </tr>
        <tr v-if="!events.length"><td colspan="5" class="py-8 text-center text-silver">No events.</td></tr>
      </tbody>
    </table>
  </div>
  <div class="mt-3 flex items-center gap-3 text-sm">
    <button class="btn-secondary" :disabled="page <= 1" @click="page--">Previous</button>
    <span class="text-silver">Page {{ page }} of {{ Math.max(1, Math.ceil(count / 50)) }}</span>
    <button class="btn-secondary" :disabled="page * 50 >= count" @click="page++">Next</button>
  </div>
</template>
