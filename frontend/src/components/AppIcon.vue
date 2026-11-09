<script lang="ts">
/** Minimal 24px line icons (white via currentColor). One file, no icon library. */
const c = (x: number, y: number, r: number) => `M${x - r} ${y}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`
const PATHS = {
  dashboard: 'M4 5a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1zM13 5a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1zM13 12a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1zM4 15a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z',
  finder: `M12 21s-6.5-5.6-6.5-10.5a6.5 6.5 0 1 1 13 0C18.5 15.4 12 21 12 21z${c(12, 10.5, 2.3)}`,
  tasks: 'M8 7h8a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1zM10 10h4v4h-4zM9.5 3v3M14.5 3v3M9.5 18v3M14.5 18v3M3 9.5h3M3 14.5h3M18 9.5h3M18 14.5h3',
  approvals: 'M12 3l7 3v5c0 4.6-3 8.2-7 10-4-1.8-7-5.4-7-10V6zM9 12l2.2 2.2L15.5 10',
  ideas: 'M9.5 18h5M10.5 21h3M12 3a6 6 0 0 0-3.8 10.6c.8.7 1.3 1.6 1.3 2.6V17h5v-.8c0-1 .5-1.9 1.3-2.6A6 6 0 0 0 12 3z',
  leads: `${c(9, 8, 3.2)}M3.5 20c0-3.2 2.5-5.5 5.5-5.5s5.5 2.3 5.5 5.5M16 4.8a3.2 3.2 0 0 1 0 6.4M20.5 20c0-2.5-1.5-4.6-3.8-5.3`,
  campaigns: 'M21 3 3.5 10.2l7 2.8 2.8 7zM10.5 13 14.5 9',
  suppression: `${c(12, 12, 8.5)}M6 6l12 12`,
  settings: `M4 7h9M17 7h3M4 12h3M11 12h9M4 17h11M19 17h1${c(15, 7, 2)}${c(9, 12, 2)}${c(17, 17, 2)}`,
  audit: 'M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM9 8h6M9 12h6M9 16h3.5',
  logout: 'M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4M10 16l-4-4 4-4M6 12h10',
  menu: 'M4 7h16M4 12h16M4 17h16',
  close: 'M6 6l12 12M18 6 6 18',
  collapse: 'M15 6l-6 6 6 6',
  expand: 'M9 6l6 6-6 6',
  search: `${c(11, 11, 6.5)}M16 16l4 4`,
  bell: 'M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0',
  plus: 'M12 5v14M5 12h14',
  spark: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18',
} as const
export type IconName = keyof typeof PATHS
</script>

<script setup lang="ts">
defineProps<{ name: IconName; size?: number }>()
</script>

<template>
  <svg :width="size ?? 18" :height="size ?? 18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="shrink-0"><path :d="PATHS[name]" /></svg>
</template>
