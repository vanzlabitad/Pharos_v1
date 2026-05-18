/**
 * Pharos design tokens — single source of truth.
 *
 * Colour: single baby-blue accent on near-black base.
 * Type:   Inter Tight (display + body) + JetBrains Mono (data).
 * Radius: max 6px; inputs/chips 2px; chart elements 0.
 */

// ── Colour ──────────────────────────────────────────────────────────────────

export const bg = {
  page: "#07090b",
  surf: "#0c0f12",
  raised: "#12161b",
  overlay: "rgba(7, 9, 11, 0.85)",
} as const;

export const ink = {
  100: "#f4f5f7",
  200: "#d1d5db",
  300: "#9ca3af",
  400: "#6b7280",
  500: "#4b5563",
  600: "#374151",
} as const;

export const accent = {
  DEFAULT: "#5EBBF0",
  wash: "rgba(94, 187, 240, 0.10)",
  line: "rgba(94, 187, 240, 0.55)",
  muted: "rgba(94, 187, 240, 0.35)",
  text: "#5EBBF0",
} as const;

export const semantic = {
  flagged: "#5EBBF0",
  unflagged: "#6b7280",
  null_ref: "rgba(94, 187, 240, 0.55)",
} as const;

export const border = {
  hair: "rgba(244, 245, 247, 0.06)",
  rule: "rgba(244, 245, 247, 0.10)",
  edge: "rgba(244, 245, 247, 0.15)",
} as const;

// ── Typography ──────────────────────────────────────────────────────────────

export const font = {
  display: ['"Inter Tight"', "system-ui", "sans-serif"],
  body: ['"Inter Tight"', "system-ui", "sans-serif"],
  mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
} as const;

export const letterSpacing = {
  display: "-0.02em",
  drugName: "-0.04em",
  data: "0",
} as const;

// ── Spacing ─────────────────────────────────────────────────────────────────

export const spacing = {
  xs: "4px",
  sm: "8px",
  md: "16px",
  lg: "24px",
  xl: "32px",
  "2xl": "48px",
  "3xl": "64px",
} as const;

// ── Radius ──────────────────────────────────────────────────────────────────

export const radius = {
  sharp: "0",
  xs: "2px",
  sm: "4px",
  md: "6px",
} as const;

// ── Motion ──────────────────────────────────────────────────────────────────

export const motion = {
  fast: "120ms ease-out",
  normal: "200ms ease-out",
  slow: "350ms ease-out",
} as const;

// ── Recharts theme ──────────────────────────────────────────────────────────

export const rechartsTheme = {
  axisStroke: ink[500],
  axisTickFill: ink[400],
  gridStroke: border.hair,
  tooltipBg: bg.raised,
  tooltipBorder: border.edge,
  tooltipText: ink[100],
  accentFill: accent.DEFAULT,
  accentStroke: accent.DEFAULT,
  mutedFill: ink[500],
} as const;

// ── Forest plot constants ───────────────────────────────────────────────────

export const forestPlot = {
  scaleMin: 0.1,
  scaleMax: 100,
  nullLine: 1,
  nullLineColor: accent.line,
  nullWash: "rgba(94, 187, 240, 0.10)",
  flaggedDotR: 5.5,
  unflaggedDotR: 4,
  flaggedColor: accent.DEFAULT,
  flaggedHalo: accent.line,
  unflaggedColor: ink[300],
  arrowColor: ink[400],
  rowH: 28,
  leftCol: 210,
  rightCol: 280,
  defaultWidth: 900,
} as const;

// ── CSS custom properties (for :root injection) ─────────────────────────────

export const cssVars = {
  "--bg-page": bg.page,
  "--bg-surf": bg.surf,
  "--bg-raised": bg.raised,
  "--bg-overlay": bg.overlay,
  "--ink-100": ink[100],
  "--ink-200": ink[200],
  "--ink-300": ink[300],
  "--ink-400": ink[400],
  "--ink-500": ink[500],
  "--ink-600": ink[600],
  "--accent": accent.DEFAULT,
  "--accent-wash": accent.wash,
  "--accent-line": accent.line,
  "--accent-muted": accent.muted,
  "--border-hair": border.hair,
  "--border-rule": border.rule,
  "--border-edge": border.edge,
  "--font-display": font.display.join(", "),
  "--font-body": font.body.join(", "),
  "--font-mono": font.mono.join(", "),
} as const;
