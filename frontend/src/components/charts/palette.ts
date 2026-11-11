/**
 * Monochrome categorical ramp for part-to-whole charts on the dark surface (brightest first).
 * Identity is never shade-alone: every chart using it also prints labels/values in a legend.
 */
export const MONO_RAMP = ['#fafafa', '#b4b4bb', '#80808a', '#55555c', '#3a3a40', '#2a2a2f'] as const
export const monoShade = (i: number) => MONO_RAMP[Math.min(i, MONO_RAMP.length - 1)]!
