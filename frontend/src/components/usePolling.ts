import { onBeforeUnmount, onMounted } from 'vue'

/** Run `fn` on mount and every `ms` while the component is mounted (tasks/progress refresh). */
export function usePolling(fn: () => unknown, ms = 5000) {
  let id: number | undefined
  onMounted(() => { fn(); id = window.setInterval(fn, ms) })
  onBeforeUnmount(() => window.clearInterval(id))
}
