import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_banner.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_banner", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_banner_uses_the_track_cover_instead_of_the_generic_mask():
    module = load_module()
    track_cover = "data:image/jpeg;base64,dHJhY2stY292ZXI="

    svg = module.banner(
        {
            "title": "A Live Track",
            "artist": "An Artist",
            "mode": "NOW PLAYING · SPOTIFY",
            "cover": track_cover,
        }
    )

    assert track_cover in svg
    assert 'x="122" y="215" width="328" height="328"' in svg
    assert 'M282 260 C208 284' not in svg
    assert '<animate attributeName="height"' in svg
    assert 'repeatCount="indefinite"' in svg


def test_now_playing_returns_spotify_album_art_url(monkeypatch):
    module = load_module()
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "refresh")
    responses = iter(
        [
            (200, {"access_token": "access"}),
            (
                200,
                {
                    "is_playing": True,
                    "item": {
                        "name": "A Live Track",
                        "artists": [{"name": "An Artist"}],
                        "album": {"images": [{"url": "https://cover.example/live.jpg"}]},
                    },
                },
            ),
        ]
    )
    monkeypatch.setattr(module, "request_json", lambda *args, **kwargs: next(responses))

    assert module.now_playing()["cover_url"] == "https://cover.example/live.jpg"
