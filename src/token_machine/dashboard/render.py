"""Dashboard HTML rendering."""

from __future__ import annotations

from token_machine.dashboard.static import CSS, JS


def render_dashboard() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Token Machine</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Token Machine</h1>
      <div class="sub">Local CLI-agent usage, refreshed from this machine.</div>
    </div>
    <div class="status" id="status">Connecting</div>
  </header>
  <section class="grid metrics">
    <div class="card"><div class="label">Sessions</div><div class="value" id="metric-sessions">0</div></div>
    <div class="card"><div class="label">Events</div><div class="value" id="metric-events">0</div></div>
    <div class="card"><div class="label">Model calls</div><div class="value" id="metric-model-calls">0</div></div>
    <div class="card"><div class="label">Tokens</div><div class="value" id="metric-tokens">0</div></div>
  </section>
  <section class="grid columns">
    <div class="card"><h2>Models</h2><div id="models"></div></div>
    <div class="card"><h2>Tools</h2><div id="tools"></div></div>
  </section>
  <section class="grid columns">
    <div class="card"><h2>CLIs</h2><div id="clis"></div></div>
    <div class="card"><h2>Recent Sessions</h2><div class="timeline" id="sessions-list"></div></div>
  </section>
</main>
<script>{JS}</script>
</body>
</html>
"""
