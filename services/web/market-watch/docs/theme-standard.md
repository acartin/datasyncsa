# Market Watch Theme Standard

This document defines how Market Watch standardizes theme configuration on top of `shadcn/ui` and Tailwind, so a theme chosen later from `tweakcn`, `shadcn`, or another compatible source can be applied with minimal friction.

## 1. Goal

The goal is not to bind the product to one visual preset. The goal is to define a stable contract between:

- external theme sources such as `tweakcn`
- Market Watch semantic tokens
- shared UI primitives
- dense operational surfaces such as grids, toolbars, tabs, KPI cards, and product workspaces

## 2. Layers

Theme configuration is standardized in four layers.

### Layer A: Foundation Tokens

Defined in `app/globals.css`.

- font family
- base text sizes and line heights
- radius
- surfaces
- borders
- semantic colors
- chart palette
- density heights

These are raw design tokens, not screen-specific styles.

### Layer B: Semantic Tailwind Mapping

Defined in `tailwind.config.ts`.

- color aliases like `bg-card`, `text-muted-foreground`, `border-border-2`
- semantic typography like `text-page-title`, `text-grid-cell`, `text-kpi-label`
- density spacing like `h-control`, `h-control-sm`, `h-grid-row`

This is the public contract components should consume.

### Layer C: Shared Component Mapping

Defined in shared components under:

- `components/ui/*`
- `components/market-watch/data-grid.tsx`
- `components/market-watch/kpi-card.tsx`
- `components/portal/*`

These components should prefer semantic typography and density tokens over one-off pixel classes.

### Layer D: Screen Composition

Page and feature components should compose existing component primitives and only make local typography decisions when genuinely necessary.

## 3. Token Groups

### 3.1 shadcn-compatible tokens

These align closely with common `shadcn/ui` theme inputs:

- `--background`
- `--foreground`
- `--card`
- `--card-foreground`
- `--primary`
- `--primary-hover`
- `--primary-foreground`
- `--secondary`
- `--secondary-foreground`
- `--muted`
- `--muted-foreground`
- `--accent`
- `--accent-foreground`
- `--destructive`
- `--destructive-foreground`
- `--input`
- `--ring`
- `--radius`

### 3.2 Market Watch extension tokens

These cover dashboard and operational needs not standardized by `shadcn`:

- `--surface`
- `--surface-2`
- `--surface-3`
- `--surface-hover`
- `--surface-selected`
- `--border`
- `--border-2`
- `--border-strong`
- `--ink-primary`
- `--ink-secondary`
- `--ink-muted`
- `--shadow-color`
- `--overlay`
- semantic state colors
- chain chip colors
- chart series colors
- navigation state colors

## 4. Typography Contract

Typography should be referenced semantically, not by scattered ad hoc sizes.

### Typography tokens

- `text-page-title`
- `text-page-subtitle`
- `text-section-title`
- `text-card-title`
- `text-body`
- `text-body-sm`
- `text-label`
- `text-meta`
- `text-grid-header`
- `text-grid-cell`
- `text-kpi-value`
- `text-kpi-label`

### Intended usage

- `text-page-title`: workspace and page headers
- `text-page-subtitle`: descriptive copy under headers
- `text-section-title`: section labels, panel titles
- `text-card-title`: card header titles
- `text-body`: default body copy
- `text-body-sm`: controls, tabs, dense interface text
- `text-label`: form labels, compact UI labels
- `text-meta`: helper text, tenant metadata, minor annotations
- `text-grid-header`: table headers
- `text-grid-cell`: table cells
- `text-kpi-value`: KPI numeric value
- `text-kpi-label`: KPI caption

## 5. Density Contract

Operational UI should also be standardized semantically.

### Density tokens

- `h-control`
- `h-control-sm`
- `h-control-lg`
- `h-grid-row`
- `h-toolbar`

### Intended usage

- `h-control`: default input/button height
- `h-control-sm`: chips, compact selectors, toolbar micro-actions
- `h-control-lg`: prominent filters or larger form controls
- `h-grid-row`: default grid row target height
- `h-toolbar`: toolbar container target height

## 6. Mapping External Themes

When importing a theme from `tweakcn` or a compatible source:

1. Map the shadcn-compatible tokens first.
2. Derive Market Watch extension tokens from that palette.
3. Keep typography and density contract stable unless the theme change explicitly includes a scale update.
4. Validate grids, KPI cards, sidebar, topbar, tabs, and product detail pages before considering the theme applied.

## 7. Non-goals

This standard intentionally avoids:

- a parallel CSS framework beside Tailwind and `shadcn`
- per-page bespoke pixel scales
- dozens of global utility classes with unclear ownership
- direct color literals in feature components when semantic tokens already exist

## 8. Migration Rule

When refactoring existing UI:

1. replace repeated raw size classes with semantic typography where possible
2. move density defaults into shared primitives
3. keep exceptions local and documented by context

The desired end state is fewer arbitrary classes in screens, not more.
