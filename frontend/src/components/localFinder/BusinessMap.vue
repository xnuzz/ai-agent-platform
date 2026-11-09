<script setup lang="ts">
/**
 * Live discovery map (MapLibre GL). Businesses are clustered by a GeoJSON source; unclustered points and
 * clusters are rendered as HTML markers (keyboard-focusable buttons with CSS states/animations).
 * Only backend-supplied coordinates are plotted — rows without valid coordinates stay list-only.
 */
import type { Feature, FeatureCollection, Point } from 'geojson'
import {
  LngLatBounds, Map as MapLibre, Marker, NavigationControl, Popup, setWorkerUrl,
  type GeoJSONSource, type IControl, type LngLatLike, type MapGeoJSONFeature,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
// MapLibre derives its worker URL from import.meta.url, which bundlers rewrite; point it at the emitted asset.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { computed, h, onBeforeUnmount, onMounted, ref, render, watch } from 'vue'
import { COUNTRY_BOUNDS } from '@/features/localFinder/catalog'
import { MAP_BG, mapStyle } from '@/features/localFinder/mapStyle'
import { countryName, POTENTIAL_LABEL, REVIEW_LABEL, taskInput, type LeadRow, type MarkerTone } from '@/features/localFinder/model'
import { useLocalFinderStore } from '@/stores/localFinder'
import BusinessPopup from './BusinessPopup.vue'

setWorkerUrl(workerUrl)

const store = useLocalFinderStore()
const container = ref<HTMLDivElement>()
const failed = ref<string | null>(null)
const tilesDown = ref(false)
const labels = ref(false)

let map: MapLibre | null = null
let ready = false
let follow = true // auto-frame results until the user pans/zooms
let syncQueued = false
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const points = new Map<string, { marker: Marker; pin: HTMLButtonElement }>()
const clusters = new Map<number, { marker: Marker; pin: HTMLButtonElement }>()
let popup: Popup | null = null
let popupBody: HTMLDivElement | null = null
const popupLead = ref<string | null>(null)
let tooltip: Popup | null = null

const TONES: { tone: MarkerTone; label: string }[] = [
  { tone: 'new', label: 'New discovery' }, { tone: 'hot', label: 'High potential' }, { tone: 'reviewed', label: 'Reviewed' },
  { tone: 'approved', label: 'Approved' }, { tone: 'rejected', label: 'Rejected' },
]

/** The map shows what the list shows (filter + search); framing uses the whole run so filters don't move the camera. */
const onMap = computed(() => store.visibleRows.filter((r) => r.coords))
const byId = computed(() => new Map(store.rows.map((r) => [r.lead.id, r])))
const unmapped = computed(() => store.visibleRows.length - onMap.value.length)
const toneCounts = computed(() => onMap.value.reduce<Record<string, number>>((o, r) => ({ ...o, [r.tone]: (o[r.tone] ?? 0) + 1 }), {}))
const areaTask = computed(() => store.activeTask ?? store.currentTask)
const crumbs = computed(() => {
  const loc = taskInput(areaTask.value)?.location
  if (!loc) return []
  return [countryName(loc.country_code), loc.region, loc.city].filter(Boolean) as string[]
})

// ------------------------------------------------------------------ setup
onMounted(() => {
  let m: MapLibre
  try {
    m = map = new MapLibre({
      container: container.value!, style: mapStyle(), center: [15, 48], zoom: 3.3, maxPitch: 0, dragRotate: false,
      pitchWithRotate: false, touchPitch: false, attributionControl: { compact: true }, fadeDuration: reduced ? 0 : 200,
    })
  } catch {
    failed.value = 'The map needs WebGL, which this browser or device does not provide. The business list still works.'
    return
  }
  m.touchZoomRotate.disableRotation()
  m.addControl(new NavigationControl({ showCompass: false }), 'top-right')
  m.addControl(new FitControl(), 'top-right')
  m.on('error', (e) => {
    // Basemap tiles/fonts unreachable: keep working (markers do not depend on them) and say so.
    if ((e as { sourceId?: string }).sourceId === 'omt' || /tiles|fonts|pbf|tilejson/i.test(String(e.error?.message ?? ''))) tilesDown.value = true
  })
  m.once('style.load', setup)
  m.on('render', queueSync)
  m.on('zoomend', () => { labels.value = (m.getZoom() ?? 0) >= 14 })
  for (const ev of ['dragstart', 'zoomstart', 'rotatestart'] as const) m.on(ev, (e) => { if ((e as { originalEvent?: Event }).originalEvent) follow = false })
  m.on('click', (e) => {
    if ((e.originalEvent.target as HTMLElement)?.closest('.lbf-marker, .lbf-cluster, .maplibregl-popup')) return
    if (store.picking) {
      store.draftCenter = [round6(e.lngLat.lng), round6(e.lngLat.lat)]
      store.picking = false
    }
  })
  new ResizeObserver(() => map?.resize()).observe(container.value!)
})

function setup() {
  if (!map) return
  map.addSource('businesses', { type: 'geojson', data: features(), cluster: true, clusterRadius: 48, clusterMaxZoom: 14 })
  // Invisible layer: keeps the clustered source loaded so querySourceFeatures() returns its features.
  map.addLayer({ id: 'businesses-index', type: 'circle', source: 'businesses', paint: { 'circle-radius': 0, 'circle-opacity': 0 } })
  map.addSource('area', { type: 'geojson', data: emptyFc() })
  map.addLayer({ id: 'area-fill', type: 'fill', source: 'area', paint: { 'fill-color': '#ffffff', 'fill-opacity': 0.04 } })
  map.addLayer({ id: 'area-line', type: 'line', source: 'area', paint: { 'line-color': '#d4d4d8', 'line-width': 1.2, 'line-dasharray': [2, 2] } })
  ready = true
  drawArea()
  frame(true)
}

onBeforeUnmount(() => {
  closePopup()
  map?.remove()
  map = null
})

// ------------------------------------------------------------------ data → source
const emptyFc = (): FeatureCollection => ({ type: 'FeatureCollection', features: [] })
function features(): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: onMap.value.map((r) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: r.coords! }, properties: { id: r.lead.id } })),
  }
}
// Re-cluster only when the plotted set or a position changes (polls replace objects every few seconds).
const plotted = computed(() => onMap.value.map((r) => `${r.lead.id}@${r.coords!.join(',')}`).join('|'))
watch(plotted, () => {
  if (!ready || !map) return
  void (map.getSource('businesses') as GeoJSONSource).setData(features())
  queueSync()
})
// Restyle visible markers when statuses/selection change without a data change.
watch([() => store.selectedId, () => store.fresh, byId], () => points.forEach((p, id) => paint(p.pin, byId.value.get(id))))

function queueSync() {
  if (syncQueued || !ready) return
  syncQueued = true
  requestAnimationFrame(() => { syncQueued = false; syncMarkers() })
}

function syncMarkers() {
  if (!map || !map.getSource('businesses') || !map.isSourceLoaded('businesses')) return
  const seenP = new Set<string>(), seenC = new Set<number>()
  for (const f of map.querySourceFeatures('businesses') as MapGeoJSONFeature[]) {
    const at = (f.geometry as Point).coordinates as [number, number]
    const p = f.properties as { cluster?: boolean; cluster_id?: number; point_count?: number; id?: string }
    if (p.cluster) {
      const cid = p.cluster_id!
      if (seenC.has(cid)) continue
      seenC.add(cid)
      const c = clusters.get(cid) ?? addCluster(cid, at)
      c.pin.textContent = String(p.point_count)
      c.pin.setAttribute('aria-label', `${p.point_count} businesses — zoom in`)
      c.pin.style.setProperty('--size', `${Math.min(56, 30 + Math.log2(p.point_count ?? 2) * 5)}px`)
    } else if (p.id) {
      const row = byId.value.get(p.id)
      if (!row || seenP.has(p.id)) continue
      seenP.add(p.id)
      const m = points.get(p.id) ?? addPoint(row, at)
      paint(m.pin, row)
    }
  }
  for (const [id, m] of points) if (!seenP.has(id)) { m.marker.remove(); points.delete(id) }
  for (const [id, c] of clusters) if (!seenC.has(id)) { c.marker.remove(); clusters.delete(id) }
}

function addPoint(row: LeadRow, at: LngLatLike) {
  const wrap = document.createElement('div')
  wrap.className = 'lbf-marker'
  const pin = document.createElement('button')
  pin.type = 'button'
  pin.className = 'lbf-pin'
  pin.dataset.id = row.lead.id
  const label = document.createElement('span')
  label.className = 'lbf-name'
  label.textContent = row.lead.business.name
  wrap.append(pin, label)
  pin.addEventListener('click', () => store.select(row.lead.id))
  pin.addEventListener('mouseenter', () => showTooltip(row.lead.id))
  pin.addEventListener('focus', () => showTooltip(row.lead.id))
  pin.addEventListener('mouseleave', hideTooltip)
  pin.addEventListener('blur', hideTooltip)
  if (store.fresh[row.lead.id]) pin.classList.add('is-fresh')
  const marker = new Marker({ element: wrap, anchor: 'center' }).setLngLat(at).addTo(map!)
  const entry = { marker, pin }
  points.set(row.lead.id, entry)
  return entry
}

function paint(pin: HTMLButtonElement, row: LeadRow | undefined) {
  if (!row) return
  pin.dataset.tone = row.tone
  pin.dataset.potential = row.potential
  pin.classList.toggle('is-selected', row.lead.id === store.selectedId)
  pin.setAttribute('aria-label', `${row.lead.business.name}, ${POTENTIAL_LABEL[row.potential].toLowerCase()}, score ${row.lead.score ?? 'none'}, ${REVIEW_LABEL[row.review].toLowerCase()}`)
  pin.setAttribute('aria-pressed', String(row.lead.id === store.selectedId))
}

function addCluster(cid: number, at: LngLatLike) {
  const wrap = document.createElement('div')
  wrap.className = 'lbf-cluster'
  const pin = document.createElement('button')
  pin.type = 'button'
  pin.className = 'lbf-cluster-pin'
  wrap.append(pin)
  pin.addEventListener('click', async () => {
    const src = map?.getSource('businesses') as GeoJSONSource | undefined
    if (!src || !map) return
    const zoom = await src.getClusterExpansionZoom(cid).catch(() => map!.getZoom() + 2)
    follow = false
    map.easeTo({ center: at, zoom: Math.min(zoom + 0.5, 18), duration: reduced ? 0 : 500 })
  })
  const marker = new Marker({ element: wrap, anchor: 'center' }).setLngLat(at).addTo(map!)
  const entry = { marker, pin }
  clusters.set(cid, entry)
  return entry
}

// ------------------------------------------------------------------ tooltip + popup
function showTooltip(id: string) {
  const row = byId.value.get(id)
  if (!map || !row?.coords || popupLead.value === id) return
  const box = document.createElement('div')
  const name = document.createElement('div')
  name.className = 'lbf-tip-name'
  name.textContent = row.lead.business.name
  const meta = document.createElement('div')
  meta.className = 'lbf-tip-meta'
  meta.textContent = `${row.lead.business.category || 'Uncategorised'} · score ${row.lead.score ?? '—'} · ${REVIEW_LABEL[row.review]}`
  box.append(name, meta)
  tooltip ??= new Popup({ closeButton: false, closeOnClick: false, className: 'lbf-tooltip', offset: 14, maxWidth: '260px' })
  tooltip.setLngLat(row.coords).setDOMContent(box).addTo(map)
}
function hideTooltip() { tooltip?.remove() }

function openPopup(row: LeadRow) {
  if (!map || !row.coords) return
  closePopup()
  hideTooltip()
  popupBody = document.createElement('div')
  popupLead.value = row.lead.id
  renderPopup(row)
  popup = new Popup({ closeButton: true, closeOnClick: false, className: 'lbf-popup', offset: 18, maxWidth: 'none', focusAfterOpen: false })
    .setLngLat(row.coords).setDOMContent(popupBody).addTo(map)
  popup.on('close', () => {
    if (popupBody) render(null, popupBody)
    popupBody = null
    popup = null
    popupLead.value = null
  })
}
const renderPopup = (row: LeadRow) => popupBody && render(h(BusinessPopup, { row, onOpen: () => store.openDetail(row.lead.id) }), popupBody)
function closePopup() { popup?.remove() }
watch(() => (popupLead.value ? byId.value.get(popupLead.value) : undefined), (row) => { if (row) renderPopup(row) })

// ------------------------------------------------------------------ selection + camera
watch(() => store.focusSeq, () => {
  const row = store.selectedRow
  if (!map || !row) return
  if (!row.coords) { closePopup(); return }
  follow = false
  const opts = { center: row.coords, zoom: Math.max(map.getZoom(), 15) }
  if (reduced) map.jumpTo(opts)
  else map.flyTo({ ...opts, speed: 1.6, curve: 1.3, essential: true })
  openPopup(row)
})
watch(() => store.selectedId, (id) => { if (!id) closePopup() })

/** Frame the current run: its businesses, else its search centre, else its country, else Europe. */
function frame(instant = false) {
  if (!map || !ready) return
  const duration = instant || reduced ? 0 : 900
  const pts = store.scopedRows.flatMap((r) => (r.coords ? [r.coords] : []))
  if (pts.length === 1) { map.easeTo({ center: pts[0], zoom: 14, duration }); return }
  if (pts.length > 1) {
    const b = pts.reduce((acc, p) => acc.extend(p), new LngLatBounds(pts[0], pts[0]))
    map.fitBounds(b, { padding: { top: 80, bottom: 100, left: 70, right: 70 }, maxZoom: 15, duration })
    return
  }
  const loc = taskInput(areaTask.value)?.location
  if (loc?.latitude != null && loc.longitude != null) {
    map.easeTo({ center: [loc.longitude, loc.latitude], zoom: zoomForRadius(loc.radius_km ?? 10), duration })
    return
  }
  const box = loc?.country_code ? COUNTRY_BOUNDS[loc.country_code.toUpperCase()] : undefined
  if (box) map.fitBounds(box, { padding: 40, duration })
}
const zoomForRadius = (km: number) => Math.max(6, Math.min(15, 14.6 - Math.log2(km)))
const round6 = (n: number) => Math.round(n * 1e6) / 1e6

let frameTimer: number | undefined
watch(() => store.scopedRows.filter((r) => r.coords).length, () => {
  if (!follow) return
  window.clearTimeout(frameTimer)
  frameTimer = window.setTimeout(() => frame(), 400) // a batch lands at once: frame once
})
watch(() => store.taskFilter, () => { follow = true; frame() })
watch(() => store.activeTask?.id, (id) => { if (id) { follow = true; frame(); drawArea() } })

class FitControl implements IControl {
  private el?: HTMLDivElement
  onAdd() {
    this.el = document.createElement('div')
    this.el.className = 'maplibregl-ctrl maplibregl-ctrl-group'
    const b = document.createElement('button')
    b.type = 'button'
    b.className = 'lbf-fit'
    b.title = 'Fit map to discovered businesses'
    b.setAttribute('aria-label', 'Fit map to discovered businesses')
    b.innerHTML = '<svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 7V3h4M17 7V3h-4M3 13v4h4M17 13v4h-4"/></svg>'
    b.addEventListener('click', () => { follow = true; frame() })
    this.el.append(b)
    return this.el
  }
  onRemove() { this.el?.remove() }
}

// ------------------------------------------------------------------ search area (task input or draft)
function circle([lng, lat]: [number, number], km: number): Feature {
  const coords: [number, number][] = []
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * 2 * Math.PI
    coords.push([lng + (km / (111.32 * Math.cos((lat * Math.PI) / 180))) * Math.cos(a), lat + (km / 110.574) * Math.sin(a)])
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [coords] }, properties: {} }
}
function drawArea() {
  if (!map || !ready) return
  let fc = emptyFc()
  const loc = taskInput(areaTask.value)?.location
  if (store.configOpen && store.draftCenter) fc = { type: 'FeatureCollection', features: [circle(store.draftCenter, store.draftRadiusKm)] }
  else if (loc?.latitude != null && loc.longitude != null) fc = { type: 'FeatureCollection', features: [circle([loc.longitude, loc.latitude], loc.radius_km ?? 10)] }
  void (map.getSource('area') as GeoJSONSource | undefined)?.setData(fc)
}
watch([() => store.configOpen, () => store.draftCenter, () => store.draftRadiusKm, areaTask], drawArea)
watch(() => store.draftCenter, (c) => {
  if (c && map && store.configOpen) map.easeTo({ center: c, zoom: zoomForRadius(store.draftRadiusKm), duration: reduced ? 0 : 600 })
})

// ------------------------------------------------------------------ discovery ripples
watch(() => Object.keys(store.fresh), (ids, old) => {
  if (!map) return
  for (const id of ids.filter((x) => !old?.includes(x))) {
    const row = byId.value.get(id)
    if (!row?.coords || reduced) continue
    const el = document.createElement('div')
    el.className = 'lbf-ripple'
    el.setAttribute('aria-hidden', 'true')
    const m = new Marker({ element: el, anchor: 'center' }).setLngLat(row.coords).addTo(map)
    window.setTimeout(() => m.remove(), 2600)
  }
})
</script>

<template>
  <div class="relative h-full w-full overflow-hidden rounded-2xl" :style="{ background: MAP_BG }">
    <!-- inline position: MapLibre's .maplibregl-map sets position:relative, which would beat a utility class -->
    <div ref="container" class="lbf-map" style="position: absolute; inset: 0" :class="{ 'lbf-labels': labels, 'lbf-picking': store.picking }"
      role="region" aria-label="Map of discovered businesses" />

    <!-- area breadcrumb -->
    <div v-if="crumbs.length" class="glass-pop pointer-events-none absolute top-3 left-3 flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-silver">
      <svg viewBox="0 0 20 20" class="h-3.5 w-3.5 text-silver" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 18s6-5.2 6-10A6 6 0 0 0 4 8c0 4.8 6 10 6 10Zm0-8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" clip-rule="evenodd" /></svg>
      <template v-for="(c, i) in crumbs" :key="i"><span v-if="i" class="text-silver">›</span><span :class="i === crumbs.length - 1 ? 'font-medium text-white' : ''">{{ c }}</span></template>
      <span v-if="store.agentState === 'SCANNING'" class="ml-2 flex items-center gap-1.5 rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-semibold tracking-wider text-silver">
        <span class="lbf-live-dot" />LIVE SCANNING
      </span>
    </div>

    <div v-if="store.picking" class="absolute top-3 left-1/2 -translate-x-1/2 rounded-full bg-white px-3.5 py-1.5 text-xs font-medium text-black shadow-[0_0_24px_-4px_rgb(255_255_255/0.6)]" role="status">
      Click the map to set the search centre · Esc to cancel
    </div>

    <!-- legend -->
    <div class="glass-pop absolute bottom-3 left-3 max-w-[calc(100%-1.5rem)] rounded-[var(--radius)] px-3 py-2 text-[11px] text-silver sm:max-w-[calc(100%-21rem)]" aria-label="Marker legend">
      <ul class="flex flex-wrap gap-x-3 gap-y-1">
        <li v-for="t in TONES" :key="t.tone" class="flex items-center gap-1.5">
          <span class="lbf-swatch" :data-tone="t.tone" />{{ t.label }}<span class="text-silver tabular-nums">{{ toneCounts[t.tone] ?? 0 }}</span>
        </li>
      </ul>
      <p v-if="unmapped > 0" class="mt-1 text-muted" data-testid="unmapped-note">{{ unmapped }} without coordinates — list only</p>
      <p v-if="tilesDown" class="mt-1 text-warn" role="status">Basemap tiles unavailable — markers are still at their real coordinates.</p>
    </div>

    <div v-if="!store.loaded && !failed" class="absolute inset-0 grid place-items-center text-sm text-muted">
      <span class="flex items-center gap-2"><span class="h-4 w-4 animate-spin rounded-full border-2 border-white/25 border-t-transparent" />Loading businesses…</span>
    </div>
    <div v-else-if="failed" class="absolute inset-0 grid place-items-center p-6 text-center text-sm text-muted">{{ failed }}</div>
    <div v-else-if="!store.scopedRows.length && store.agentState !== 'SCANNING' && !store.configOpen" class="pointer-events-none absolute inset-0 grid place-items-center p-6">
      <div class="glass-pop pointer-events-auto max-w-sm rounded-[var(--radius-lg)] p-6 text-center">
        <div class="text-sm font-semibold text-white">No businesses discovered yet</div>
        <p class="mt-1 text-xs text-muted">Choose a city and categories, then start Agent 2. Discoveries appear here live.</p>
        <button type="button" class="btn-accent mt-3" @click="store.configOpen = true">Configure research</button>
      </div>
    </div>
    <slot />
  </div>
</template>

<style>
/* Global: markers/popups live outside this component's DOM (MapLibre containers). Monochrome; colour only for approved/rejected. */
:root { --lbf-new: #d4d4d8; --lbf-hot: #ffffff; --lbf-reviewed: #71717a; --lbf-approved: var(--ok); --lbf-rejected: var(--bad); }
.lbf-picking .maplibregl-canvas-container { cursor: crosshair; }
.lbf-marker { display: flex; align-items: center; }
.lbf-pin {
  --c: var(--lbf-new);
  width: 14px; height: 14px; border-radius: 9999px; background: var(--c); border: 2px solid #050505;
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--c) 45%, transparent), 0 0 10px color-mix(in srgb, var(--c) 35%, transparent);
  cursor: pointer; transition: transform var(--dur-2) var(--ease), box-shadow var(--dur-2) var(--ease), background-color .3s ease, opacity .3s ease;
  animation: lbf-in .35s var(--ease) both;
}
.lbf-pin:hover, .lbf-pin:focus-visible { transform: scale(1.3); outline: none; box-shadow: 0 0 0 3px color-mix(in srgb, var(--c) 35%, transparent), 0 0 16px color-mix(in srgb, var(--c) 55%, transparent); }
.lbf-pin[data-tone='hot'] { --c: var(--lbf-hot); width: 16px; height: 16px; box-shadow: 0 0 0 3px rgb(255 255 255 / .2), 0 0 18px 5px rgb(255 255 255 / .55); }
.lbf-pin[data-tone='reviewed'] { --c: var(--lbf-reviewed); }
.lbf-pin[data-tone='approved'] { --c: var(--lbf-approved); }
.lbf-pin[data-tone='rejected'] { --c: var(--lbf-rejected); }
.lbf-pin[data-tone='new'][data-potential='low'] { width: 11px; height: 11px; opacity: .75; }
.lbf-pin.is-selected { transform: scale(1.5); z-index: 2; box-shadow: 0 0 0 3px #050505, 0 0 0 4.5px #fff, 0 0 26px 6px rgb(255 255 255 / .55); }
.lbf-pin.is-fresh { animation: lbf-drop .7s var(--ease) both; }
.lbf-name {
  display: none; margin-left: 7px; padding: 1px 7px; border-radius: 9999px; max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font: 500 11px/1.5 var(--font-sans); color: #f4f4f5; background: rgb(10 10 12 / .75); border: 1px solid rgb(255 255 255 / .08); pointer-events: none;
}
.lbf-labels .lbf-name { display: block; }
.lbf-cluster-pin {
  width: var(--size, 34px); height: var(--size, 34px); border-radius: 9999px; display: grid; place-items: center; cursor: pointer;
  font: 600 12px/1 var(--font-sans); color: #fff; background: rgb(255 255 255 / .1); border: 1px solid rgb(255 255 255 / .35);
  box-shadow: 0 0 0 6px rgb(255 255 255 / .04), 0 0 24px -2px rgb(255 255 255 / .3); backdrop-filter: blur(6px);
  transition: transform var(--dur-2) var(--ease), background-color var(--dur-2); animation: lbf-in .35s var(--ease) both;
}
.lbf-cluster-pin:hover, .lbf-cluster-pin:focus-visible { transform: scale(1.08); outline: none; background: rgb(255 255 255 / .2); }
.lbf-ripple { width: 16px; height: 16px; border-radius: 9999px; pointer-events: none; }
.lbf-ripple::before, .lbf-ripple::after {
  content: ''; position: absolute; inset: 0; border-radius: inherit; border: 1.5px solid rgb(255 255 255 / .8); animation: lbf-ripple 1.6s var(--ease) 2 both;
}
.lbf-ripple::after { animation-delay: .4s; }
.lbf-swatch { width: 8px; height: 8px; border-radius: 9999px; background: var(--lbf-new); display: inline-block; }
.lbf-swatch[data-tone='hot'] { background: var(--lbf-hot); box-shadow: 0 0 6px 1px rgb(255 255 255 / .8); }
.lbf-swatch[data-tone='reviewed'] { background: var(--lbf-reviewed); }
.lbf-swatch[data-tone='approved'] { background: var(--lbf-approved); }
.lbf-swatch[data-tone='rejected'] { background: var(--lbf-rejected); }
.lbf-live-dot { width: 6px; height: 6px; border-radius: 9999px; background: #fff; box-shadow: 0 0 8px 1px rgb(255 255 255 / .9); animation: lbf-blink 1.4s ease-in-out infinite; }
/* MapLibre chrome → glass */
.lbf-map .maplibregl-ctrl-group { background: var(--glass-3); border: 1px solid var(--line-strong); border-radius: 12px; box-shadow: var(--shadow-1); overflow: hidden; backdrop-filter: blur(var(--blur-2)); }
.lbf-map .maplibregl-ctrl-group button { width: 32px; height: 32px; }
.lbf-map .maplibregl-ctrl-group button + button { border-top: 1px solid var(--line); }
.lbf-map .maplibregl-ctrl-group button:hover { background: rgb(255 255 255 / .08); }
.lbf-map .maplibregl-ctrl-group .maplibregl-ctrl-icon { filter: invert(1) brightness(1.2); }
.lbf-fit { display: grid !important; place-items: center; color: #fff; }
.lbf-tooltip .maplibregl-popup-content { padding: 6px 10px; border-radius: 10px; background: var(--glass-3); color: #fff; box-shadow: var(--shadow-2); border: 1px solid var(--line-strong); backdrop-filter: blur(var(--blur-2)); }
.lbf-tooltip .maplibregl-popup-tip { display: none; }
.lbf-tip-name { font: 600 12px/1.3 var(--font-sans); }
.lbf-tip-meta { font: 400 11px/1.3 var(--font-sans); color: var(--silver); margin-top: 1px; }
.lbf-popup .maplibregl-popup-content { padding: 16px; border-radius: var(--radius-lg); background: var(--glass-3); border: 1px solid var(--line-strong); box-shadow: var(--shadow-2); backdrop-filter: blur(var(--blur-3)); }
.lbf-popup.maplibregl-popup-anchor-bottom .maplibregl-popup-tip { border-top-color: rgb(20 20 23 / .92); }
.lbf-popup.maplibregl-popup-anchor-top .maplibregl-popup-tip { border-bottom-color: rgb(20 20 23 / .92); }
.lbf-popup.maplibregl-popup-anchor-left .maplibregl-popup-tip { border-right-color: rgb(20 20 23 / .92); }
.lbf-popup.maplibregl-popup-anchor-right .maplibregl-popup-tip { border-left-color: rgb(20 20 23 / .92); }
.lbf-popup .maplibregl-popup-close-button { top: 8px; right: 10px; font-size: 18px; color: var(--silver); border-radius: 8px; }
.lbf-popup .maplibregl-popup-close-button:hover { background: rgb(255 255 255 / .08); color: #fff; }
.lbf-map .maplibregl-ctrl-attrib { background: rgb(10 10 12 / .7); color: var(--muted); }
.lbf-map .maplibregl-ctrl-attrib a { color: var(--soft); }
.lbf-map .maplibregl-ctrl-attrib-button { filter: invert(1); }
@keyframes lbf-in { from { opacity: 0; transform: scale(.4); } to { opacity: 1; transform: scale(1); } }
@keyframes lbf-drop { 0% { opacity: 0; transform: translateY(-12px) scale(.4); } 60% { opacity: 1; transform: translateY(0) scale(1.25); } 100% { transform: scale(1); } }
@keyframes lbf-ripple { from { transform: scale(.6); opacity: .9; } to { transform: scale(4); opacity: 0; } }
@keyframes lbf-blink { 50% { opacity: .25; } }
@media (prefers-reduced-motion: reduce) {
  .lbf-pin, .lbf-cluster-pin, .lbf-pin.is-fresh, .lbf-live-dot { animation: none; transition: none; }
}
</style>
