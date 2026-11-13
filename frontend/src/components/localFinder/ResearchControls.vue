<script setup lang="ts">
/**
 * Research configuration drawer → POST research-tasks/ (LOCAL_LEAD_DISCOVERY, AGENT_2_CONTRACT.md inputs).
 * Non-modal on desktop so the map stays usable for "pick the search centre".
 */
import { computed, nextTick, ref, watch } from 'vue'
import { errorText } from '@/api/client'
import { localFinderApi as api } from '@/api/localFinder'
import { CATEGORY_SUGGESTIONS, countryOptions, LANGUAGES, SERVICES } from '@/features/localFinder/catalog'
import { taskInput, type DiscoveryInput } from '@/features/localFinder/model'
import { useLocalFinderStore } from '@/stores/localFinder'

const store = useLocalFinderStore()
const panel = ref<HTMLElement>()
const countries = countryOptions()
const form = ref(blank())
const categoryDraft = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
let geocoded: [number, number] | null = null // last centre set from the city; any other centre was picked by the user

/** City -> [lng, lat] via OSM Nominatim (low volume: on blur / submit only). Fails silently: the agent geocodes too. */
async function geocode(): Promise<[number, number] | null> {
  const f = form.value
  if (!f.city.trim()) return null
  const q = new URLSearchParams({ city: f.city.trim(), countrycodes: f.country.toLowerCase(), format: 'jsonv2', limit: '1' })
  if (f.region.trim()) q.set('state', f.region.trim())
  try {
    const r = await fetch(`https://nominatim.openstreetmap.org/search?${q}`, { signal: AbortSignal.timeout(5000) })
    const [hit] = r.ok ? await r.json() : []
    return hit ? [Number(hit.lon), Number(hit.lat)] : null
  } catch { return null }
}
async function centreOnCity() {
  if (store.draftCenter && String(store.draftCenter) !== String(geocoded)) return // never override a centre the user picked on the map
  const c = await geocode()
  if (c) store.draftCenter = geocoded = c // the map flies there (BusinessMap watches draftCenter)
}

function blank() {
  return { country: 'BG', city: '', region: '', neighborhood: '', categories: [] as string[], services: [] as string[], minScore: 50, max: 25, language: 'auto', notes: '' }
}

// Prefill from the latest run each time the drawer opens (fast re-runs with a tweak).
watch(() => store.configOpen, async (open) => {
  if (!open) { store.picking = false; return }
  const last = taskInput(store.tasks[0] ?? null)
  const f = blank()
  if (last) {
    Object.assign(f, {
      country: last.location.country_code, city: last.location.city, region: last.location.region ?? '', categories: [...(last.categories ?? [])],
      minScore: last.min_score ?? 50, max: last.max_businesses ?? 25, language: last.language ?? 'auto',
      services: SERVICES.filter((s) => s.checks.some((c) => last.checks?.includes(c))).map((s) => s.id),
    })
    store.draftRadiusKm = last.location.radius_km ?? 10
    store.draftCenter = last.location.latitude != null && last.location.longitude != null ? [last.location.longitude, last.location.latitude] : null
  }
  form.value = f
  geocoded = store.draftCenter ? [...store.draftCenter] : null // a prefilled centre follows a new city
  error.value = null
  await nextTick()
  panel.value?.querySelector<HTMLElement>('select, input')?.focus()
}, { immediate: true })

const suggestions = computed(() => CATEGORY_SUGGESTIONS.filter((c) => !form.value.categories.includes(c)).slice(0, 14))
function addCategory(c = categoryDraft.value) {
  for (const part of c.split(',').map((x) => x.trim()).filter(Boolean)) {
    if (form.value.categories.length < 30 && !form.value.categories.some((x) => x.toLowerCase() === part.toLowerCase())) form.value.categories.push(part.slice(0, 100))
  }
  categoryDraft.value = ''
}
function onCategoryKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addCategory() }
}
const removeCategory = (c: string) => { form.value.categories = form.value.categories.filter((x) => x !== c) }
const toggleService = (id: string) => {
  form.value.services = form.value.services.includes(id) ? form.value.services.filter((x) => x !== id) : [...form.value.services, id]
}

const notes = computed(() => [form.value.neighborhood.trim() && `Focus area / neighbourhood: ${form.value.neighborhood.trim()}.`, form.value.notes.trim()]
  .filter(Boolean).join('\n').slice(0, 2000))

async function start() {
  addCategory()
  error.value = null
  const f = form.value
  const input: DiscoveryInput = {
    location: { city: f.city.trim(), country_code: f.country, region: f.region.trim(), radius_km: store.draftRadiusKm },
    categories: f.categories, max_businesses: f.max, min_score: f.minScore, language: f.language, notes: notes.value,
    checks: [...new Set(SERVICES.filter((s) => f.services.includes(s.id)).flatMap((s) => s.checks))],
  }
  busy.value = true
  if (!store.draftCenter) await centreOnCity() // coordinates let the map zoom to the city and save the agent a lookup
  if (store.draftCenter) Object.assign(input.location, { longitude: store.draftCenter[0], latitude: store.draftCenter[1] })
  try {
    const task = await api.startDiscovery(input)
    store.configOpen = false
    store.taskFilter = task.id
    store.log('started', `Research queued · ${f.city}, ${f.country}`)
    store.syncNow()
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Transition name="lbf-drawer">
    <aside v-if="store.configOpen" v-show="!store.picking" ref="panel" role="dialog" aria-modal="false" aria-labelledby="cfg-h"
      class="glass-pop fixed inset-0 z-40 flex flex-col md:inset-y-3 md:right-3 md:left-auto md:w-[420px] md:rounded-[var(--radius-lg)]">
      <header class="flex items-center justify-between border-b border-line px-5 py-4">
        <div>
          <h2 id="cfg-h" class="text-base font-semibold text-ink">New research</h2>
          <p class="text-xs text-silver">Agent 2 discovers businesses, scans their websites and drafts proposals for your approval.</p>
        </div>
        <button type="button" class="rounded-lg p-1.5 text-muted hover:bg-white/[0.06] hover:text-soft" aria-label="Close" @click="store.configOpen = false">
          <svg viewBox="0 0 20 20" class="h-4 w-4" fill="currentColor" aria-hidden="true"><path d="M5.3 5.3a1 1 0 0 1 1.4 0L10 8.6l3.3-3.3a1 1 0 1 1 1.4 1.4L11.4 10l3.3 3.3a1 1 0 0 1-1.4 1.4L10 11.4l-3.3 3.3a1 1 0 0 1-1.4-1.4L8.6 10 5.3 6.7a1 1 0 0 1 0-1.4Z" /></svg>
        </button>
      </header>

      <form id="cfg-form" class="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-4" @submit.prevent="start">
        <fieldset class="space-y-3">
          <legend class="mb-2 text-xs font-semibold text-ink">Area</legend>
          <div class="grid grid-cols-2 gap-3">
            <div><label class="label" for="cfg-country">Country</label>
              <select id="cfg-country" v-model="form.country" class="input" required @change="centreOnCity">
                <option v-for="c in countries" :key="c.code" :value="c.code">{{ c.name }}</option>
              </select></div>
            <div><label class="label" for="cfg-city">City</label><input id="cfg-city" v-model="form.city" class="input" required maxlength="120" placeholder="Sofia" @change="centreOnCity" /></div>
            <div><label class="label" for="cfg-region">Region</label><input id="cfg-region" v-model="form.region" class="input" maxlength="120" placeholder="Optional" /></div>
            <div><label class="label" for="cfg-hood">Neighbourhood</label><input id="cfg-hood" v-model="form.neighborhood" class="input" maxlength="120" placeholder="e.g. Lozenets" /></div>
          </div>
          <div class="rounded-xl border border-line p-3">
            <div class="flex items-center justify-between gap-2">
              <div class="text-xs">
                <div class="font-medium text-ink">Search centre</div>
                <div class="text-silver" data-testid="draft-center">{{ store.draftCenter ? `${store.draftCenter[1].toFixed(5)}, ${store.draftCenter[0].toFixed(5)}` : 'City centre (found when you enter the city)' }}</div>
              </div>
              <div class="flex gap-1.5">
                <button v-if="store.draftCenter" type="button" class="btn-secondary px-2 py-1 text-xs" @click="store.draftCenter = null">Clear</button>
                <button type="button" class="btn-secondary px-2 py-1 text-xs" @click="store.picking = true">Pick on map</button>
              </div>
            </div>
            <label class="label mt-3" for="cfg-radius">Radius · {{ store.draftRadiusKm }} km</label>
            <input id="cfg-radius" v-model.number="store.draftRadiusKm" type="range" min="1" max="100" class="w-full accent-white" />
            <p class="text-[11px] text-muted">The neighbourhood is passed to the agent as a note; pick a centre on the map to focus discovery there.</p>
          </div>
        </fieldset>

        <fieldset>
          <legend class="mb-2 text-xs font-semibold text-ink">Business categories <span class="font-normal text-muted">· empty = any</span></legend>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="c in form.categories" :key="c" class="inline-flex items-center gap-1 rounded-full bg-white py-0.5 pr-1 pl-2.5 text-xs font-medium text-black">
              {{ c }}<button type="button" class="rounded-full p-0.5 hover:bg-black/10" :aria-label="`Remove ${c}`" @click="removeCategory(c)">
                <svg viewBox="0 0 20 20" class="h-3 w-3" fill="currentColor" aria-hidden="true"><path d="M5.3 5.3a1 1 0 0 1 1.4 0L10 8.6l3.3-3.3a1 1 0 1 1 1.4 1.4L11.4 10l3.3 3.3a1 1 0 0 1-1.4 1.4L10 11.4l-3.3 3.3a1 1 0 0 1-1.4-1.4L8.6 10 5.3 6.7a1 1 0 0 1 0-1.4Z" /></svg></button>
            </span>
          </div>
          <input v-model="categoryDraft" class="input mt-2" placeholder="Type a category and press Enter" maxlength="100" aria-label="Add category"
            @keydown="onCategoryKey" />
          <div class="mt-2 flex flex-wrap gap-1">
            <button v-for="s in suggestions" :key="s" type="button" class="chip py-0.5" @click="addCategory(s)">+ {{ s }}</button>
          </div>
        </fieldset>

        <fieldset>
          <legend class="mb-2 text-xs font-semibold text-ink">Development services <span class="font-normal text-muted">· none = check everything</span></legend>
          <div class="grid grid-cols-2 gap-2">
            <button v-for="s in SERVICES" :key="s.id" type="button" role="checkbox" :aria-checked="form.services.includes(s.id)"
              class="rounded-xl border p-2.5 text-left transition" :class="form.services.includes(s.id) ? 'border-white/60 bg-white/[0.08] shadow-[0_0_20px_-6px_rgb(255_255_255/0.4)]' : 'border-line hover:border-white/25'"
              @click="toggleService(s.id)">
              <div class="text-xs font-medium text-ink">{{ s.label }}</div>
              <div class="mt-0.5 text-[10px] leading-snug text-silver">{{ s.hint }}</div>
            </button>
          </div>
        </fieldset>

        <fieldset class="space-y-3">
          <legend class="mb-2 text-xs font-semibold text-ink">Lead qualification</legend>
          <div><label class="label" for="cfg-min">Minimum score to qualify · {{ form.minScore }}</label>
            <input id="cfg-min" v-model.number="form.minScore" type="range" min="0" max="100" step="5" class="w-full accent-white" /></div>
          <div class="grid grid-cols-2 gap-3">
            <div><label class="label" for="cfg-max">Max businesses</label><input id="cfg-max" v-model.number="form.max" type="number" min="1" max="200" class="input" required /></div>
            <div><label class="label" for="cfg-lang">Outreach language</label>
              <select id="cfg-lang" v-model="form.language" class="input"><option v-for="[c, n] in LANGUAGES" :key="c" :value="c">{{ n }}</option></select></div>
          </div>
          <div><label class="label" for="cfg-notes">Notes for the agent</label><textarea id="cfg-notes" v-model="form.notes" rows="2" maxlength="1800" class="input" placeholder="Optional context" /></div>
        </fieldset>
      </form>

      <footer class="space-y-2 border-t border-line px-5 py-4">
        <p v-if="error" class="rounded-lg bg-bad/10 px-3 py-2 text-xs text-bad" role="alert">{{ error }}</p>
        <p v-if="store.activeTask" class="text-[11px] text-warn">A run is already in progress; a new one is queued after it.</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn-secondary" @click="store.configOpen = false">Cancel</button>
          <button type="submit" form="cfg-form" class="btn-accent" :disabled="busy">{{ busy ? 'Starting…' : 'Start research' }}</button>
        </div>
      </footer>
    </aside>
  </Transition>
</template>

<style scoped>
.lbf-drawer-enter-active, .lbf-drawer-leave-active { transition: transform .25s ease, opacity .25s ease; }
.lbf-drawer-enter-from, .lbf-drawer-leave-to { transform: translateX(24px); opacity: 0; }
@media (prefers-reduced-motion: reduce) { .lbf-drawer-enter-active, .lbf-drawer-leave-active { transition: none; } }
</style>
