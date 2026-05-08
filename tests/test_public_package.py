from pathlib import Path

from token_machine.dashboard.icons import LOBE_ICONS_PACKAGE


def test_public_package_has_no_private_product_names() -> None:
    private_name = "Ko" + "modo"
    root = Path(__file__).resolve().parents[1]
    ignored_dirs = {".git", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__"}
    checked_suffixes = {".py", ".md", ".toml", ".html", ".css", ".js", ".txt", ".svg"}

    offenders: list[Path] = []
    for path in root.rglob("*"):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path.is_file() and path.suffix in checked_suffixes:
            if private_name in path.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(path.relative_to(root))

    assert offenders == []


def test_architecture_doc_has_required_front_matter() -> None:
    text = Path("ARCHITECTURE.md").read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert "status: active" in text
    assert "date: 2026-05-08" in text
    assert "description:" in text
    assert "keywords:" in text


def test_third_party_notices_include_lobe_icons_attribution() -> None:
    text = Path("THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    assert "Lobe Icons" in text
    assert LOBE_ICONS_PACKAGE in text
    assert "MIT" in text
