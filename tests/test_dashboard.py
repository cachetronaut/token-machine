from pathlib import Path
import json

from fastapi.testclient import TestClient

from token_machine.dashboard.app import create_app
from token_machine.dashboard.icons import icon_filenames
from token_machine.models import AgentSource, AnalyticsEvent, EventType, TokenUsage
from token_machine.storage.repository import AnalyticsRepository


def test_fastapi_dashboard_routes_return_html_and_summary(tmp_path: Path) -> None:
    repository = AnalyticsRepository(tmp_path)
    repository.write_events(
        [
            AnalyticsEvent(
                event_id="e1",
                event_type=EventType.MODEL_CALL,
                source=AgentSource.CODEX,
                source_path="/tmp/session.jsonl",
                session_id="s1",
                timestamp="2026-05-08T10:00:00Z",
                model="gpt-5.4",
                token_usage=TokenUsage(input_tokens=1, total_tokens=1),
            ),
            AnalyticsEvent(
                event_id="e2",
                event_type=EventType.SKILL_CALL,
                source=AgentSource.CODEX,
                source_path="/tmp/session.jsonl",
                session_id="s1",
                timestamp="2026-05-08T10:00:01Z",
                model="gpt-5.4",
                skill_name="frontend-design",
            ),
            AnalyticsEvent(
                event_id="e3",
                event_type=EventType.TOOL_CALL,
                source=AgentSource.CODEX,
                source_path="/tmp/session.jsonl",
                session_id="s1",
                timestamp="2026-05-08T10:00:02Z",
                model="gpt-5.4",
                tool_name="exec_command",
                cli_name="uv",
                command="uv run pytest",
            ),
        ],
        [],
    )

    client = TestClient(create_app(tmp_path))
    html_response = client.get("/")
    summary_response = client.get("/api/summary")

    assert html_response.status_code == 200
    assert "Token Machine" in html_response.text
    assert "/assets/css/base.css" in html_response.text
    assert "/assets/css/live.css" in html_response.text
    assert "/assets/js/dashboard.js" in html_response.text
    assert "live-lanes" in html_response.text
    assert "live-agents" in html_response.text
    assert "prompts" in html_response.text
    assert "models-donut" in html_response.text
    assert "model-profiles" in html_response.text
    assert "recent-sessions" in html_response.text
    assert "daily-chart" in html_response.text
    assert "hourly-chart" in html_response.text
    assert "Signal charts" in html_response.text
    assert "model-profiles-wrap" in html_response.text
    assert html_response.text.index(
        '<section class="metrics">'
    ) < html_response.text.index('id="live-console"')
    assert "rankings" not in html_response.text
    assert summary_response.status_code == 200
    payload = summary_response.json()
    assert set(payload) >= {
        "generated_at",
        "summary",
        "daily",
        "hourly",
        "model_profiles",
        "recent_sessions",
    }
    assert set(payload["summary"]) >= {
        "generated_at",
        "event_count",
        "sessions",
        "sources",
        "models",
        "skill_calls",
        "command_calls",
        "tools",
        "skills",
        "executables",
        "clis",
        "event_types",
        "tokens",
        "descriptions",
    }
    assert set(payload["summary"]["tokens"]) >= {
        "input_tokens",
        "cached_input_tokens",
        "cache_creation_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
    }
    assert payload["summary"]["sessions"] == 1
    assert payload["summary"]["skill_calls"] == 1
    assert payload["summary"]["skills"] == {"frontend-design": 1}
    assert payload["summary"]["executables"] == {"Uv": 1}
    assert payload["summary"]["command_calls"] == 1
    assert isinstance(payload["daily"], list)
    assert isinstance(payload["hourly"], list)
    assert "rollup" in payload["recent_sessions"][0]
    assert payload["recent_sessions"][0]["rollup"]["skill_calls"] == 1
    assert payload["model_profiles"][0]["model"] == "gpt-5.4"


_STUB_SVG = '<svg xmlns="http://www.w3.org/2000/svg" height="1em" viewBox="0 0 24 24"><title>Icon</title></svg>'


def _seed_icons(store: Path) -> None:
    icons_dir = store / "cache" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    for name in icon_filenames():
        (icons_dir / name).write_text(_STUB_SVG, encoding="utf-8")


def test_fastapi_dashboard_serves_packaged_assets(tmp_path: Path) -> None:
    _seed_icons(tmp_path)
    client = TestClient(create_app(tmp_path))

    css_response = client.get("/assets/css/base.css")
    live_css_response = client.get("/assets/css/live.css")
    js_response = client.get("/assets/js/dashboard.js")
    font_response = client.get("/assets/fonts/orbitron-900.ttf")
    icon_response = client.get("/assets/icons/openai.svg")
    zed_response = client.get("/assets/icons/zed.svg")
    missing_response = client.get("/assets/icons/missing.svg")

    assert css_response.status_code == 200
    assert css_response.headers["content-type"].startswith("text/css")
    assert css_response.headers["cache-control"] == "no-store"
    assert live_css_response.status_code == 200
    assert "live-console" in live_css_response.text
    assert js_response.status_code == 200
    assert js_response.headers["content-type"].startswith("text/javascript")
    assert js_response.headers["cache-control"] == "no-store"
    assert font_response.status_code == 200
    assert font_response.headers["content-type"] == "font/ttf"
    assert font_response.headers["cache-control"] == "no-store"
    assert icon_response.status_code == 200
    assert icon_response.headers["content-type"].startswith("image/svg+xml")
    assert icon_response.headers["cache-control"] == "no-store"
    assert zed_response.status_code == 200
    assert zed_response.headers["content-type"].startswith("image/svg+xml")
    assert missing_response.status_code == 404


def test_fastapi_dashboard_serves_packaged_icon_fallbacks(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    zed_response = client.get("/assets/icons/zed.svg")

    assert zed_response.status_code == 200
    assert "<title>Zed</title>" in zed_response.text


def test_fastapi_dashboard_serves_lobe_icon_subset(tmp_path: Path) -> None:
    _seed_icons(tmp_path)
    client = TestClient(create_app(tmp_path))

    for icon_name in sorted(icon_filenames()):
        response = client.get(f"/assets/icons/{icon_name}")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/svg+xml")
        assert "<svg" in response.text
        assert 'height="1em"' in response.text
        assert "<title>" in response.text


def test_dashboard_uses_package_local_icon_urls_only() -> None:
    dashboard_js = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("src/token_machine/dashboard/assets/js").glob("*.js")
    )

    assert "/assets/icons/" in dashboard_js
    assert "https://" not in dashboard_js
    assert "http://" not in dashboard_js
    assert "unpkg.com" not in dashboard_js


def test_dashboard_uses_package_local_font_urls_only() -> None:
    dashboard_css = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("src/token_machine/dashboard/assets/css").glob("*.css")
    )

    assert "/assets/fonts/" in dashboard_css
    assert "fonts.googleapis.com" not in dashboard_css
    assert "fonts.gstatic.com" not in dashboard_css


def test_dashboard_live_surface_polls_live_api_and_debug_reload() -> None:
    dashboard_js = Path("src/token_machine/dashboard/assets/js/dashboard.js").read_text(
        encoding="utf-8"
    )
    api_js = Path("src/token_machine/dashboard/assets/js/api.js").read_text(
        encoding="utf-8"
    )
    live_js = Path("src/token_machine/dashboard/assets/js/live.js").read_text(
        encoding="utf-8"
    )

    assert 'from "./live.js"' in dashboard_js
    assert "/api/live" in api_js
    assert "/api/debug/reload" in api_js
    assert "startDebugReloadPolling" in dashboard_js
    assert "script_reload_token" in api_js
    assert "window.location.reload" in api_js
    assert "live-context-critical" in live_js
    assert "limitDisplayName" in live_js
    assert '"current"' in live_js
    assert '"weekly"' in live_js
    assert "live-tool-agent" in live_js
    assert "subagent_sessions" in live_js
    assert "session_limits" in live_js
    assert "Session limit pending" not in live_js
    assert "live-signal-compact" in live_js
    assert "live-signal-skill" in live_js
    assert "live-signal-command" in live_js
    assert "function liveActionKind" in live_js
    assert "tool.command" in live_js
    assert 'return "command";' in live_js
    assert "live_tool_calls" in live_js
    assert "live_actions" in live_js


def test_dashboard_typescript_sources_back_packaged_javascript() -> None:
    ts_dir = Path("src/token_machine/dashboard/assets/ts")
    js_dir = Path("src/token_machine/dashboard/assets/js")

    source_modules = {path.stem for path in ts_dir.glob("*.ts")}
    generated_modules = {path.stem for path in js_dir.glob("*.js")}

    assert {
        "api",
        "charts",
        "dashboard",
        "format",
        "icons",
        "intro",
        "live",
        "models",
        "sections",
        "sessions",
        "types",
    } <= source_modules
    assert source_modules <= generated_modules


def test_dashboard_typescript_build_scripts_are_registered() -> None:
    package = json.loads(Path("package.json").read_text(encoding="utf-8"))

    assert package["scripts"]["typecheck"] == "tsc --noEmit"
    assert package["scripts"]["build:dashboard"] == "tsc -p tsconfig.json"
    assert "scripts/check-dashboard-build.mjs" in package["scripts"]["check:dashboard"]


def test_dashboard_renames_cli_surface_to_executables() -> None:
    charts_html = Path(
        "src/token_machine/dashboard/templates/partials/charts.html"
    ).read_text(encoding="utf-8")
    dashboard_js = Path("src/token_machine/dashboard/assets/js/dashboard.js").read_text(
        encoding="utf-8"
    )

    assert "<h2>Executables</h2>" in charts_html
    assert "<h2>Skills</h2>" in charts_html
    assert "<h2>CLIs</h2>" not in charts_html
    assert 'renderBars("executables"' in dashboard_js
    assert 'renderBars("skills"' in dashboard_js


def test_dashboard_icon_mappings_include_zed_and_openrouter_models() -> None:
    icons_js = Path("src/token_machine/dashboard/assets/js/icons.js").read_text(
        encoding="utf-8"
    )

    assert 'key.includes("zed")' in icons_js
    assert 'return "zed.svg";' in icons_js
    assert 'key.includes("opencode")' in icons_js
    assert 'return "opencode.svg";' in icons_js
    assert 'return "openrouter.svg";' in icons_js
    assert 'return "deepseek.svg";' in icons_js
    assert 'return "meta.svg";' in icons_js
    assert "icon-on-dark" in icons_js


def test_model_card_front_uses_rank_medallions_without_back_badges() -> None:
    models_js = Path("src/token_machine/dashboard/assets/js/models.js").read_text(
        encoding="utf-8"
    )
    model_cards_html = Path(
        "src/token_machine/dashboard/templates/partials/model_cards.html"
    ).read_text(encoding="utf-8")

    assert '<div class="provider-logo">${renderProviderLogo(row)}</div>' in models_js
    assert '<div class="model-art">${renderModelHero(row)}</div>' in models_js
    assert "renderRankMedallions(row, 3)" in models_js
    assert 'renderTopList("skills", row.skills, row.skill_calls, 2)' in models_js
    assert (
        'renderTopList("executables", row.executables || row.clis, row.command_calls, 2)'
        in models_js
    )
    assert "avg tokens / call" in models_js
    assert "median first action" not in models_js
    assert "function renderBackStatMatrix" not in models_js
    assert "${renderBackStatMatrix(row)}" not in models_js
    assert "recorded + computed + inferred" not in models_js
    assert "scouting_report" not in models_js
    assert "model-tools" not in models_js
    assert "renderIntelligenceBadges" not in models_js
    assert "renderModelBadgeIcon" not in models_js
    assert "levelIcon" not in models_js
    assert "badge-legend" in model_cards_html
    assert "badge-legend-item" in model_cards_html
    assert "badge-legend-track" in model_cards_html
    assert "ops-badge" not in model_cards_html
    assert "Elite toolist" not in model_cards_html
