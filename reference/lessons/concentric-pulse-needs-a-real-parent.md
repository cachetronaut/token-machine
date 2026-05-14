---
status: stable
date: 2026-05-14
description: Why the recent-sessions current-item ring kept rendering off-center, and the rule that fixed it — concentric pulse rings must live as `::after` on a real DOM element, not as a sibling pseudo to a `::before` dot.
keywords: [css, pseudo-elements, pulse, ring, centering, dashboard, timeline, live-state, inset]
---

# Concentric pulse rings need a real parent element

The dashboard has a canonical "radar ping" recipe in `.live-state::after` (see `src/token_machine/dashboard/assets/css/live.css`): a static dot is a real `<span>`, and a `::after` pseudo on that span uses `inset: -5px` to draw a ring that pulses outward via `scale()`. Because `inset` is symmetric on all four sides, the ring is automatically concentric with the dot — there is no math to get wrong.

The recent-sessions timeline (`src/token_machine/dashboard/assets/css/timeline.css`) tried to replicate this pattern using **two sibling pseudo-elements** on `.timeline-item`: `::before` for the dot, `::after` for the ring. Both were absolutely positioned using independent `calc()` offsets that *should have* landed at the same center. They never quite did — across multiple iterations the ring appeared off-center in screenshots, and each "fix" tweaked offsets without addressing the root cause.

## Why sibling-pseudo centering is fragile

When two absolutely-positioned siblings each have their own `top` / `left` / `width` / `height` math, they have two independent opportunities to be wrong:

- One pseudo's offsets bake in `size/2`, the other bakes in `size`. Any divergence — subpixel rounding at non-integer DPR, CSS variable precision, an unnoticed `border` widening the box under `content-box` — shifts one relative to the other.
- In a flex or grid parent, both pseudos use the parent's padding box as their containing block, but visually verifying that requires inspecting computed styles. The math looks right on paper and still renders wrong.
- There is no structural guarantee that the two centers coincide. The dev has to maintain that invariant by hand every time either size changes.

## The rule

> **For a ring that must be concentric with a dot, put the ring as `::after` on the same element that is the dot — not as a sibling pseudo.**

The dot must therefore be a real DOM element (a `<span>`), since pseudo-elements cannot have their own pseudos. Then the ring uses `inset: -Xpx` (or equivalent symmetric offsets) on that span. Concentricity becomes a structural property of the CSS, not a computed coincidence.

## What the fix looks like

In `sessions.ts` the timeline-item now renders an explicit dot span:

```html
<div class="timeline-item session-item session-item-current" style="--project-color:...">
  <span class="timeline-dot" aria-hidden="true"></span>
  <div class="time-label">...</div>
  <div class="timeline-card">...</div>
</div>
```

In `timeline.css` the ring lives on the dot, mirroring `.live-state::after` exactly:

```css
.timeline-dot {
  position: absolute;
  /* anchored to the rail via top/left + negative margins */
}

.timeline-dot::after {
  position: absolute;
  inset: -5px;
  border: 1px solid var(--project-color);
  border-radius: inherit;
  content: "";
  opacity: 0;
}

.session-item-current .timeline-dot::after {
  animation: session-dot-pulse var(--motion-cadence) ease-out infinite;
}
```

## When this applies

Any time the design calls for one circular element to pulse outward from another. Examples in this repo: `.live-state` (canonical), recent-sessions current item (this fix). If a future surface needs the same effect, copy the structural pattern — a real element + `::after` with `inset` — rather than reinventing the dual-pseudo math.

## Adjacent lesson: reuse the canonical signal, don't parallel-implement it

When a recipe already exists and works (here, `.live-state::after` with `inset:-Xpx`), match its **structure**, not just its visual output. Parallel implementations that compute "the same" geometry through different math will drift; structurally identical implementations cannot.
