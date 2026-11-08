<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Campaign, Paginated } from '@/api/types'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { agentLabel, fmtDate } from '@/components/format'

const campaigns = ref<Campaign[]>([])
onMounted(async () => { campaigns.value = (await api.get<Paginated<Campaign>>('campaigns/')).results })
</script>

<template>
  <PageHeader title="Campaigns" subtitle="Approved campaigns are launched here. The backend re-checks compliance before every send." />
  <div class="card overflow-x-auto p-0">
    <table class="table">
      <thead><tr><th>Name</th><th>Source</th><th>Messages</th><th>Status</th><th>Created</th></tr></thead>
      <tbody>
        <tr v-for="c in campaigns" :key="c.id" class="hover:bg-slate-50">
          <td><RouterLink :to="`/campaigns/${c.id}`" class="font-medium text-indigo-700">{{ c.name }}</RouterLink></td>
          <td class="text-xs text-slate-500">{{ agentLabel(c.source) }}</td>
          <td class="text-xs"><span v-for="(n, s) in c.message_counts" :key="s" class="mr-2">{{ s }}: {{ n }}</span></td>
          <td><StatusBadge :status="c.status" /></td>
          <td class="text-slate-500">{{ fmtDate(c.created_at) }}</td>
        </tr>
        <tr v-if="!campaigns.length"><td colspan="5" class="py-8 text-center text-slate-500">No campaigns yet.</td></tr>
      </tbody>
    </table>
  </div>
</template>
