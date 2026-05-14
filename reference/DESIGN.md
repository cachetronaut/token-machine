---
status: draft
date: 2026-05-14
description: Current visual and brand reference for the Token Machine dashboard.
keywords:
  - dashboard
  - design
  - brand
  - typography
  - theme
  - visual system
---

# DESIGN.md

## Purpose

This document records the current Token Machine dashboard visual system. Use it when changing dashboard templates, CSS, JavaScript rendering, icons, or bundled assets.

## Brand position

Token Machine is a local telemetry console for CLI-agent work. The UI should feel like a dense sci-fi operations dashboard, not a marketing page and not a generic admin template.

The brand signal is the `Token Machine` wordmark, local telemetry language, and the blue-to-teal technical palette. The checked-in brand mark is `src/token_machine/dashboard/assets/icons/logo-tm.svg`.

## Visual tone

- Use a dark operating surface with compact cards, clear section strips, and data-first hierarchy.
- Keep the interface dense enough for repeated analytics work.
- Use motion as a telemetry cue: live state, chart progress, section state, current sessions, and intro playback.
- Avoid decorative badges, ungrounded chips, broad hero layouts, and generic purple-gradient SaaS styling.
- Keep runtime assets local. Do not depend on a CDN, npm build output, or remote fonts while rendering the dashboard.

## Color

The active palette lives in `src/token_machine/dashboard/assets/css/base.css`.

- Background: `#111111` with darker panel gradients.
- Core text: `#fcfcfc`.
- Muted text: `#9da4ad`.
- Brand gradient: `#9BC2FF`, `#6BA6FF`, and `#43C7B7`.
- Codex accent: `#0169cc`.
- Claude accent: `#c15f3c` and related warm variants.
- Signal colors: teal for tokens, amber for events, blue for sessions, violet for models, green for tools, sky for skills, and coral for commands.

Use color to identify source, model, or metric state. Do not introduce a new dominant theme color unless it is added as a named token in `base.css`.

## Typography

The dashboard uses local fonts served through `/assets/fonts/`.

- `Orbitron` is the brand font. Use it for the main wordmark and intro wordmark.
- `Teko` is the display font. Use it for section titles, card titles, labels, model-card titles, and compact uppercase UI text.
- `Share Tech Mono` is the numeric and technical font. Use it for counters, timestamps, status text, telemetry values, and chart labels.
- Body copy uses the local system sans stack defined by `--font-body`.

Do not add remote font URLs. Do not replace the display stack with generic body-font headings.

## Layout

The first screen is the working dashboard. It starts with:

1. Header and connection status.
2. Global metrics.
3. Live Context.
4. Signal charts.
5. Models.
6. Recent sessions.

The dashboard uses full-width sections inside a constrained `main` container. Cards are for repeated metric panels, chart panels, model cards, and framed tool surfaces. Do not wrap full page sections in decorative nested cards.

## Components

### Header

The header centers the `Token Machine` wordmark and keeps connection state on the right. The wordmark uses the brand gradient and `Orbitron`.

### Global metrics

Metric cards summarize sessions, events, model calls, and tokens. Each card uses a left-edge color strip and mono numeric values.

### Live Context

Live Context is a collapsible telemetry console. It shows active sessions, prompt counts, tools, agents, tokens, per-session lanes, context usage, session limits, compaction events, and current tool/action activity.

### Signal charts

Signal charts group daily flow, recent activity, tools, skills, and executables. Chart toggles should switch only the targeted chart when cached summary data is available.

### Models

The Models section contains model distribution and collectible-card-style model cards. Model cards use provider icons when available and initials as fallback. Rank medallions are deterministic usage badges, not decorative labels.

### Recent sessions

Recent sessions render as a timeline. The rail and dots are part of the live activity language. Dots must remain above the rail and stay readable on dark surfaces.

### Intro

The intro overlay is a one-per-session brand moment. It uses the same wordmark, grid, scan, warp, and teal signal language as the dashboard. It must respect `prefers-reduced-motion`.

## Icons and assets

Source and model icons are resolved in `src/token_machine/dashboard/assets/js/icons.js` and served from `/assets/icons/`. The dashboard can use cached SVGs from `store/cache/icons/`, with packaged fallbacks in `src/token_machine/dashboard/assets/icons/`.

Icons that render dark on dark surfaces must receive `icon-on-dark` treatment. Unknown icons must fall back to dots or initials rather than broken images.

## Motion

Motion should be slow, legible, and tied to data state.

- Live LEDs and current-session dots pulse on the shared motion cadence.
- Chart motion should describe progress through data, then settle.
- Section and chart mode switches may animate, but must not reload unrelated   surfaces.
- All recurring motion must be disabled or reduced under `prefers-reduced-motion`.
