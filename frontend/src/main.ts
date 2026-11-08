import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { session } from './api/client'
import { useAuthStore } from './stores/auth'
import './style.css'

const app = createApp(App).use(createPinia())
const auth = useAuthStore()
session.onUnauthorized(() => { auth.logout(); router.push({ name: 'login' }) })
auth.bootstrap().catch(() => auth.logout()).finally(() => app.use(router).mount('#app'))
