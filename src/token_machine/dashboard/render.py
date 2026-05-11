"""Dashboard HTML rendering."""

from __future__ import annotations

from jinja2 import Environment, PackageLoader, select_autoescape

from token_machine.dashboard.view_models import DashboardViewModel

DASHBOARD_VIEW_MODEL = DashboardViewModel(
    title="Token Machine",
    subtitle="Local CLI-agent usage across Codex, Claude, Gemini, and future agents.",
    css_assets=(
        "/assets/css/base.css",
        "/assets/css/layout.css",
        "/assets/css/live.css",
        "/assets/css/charts.css",
        "/assets/css/model-cards.css",
        "/assets/css/timeline.css",
    ),
    js_entrypoint="/assets/js/dashboard.js",
    logo_path="/assets/img/logo.png",
)

_ENVIRONMENT = Environment(
    loader=PackageLoader("token_machine.dashboard", "templates"),
    autoescape=select_autoescape(("html", "xml")),
)


def render_dashboard() -> str:
    template = _ENVIRONMENT.get_template("dashboard.html")
    return template.render(dashboard=DASHBOARD_VIEW_MODEL)
