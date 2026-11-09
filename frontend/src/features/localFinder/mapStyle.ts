/**
 * Dark basemap for the Local Business Finder.
 *
 * Default tiles: OpenFreeMap (https://openfreemap.org) — free, keyless, commercial use allowed, OpenStreetMap
 * data in the OpenMapTiles schema. Attribution is required and shown by MapLibre's attribution control.
 * Override with:
 *   VITE_MAP_STYLE_URL  — a complete MapLibre style URL (e.g. a MapTiler/Stadia dark style with your key), or
 *   VITE_MAP_TILES_URL  — another OpenMapTiles-schema TileJSON URL (+ VITE_MAP_GLYPHS_URL for its fonts).
 * Deployments with a Content-Security-Policy must allow the tile host in connect-src/img-src.
 */
import type { ExpressionSpecification, StyleSpecification } from 'maplibre-gl'

const TILES = import.meta.env.VITE_MAP_TILES_URL || 'https://tiles.openfreemap.org/planet'
const GLYPHS = import.meta.env.VITE_MAP_GLYPHS_URL || 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf'
const ATTRIBUTION = '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> '
  + '<a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a> '
  + 'Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'

export const MAP_BG = '#0d0f17'
const C = {
  land: MAP_BG, landuse: '#11141d', park: '#111a19', water: '#141c2e', waterLine: '#1b2540', building: '#161a26',
  minor: '#1d2130', major: '#2a2f45', motorway: '#3a3358', rail: '#1f2233', boundary: '#4b4370', label: '#9aa0b8',
  labelStrong: '#d6d8e6', halo: '#0b0d14',
}
const FONT = ['Noto Sans Regular']
const name: ExpressionSpecification = ['coalesce', ['get', 'name:latin'], ['get', 'name']]
const z = (stops: [number, number][]) => ['interpolate', ['exponential', 1.5], ['zoom'], ...stops.flat()] as unknown as number

export function mapStyle(): StyleSpecification | string {
  const custom = import.meta.env.VITE_MAP_STYLE_URL
  if (custom) return custom
  return {
    version: 8,
    glyphs: GLYPHS,
    sources: { omt: { type: 'vector', url: TILES, attribution: ATTRIBUTION } },
    layers: [
      { id: 'background', type: 'background', paint: { 'background-color': C.land } },
      { id: 'landuse', type: 'fill', source: 'omt', 'source-layer': 'landuse', paint: { 'fill-color': C.landuse, 'fill-opacity': 0.7 } },
      { id: 'park', type: 'fill', source: 'omt', 'source-layer': 'park', paint: { 'fill-color': C.park } },
      { id: 'water', type: 'fill', source: 'omt', 'source-layer': 'water', filter: ['!=', ['get', 'brunnel'], 'tunnel'], paint: { 'fill-color': C.water } },
      { id: 'waterway', type: 'line', source: 'omt', 'source-layer': 'waterway', paint: { 'line-color': C.waterLine, 'line-width': z([[8, 0.5], [16, 3]]) } },
      { id: 'building', type: 'fill', source: 'omt', 'source-layer': 'building', minzoom: 14, paint: { 'fill-color': C.building, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 14, 0, 15, 0.9] } },
      {
        id: 'road-minor', type: 'line', source: 'omt', 'source-layer': 'transportation', minzoom: 12,
        filter: ['in', ['get', 'class'], ['literal', ['minor', 'service', 'track']]],
        layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': C.minor, 'line-width': z([[12, 0.5], [18, 8]]) },
      },
      {
        id: 'road-major', type: 'line', source: 'omt', 'source-layer': 'transportation', minzoom: 6,
        filter: ['in', ['get', 'class'], ['literal', ['primary', 'secondary', 'tertiary', 'trunk']]],
        layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': C.major, 'line-width': z([[6, 0.4], [18, 14]]) },
      },
      {
        id: 'road-motorway', type: 'line', source: 'omt', 'source-layer': 'transportation', minzoom: 5,
        filter: ['==', ['get', 'class'], 'motorway'],
        layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': C.motorway, 'line-width': z([[5, 0.6], [18, 16]]) },
      },
      {
        id: 'rail', type: 'line', source: 'omt', 'source-layer': 'transportation', minzoom: 11,
        filter: ['in', ['get', 'class'], ['literal', ['rail', 'transit']]], paint: { 'line-color': C.rail, 'line-width': 1, 'line-dasharray': [3, 3] },
      },
      {
        id: 'boundary-country', type: 'line', source: 'omt', 'source-layer': 'boundary',
        filter: ['all', ['==', ['get', 'admin_level'], 2], ['!=', ['get', 'maritime'], 1]],
        paint: { 'line-color': C.boundary, 'line-width': z([[3, 0.8], [10, 2]]) },
      },
      {
        id: 'boundary-region', type: 'line', source: 'omt', 'source-layer': 'boundary', minzoom: 5,
        filter: ['all', ['==', ['get', 'admin_level'], 4], ['!=', ['get', 'maritime'], 1]],
        paint: { 'line-color': C.boundary, 'line-width': 0.8, 'line-dasharray': [2, 2], 'line-opacity': 0.6 },
      },
      {
        id: 'road-label', type: 'symbol', source: 'omt', 'source-layer': 'transportation_name', minzoom: 14,
        layout: { 'symbol-placement': 'line', 'text-field': name, 'text-font': FONT, 'text-size': 11 },
        paint: { 'text-color': C.label, 'text-halo-color': C.halo, 'text-halo-width': 1.2 },
      },
      {
        id: 'water-label', type: 'symbol', source: 'omt', 'source-layer': 'water_name',
        layout: { 'text-field': name, 'text-font': FONT, 'text-size': 11 }, paint: { 'text-color': '#56628a', 'text-halo-color': C.halo, 'text-halo-width': 1 },
      },
      {
        id: 'place-neighbourhood', type: 'symbol', source: 'omt', 'source-layer': 'place', minzoom: 12,
        filter: ['in', ['get', 'class'], ['literal', ['suburb', 'quarter', 'neighbourhood']]],
        layout: { 'text-field': name, 'text-font': FONT, 'text-size': 11, 'text-transform': 'uppercase', 'text-letter-spacing': 0.08 },
        paint: { 'text-color': '#7c7f99', 'text-halo-color': C.halo, 'text-halo-width': 1.2 },
      },
      {
        id: 'place-town', type: 'symbol', source: 'omt', 'source-layer': 'place', minzoom: 7,
        filter: ['in', ['get', 'class'], ['literal', ['town', 'village']]],
        layout: { 'text-field': name, 'text-font': FONT, 'text-size': z([[7, 10], [14, 14]]) },
        paint: { 'text-color': C.label, 'text-halo-color': C.halo, 'text-halo-width': 1.4 },
      },
      {
        id: 'place-city', type: 'symbol', source: 'omt', 'source-layer': 'place', minzoom: 4,
        filter: ['==', ['get', 'class'], 'city'],
        layout: { 'text-field': name, 'text-font': FONT, 'text-size': z([[4, 11], [12, 18]]) },
        paint: { 'text-color': C.labelStrong, 'text-halo-color': C.halo, 'text-halo-width': 1.6 },
      },
      {
        id: 'place-country', type: 'symbol', source: 'omt', 'source-layer': 'place', maxzoom: 7,
        filter: ['==', ['get', 'class'], 'country'],
        layout: { 'text-field': name, 'text-font': FONT, 'text-size': 13, 'text-transform': 'uppercase', 'text-letter-spacing': 0.12 },
        paint: { 'text-color': '#8b86b0', 'text-halo-color': C.halo, 'text-halo-width': 1.5 },
      },
    ],
  }
}
