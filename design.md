# Design — DAYMARK

A shared design system for the DAYMARK task workspace. All app views use this system; preserve route behavior and task semantics.

## Genre
Modern-minimal, with a calm workspace tone inspired by Notion's restrained surfaces and navigation. This is an original adaptation, not a pixel copy.

## Macrostructure family
- App pages: Workbench — persistent workspace navigation, compact page toolbar, focused content column.
- Forms: Workbench detail — one clear form surface with a quiet page title and actions grouped at the end.
- Data views: Workbench list/grid — scanning and direct manipulation take priority over decoration.

## Theme
- `--color-paper`: `oklch(99% 0.004 95)`
- `--color-paper-2`: `oklch(97% 0.006 95)`
- `--color-paper-3`: `oklch(94% 0.008 95)`
- `--color-ink`: `oklch(22% 0.008 75)`
- `--color-ink-2`: `oklch(43% 0.009 75)`
- `--color-muted`: `oklch(58% 0.008 75)`
- `--color-rule`: `oklch(89% 0.006 85)`
- `--color-accent`: `oklch(42% 0.012 75)`
- `--color-accent-soft`: `oklch(95% 0.006 75)`
- `--color-focus`: `oklch(61% 0.13 25)`
- Status colors are low-chroma semantic tokens; category colors remain user-defined.

## Typography
- Display: Inter, weight 600, roman.
- Body: Inter, weight 400.
- Mono: system monospace stack for Git output.
- Headings are compact and left-aligned; no display-scale hero typography.

## Spacing and shape
Use the named 4-point spacing scale in `static/app.css`. Surfaces use visible quiet borders and a 6px radius. Controls retain stable 34–38px heights.

## Motion
No reveal animation. Use short color and border transitions only; honor reduced motion.

## Microinteractions
- Primary actions use graphite fill; secondary actions stay quiet until hovered or focused.
- Focus rings are visible and coral-tinted.
- Task row actions remain discoverable on touch devices.
- Destructive actions remain distinct and keep their existing confirmation behavior.

## Per-page allowances
- App pages use existing data only; no invented metrics, onboarding copy, or decorative illustrations.
- Calendar and task lists prioritize density, legibility, and direct navigation.
- Forms preserve existing labels, names, values, and submission behavior.

## What pages must share
- DAYMARK wordmark and workspace navigation.
- Warm-neutral surfaces, graphite text, consistent borders, and compact controls.
- Inter typography, focus treatment, and status semantics.
