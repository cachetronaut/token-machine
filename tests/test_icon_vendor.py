import io
import json
import tarfile
from pathlib import Path

from token_machine.dashboard.icon_vendor import refresh_icon_cache


def test_refresh_icon_cache_writes_expected_icons_and_manifest(tmp_path: Path) -> None:
    tarball = _icon_tarball(
        {
            "package/icons/codex-color.svg": "<svg><title>Codex</title></svg>",
            "package/icons/geminicli-color.svg": "<svg><title>Gemini CLI</title></svg>",
        }
    )
    package_meta = {
        "version": "1.0.0",
        "dist": {"tarball": "https://example.test/icons.tgz"},
    }

    def fake_download(url: str) -> bytes:
        if url.endswith("/latest"):
            return json.dumps(package_meta).encode()
        return tarball

    result = refresh_icon_cache(tmp_path, download_bytes=fake_download)

    assert result.version == "1.0.0"
    assert result.icon_count == 2
    assert (tmp_path / "cache" / "icons" / "codex.svg").read_text(
        encoding="utf-8"
    ) == "<svg><title>Codex</title></svg>"
    assert (tmp_path / "cache" / "icons" / "geminicli.svg").read_text(
        encoding="utf-8"
    ) == "<svg><title>Gemini CLI</title></svg>"

    manifest = json.loads(
        (tmp_path / "cache" / "icons.json").read_text(encoding="utf-8")
    )
    assert manifest["version"] == "1.0.0"
    assert manifest["icons"]["codex.svg"] == "codex-color.svg"
    assert manifest["icons"]["geminicli.svg"] == "geminicli-color.svg"


def _icon_tarball(files: dict[str, str]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return output.getvalue()
