# Pharos - Redesign Handoff

For Claude Code to apply against the Next.js + Tailwind + Recharts dashboard.
Final picks are locked: **Home A - Brief**, **Drug Profile C - Methodology
Brief**, **Signal Scores B - Hybrid**. The design source of truth lives in
this project -- `pharos-tokens.ts`, `pharos-tokens.css`, and the
`pharos-*.jsx` files. This doc tells you what to change and why.

---

## 1. Decisions baked in

- **Single amber accent.** `#E0A458`. Used for flagged signals, primary
  actions, point estimates on forest plots, null reference line, info dots.
  Nothing else is coloured. The previous generic blue is removed.
- **Near-black base.** `#07090b` page, `#0c0f12` surfaces. Carries enough
  warmth to sit under amber without fighting it.
- **Type hierarchy:** Inter Tight (display + body, `letter-spacing:
  -0.02em` on headings) + JetBrains Mono (all numeric data, `tabular-nums`
  on). Drug names render at display weight; signal counts as mono numerals.
- **No pills.** Maximum border-radius `6px`. Inputs/chips `2px`. Chart
  axes and table cells are square.
- **No multi-colour badges.** Single `tag-flag` component with amber wash.
  Not-flagged / below-null is rendered in `--ink-300/400/500`, never red.
  The "serious: Yes" red pill on the current dashboard is replaced by a
  single-character indicator (filled/empty circle).

---

## 2. Token plumbing

Design tokens live in `dashboard/lib/design-tokens.ts`.

See `tailwind.config.ts` and `app/globals.css` for consumption.

---

## 3-9. See inline comments in implementation files.
