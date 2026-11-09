import { ref } from 'vue'
import { errorText } from '@/api/client'

/** Wraps async UI actions: busy flag, error text, transient success message. */
export function useAction() {
  const busy = ref(false)
  const error = ref<string | null>(null)
  const notice = ref<string | null>(null)
  async function run<T>(fn: () => Promise<T>, success?: string): Promise<T | undefined> {
    busy.value = true
    error.value = null
    notice.value = null
    try {
      const r = await fn()
      if (success) { notice.value = success; setTimeout(() => { if (notice.value === success) notice.value = null }, 3000) }
      return r
    } catch (e) {
      error.value = errorText(e)
    } finally {
      busy.value = false
    }
  }
  return { busy, error, notice, run }
}
