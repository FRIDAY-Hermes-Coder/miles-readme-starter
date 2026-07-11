#!/usr/bin/env python3
"""Generate a profile banner from Spotify playback, with a Sunflower fallback.

The SVG is self-contained: both the banner art and the current album cover are
embedded so GitHub's image proxy can render the same image reliably.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "banner.svg"
FALLBACK_COVER = ROOT / "assets" / "sunflower-cover.jpg"

FALLBACK = {
    "title": "Sunflower",
    "artist": "Post Malone, Swae Lee",
    "mode": "SUNFLOWER · FALLBACK",
}


def request_json(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None):
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        if error.code in (204, 401, 403, 404):
            return error.code, None
        raise


def request_image_data_uri(url: str) -> str:
    """Fetch Spotify cover artwork and make it safe to embed in a single SVG."""
    with urllib.request.urlopen(url, timeout=30) as response:
        image = response.read()
        content_type = response.headers.get_content_type()
    if not content_type.startswith("image/") or not image:
        raise ValueError("Spotify returned an invalid album image")
    return f"data:{content_type};base64," + base64.b64encode(image).decode("ascii")


def local_image_data_uri(path: Path) -> str:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise ValueError(f"Unsupported cover type: {content_type}")
    return f"data:{content_type};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def cover_data_uri(data: dict) -> str:
    """Use live album art when available; otherwise use the original Sunflower cover."""
    cover_url = data.get("cover_url")
    if cover_url:
        try:
            return request_image_data_uri(cover_url)
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            print(f"Album cover fetch failed; using Sunflower cover: {error}", file=sys.stderr)
    return local_image_data_uri(FALLBACK_COVER)


def now_playing() -> dict | None:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")
    if not all((client_id, client_secret, refresh_token)):
        return None

    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    payload = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
    ).encode()
    status, auth = request_json(
        "https://accounts.spotify.com/api/token",
        data=payload,
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    if status != 200 or not auth or not auth.get("access_token"):
        return None

    status, playback = request_json(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    if status != 200 or not playback or not playback.get("is_playing"):
        return None

    item = playback.get("item") or {}
    title = item.get("name")
    artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
    images = ((item.get("album") or {}).get("images") or [])
    cover_url = images[0].get("url") if images else None
    if not title or not artists:
        return None
    return {
        "title": title,
        "artist": artists,
        "mode": "NOW PLAYING · SPOTIFY",
        "cover_url": cover_url,
    }


def banner(data: dict) -> str:
    is_playing = data["mode"].startswith("NOW PLAYING")
    title = escape(data["title"])
    artist = escape(data["artist"])
    mode = escape(data["mode"])
    cover = escape(data["cover"])
    hero_data = "data:image/png;base64," + base64.b64encode(
        (ROOT / "assets" / "miles-hero.png").read_bytes()
    ).decode("ascii")

    bars = "".join(
        f'<rect x="{490 + i * 38}" y="{515 - height}" width="11" height="{height}" rx="5" class="bar"/>'
        for i, height in enumerate((20, 45, 28, 61, 37, 54, 24, 49, 32, 58, 23))
    )
    title_fill = "#f4ff00" if not is_playing else "#f8f8f8"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1983" height="793" viewBox="0 0 1983 793" role="img" aria-labelledby="title desc">
  <title id="title">What's Up Danger — {title}</title>
  <desc id="desc">Miles Morales profile banner. {mode}: {title} by {artist}.</desc>
  <defs>
    <clipPath id="coverClip"><rect x="122" y="215" width="328" height="328" rx="18"/></clipPath>
    <linearGradient id="card" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#070b10" stop-opacity="0.97"/>
      <stop offset="1" stop-color="#0c1114" stop-opacity="0.93"/>
    </linearGradient>
    <style>
      .label {{ font: 500 28px Arial, sans-serif; fill: #727277; }}
      .track {{ font: 700 61px Arial, sans-serif; fill: {title_fill}; }}
      .artist {{ font: 400 34px Arial, sans-serif; fill: #c9f6f6; }}
      .bar {{ fill: #971018; }}
    </style>
  </defs>
  <image href="{hero_data}" x="0" y="0" width="1983" height="793" preserveAspectRatio="xMidYMid slice"/>
  <rect x="64" y="164" width="1410" height="465" rx="35" fill="url(#card)" stroke="#202b34" stroke-width="2"/>
  <image href="{cover}" x="122" y="215" width="328" height="328" preserveAspectRatio="xMidYMid slice" clip-path="url(#coverClip)"/>
  <text x="490" y="304" class="label">Now Playing</text>
  <text x="490" y="381" class="track">{title}</text>
  <text x="490" y="432" class="artist">by {artist}</text>
  {bars}
</svg>\n'''


def main() -> None:
    try:
        data = now_playing() or FALLBACK.copy()
        data["cover"] = cover_data_uri(data)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"Spotify request failed; using fallback: {error}", file=sys.stderr)
        data = FALLBACK.copy()
        data["cover"] = local_image_data_uri(FALLBACK_COVER)
    OUTPUT.write_text(banner(data), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} — {data['mode']}")


if __name__ == "__main__":
    main()
