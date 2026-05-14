---
status: stable
date: 2026-05-14
description: Why signal chart dots became ellipses, and why renaming `.chart-head` was forced — two reusable lessons from the dashboard chart-dot polish pass.
keywords: [svg, preserveAspectRatio, dashboard, charts, css, class-collision, html-overlay, circles]
---

# Chart overlay circles and class collisions

Two reusable nuances surfaced while making the Daily Flow and Recent Activity dot markers perfectly circular and stylistically unified with the line.

## SVG `preserveAspectRatio="none"` distorts every circle inside it

The signal charts render through `chartSvg()` in `src/token_machine/dashboard/assets/js/charts.js` with a `viewBox="0 0 760 260"` and `preserveAspectRatio="none"`. That tells the browser to stretch the SVG non-uniformly to fill the container, which is what we want for the line/area (they should hug the card edges), but it also means **every `<circle>` inside the SVG gets squashed into an ellipse** because the X and Y axes scale by different factors.

There is no clean SVG-only escape:
- `vector-effect="non-scaling-stroke"` only fixes stroke width, not shape.
- Switching to `xMidYMid meet` letterboxes the chart — visually worse.
- Compensating with `<ellipse rx/ry>` requires recomputing on every resize.

The aesthetic winner is a hybrid: keep `preserveAspectRatio="none"` on the SVG (so line/area/grid still fill edge-to-edge), and move anything that must stay perfectly round — dots, head ball, halo — into an HTML overlay layer that sits absolutely positioned over the SVG. Pixel-sized `border-radius: 50%` divs are immune to the container's aspect ratio.

Pattern:
- Wrap the chart in a `position: relative` `<div>` (not the `<svg>` itself).
- Render `<svg>` for line/area/grid, sized via the global `svg { width: 100%; height: 260px }` rule.
- Render a sibling `<div class="...-overlay">` with `position: absolute; inset: 0`, holding pixel-sized circular divs positioned via `left: X%; top: Y%` computed from viewBox coordinates (`x / viewW * 100`).

When the line is progress-clipped via SVG `clipPath`, the overlay must be revealed in sync. Use `clip-path: inset(0 calc(100% - var(--reveal, 0%)) 0 0)` on the overlay layer and set `--reveal` to the head's left percentage each animation frame. Add small negative top/bottom inset values to keep dot glows from getting clipped.

## Always grep before adding a generic class name

I added a `.chart-head` div to wrap the leading marker in the new HTML overlay. The card already had `<div class="chart-head">` for the title row (h2 + eyebrow + toggle buttons) in `partials/charts.html`. My new CSS — `.chart-head { position: absolute; width: 0; height: 0 }` — silently collapsed the card header, hiding "Daily flow" / "Recent activity" titles.

How to apply: before introducing any new class name in shared CSS, grep both CSS and templates for that exact selector. Generic names like `head`, `body`, `card`, `tag`, `pill`, `item` are landmines in CSS that has grown organically. When in doubt, prefix with the feature scope (`chart-marker` instead of `chart-head`, `signal-overlay` instead of `overlay`).

## Where this matters next

- Any future chart variant in `assets/js/charts.js` should keep dots/markers in the overlay layer rather than as SVG circles.
- The value-tag pill is still inside the SVG and therefore still distorts horizontally with the container width — fair candidate for the same overlay treatment if it ever needs visual polish.
