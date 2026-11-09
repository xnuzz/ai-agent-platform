/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  /** Local Business Finder basemap overrides (see src/features/localFinder/mapStyle.ts). */
  readonly VITE_MAP_STYLE_URL?: string
  readonly VITE_MAP_TILES_URL?: string
  readonly VITE_MAP_GLYPHS_URL?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
