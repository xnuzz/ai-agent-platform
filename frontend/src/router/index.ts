import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppLayout from '@/layouts/AppLayout.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/reset-password', name: 'reset-password', component: () => import('@/views/ResetPasswordView.vue'), meta: { public: true } },
    { path: '/unsubscribe/:token', name: 'unsubscribe', component: () => import('@/views/UnsubscribeView.vue'), meta: { public: true } },
    // Full-screen dashboard with its own top navigation (map needs the width the sidebar layout would take).
    { path: '/local-finder', name: 'local-finder', component: () => import('@/views/LocalBusinessFinderView.vue') },
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
        { path: 'tasks', name: 'tasks', component: () => import('@/views/TasksView.vue') },
        { path: 'tasks/:id', name: 'task', component: () => import('@/views/TaskDetailView.vue'), props: true },
        { path: 'approvals', name: 'approvals', component: () => import('@/views/ApprovalsView.vue') },
        { path: 'ideas', name: 'ideas', component: () => import('@/views/IdeasView.vue') },
        { path: 'ideas/:id', name: 'idea', component: () => import('@/views/IdeaDetailView.vue'), props: true },
        { path: 'leads', name: 'leads', component: () => import('@/views/LeadsView.vue') },
        { path: 'leads/:id', name: 'lead', component: () => import('@/views/LeadDetailView.vue'), props: true },
        { path: 'campaigns', name: 'campaigns', component: () => import('@/views/CampaignsView.vue') },
        { path: 'campaigns/:id', name: 'campaign', component: () => import('@/views/CampaignDetailView.vue'), props: true },
        { path: 'suppression', name: 'suppression', component: () => import('@/views/SuppressionView.vue') },
        { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
        { path: 'audit', name: 'audit', component: () => import('@/views/AuditView.vue'), meta: { admin: true } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.user) return { name: 'login', query: { next: to.fullPath } }
  if (to.name === 'login' && auth.user) return { name: 'dashboard' }
  if (to.meta.admin && !auth.isAdmin()) return { name: 'dashboard' }
})
