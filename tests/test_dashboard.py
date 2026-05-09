from pathlib import Path

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
            )
        ],
        [],
    )

    client = TestClient(create_app(tmp_path))
    html_response = client.get("/")
    summary_response = client.get("/api/summary")

    assert html_response.status_code == 200
    assert "Token Machine" in html_response.text
    assert "/assets/css/base.css" in html_response.text
    assert "/assets/js/dashboard.js" in html_response.text
    assert "models-donut" in html_response.text
    assert "model-profiles" in html_response.text
    assert "recent-sessions" in html_response.text
    assert "daily-chart" in html_response.text
    assert "hourly-chart" in html_response.text
    assert summary_response.status_code == 200
    payload = summary_response.json()
    assert payload["summary"]["sessions"] == 1
    assert "rollup" in payload["recent_sessions"][0]
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
    js_response = client.get("/assets/js/dashboard.js")
    icon_response = client.get("/assets/icons/openai.svg")
    zed_response = client.get("/assets/icons/zed.svg")
    missing_response = client.get("/assets/icons/missing.svg")

    assert css_response.status_code == 200
    assert css_response.headers["content-type"].startswith("text/css")
    assert js_response.status_code == 200
    assert js_response.headers["content-type"].startswith("text/javascript")
    assert icon_response.status_code == 200
    assert icon_response.headers["content-type"].startswith("image/svg+xml")
    assert zed_response.status_code == 200
    assert zed_response.headers["content-type"].startswith("image/svg+xml")
    assert missing_response.status_code == 404

    # Test image asset serving (using placeholder created in setup or here)
    img_response = client.get("/assets/img/logo.png")
    assert img_response.status_code == 200
    assert img_response.headers["content-type"] == "image/png"


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


def test_dashboard_icon_mappings_include_zed_and_openrouter_models() -> None:
    icons_js = Path("src/token_machine/dashboard/assets/js/icons.js").read_text(
        encoding="utf-8"
    )

    assert 'if (key.includes("zed")) return "zed.svg";' in icons_js
    assert 'return "openrouter.svg";' in icons_js
    assert 'return "deepseek.svg";' in icons_js
    assert 'return "meta.svg";' in icons_js
