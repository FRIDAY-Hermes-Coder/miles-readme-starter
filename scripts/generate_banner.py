#!/usr/bin/env python3
"""Generate the profile banner from Spotify playback, with a Sunflower fallback.

No third-party dependencies. When Spotify secrets are absent, it deterministically
writes the fallback banner so the repository always has a usable image.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "banner.svg"

FALLBACK = {
    "title": "Sunflower",
    "artist": "Post Malone & Swae Lee",
    "mode": "SUNFLOWER · FALLBACK",
    "lyrics": [
        "Then you're left in the dust",
        "Unless I stuck by ya",
        "You're the sunflower",
    ],
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
    if not title or not artists:
        return None
    return {"title": title, "artist": artists, "mode": "NOW PLAYING · SPOTIFY"}


def banner(data: dict) -> str:
    is_playing = data["mode"].startswith("NOW PLAYING")
    title = escape(data["title"])
    artist = escape(data["artist"])
    mode = escape(data["mode"])
    lyric_lines = data.get("lyrics", [])

    # The supplied image is deliberately positioned to leave the left side clear.
    lyric_svg = "".join(
        f'<text x="112" y="{492 + (i * 45)}" class="lyric">{escape(line)}</text>'
        for i, line in enumerate(lyric_lines)
    )
    bar_class = "bar active" if is_playing else "bar"
    bars = "".join(
        f'<rect x="{117 + i * 26}" y="{388 - height}" width="12" height="{height}" rx="6" class="{bar_class}"/>'
        for i, height in enumerate((24, 48, 34, 68, 42, 56, 27))
    )
    fallback_label = "FALLBACK LYRICS" if lyric_lines else "LIVE AUDIO SIGNAL"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1983" height="793" viewBox="0 0 1983 793" role="img" aria-labelledby="title desc">
  <title id="title">What's Up Danger — {title}</title>
  <desc id="desc">Miles Morales profile banner. {mode}: {title} by {artist}.</desc>
  <defs>
    <linearGradient id="shade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#030303" stop-opacity="0.98"/>
      <stop offset="0.49" stop-color="#090506" stop-opacity="0.90"/>
      <stop offset="0.74" stop-color="#090506" stop-opacity="0.18"/>
      <stop offset="1" stop-color="#090506" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="line" x1="0" x2="1"><stop stop-color="#f20a24"/><stop offset="1" stop-color="#ff5364"/></linearGradient>
    <style>
      .label {{ font: 600 22px Arial, sans-serif; letter-spacing: 5px; fill: #ff5364; }}
      .track {{ font: 700 48px Arial, sans-serif; fill: #f8f8f8; }}
      .artist {{ font: 400 26px Arial, sans-serif; fill: #afafb2; }}
      .hint {{ font: 600 16px Arial, sans-serif; letter-spacing: 3px; fill: #747478; }}
      .lyric {{ font: italic 700 31px Arial, sans-serif; fill: #ffffff; }}
      .bar {{ fill: #7e141f; }} .bar.active {{ fill: #ff2439; }}
    </style>
  </defs>
  <image href="miles-hero.png" x="0" y="0" width="1983" height="793" preserveAspectRatio="xMidYMid slice"/>
  <rect width="1983" height="793" fill="url(#shade)"/>
  <rect x="74" y="90" width="6" height="607" rx="3" fill="url(#line)"/>
  <text x="112" y="132" class="label">{mode}</text>
  <text x="112" y="215" class="track">{title}</text>
  <text x="112" y="258" class="artist">{artist}</text>
  <line x1="112" y1="300" x2="612" y2="300" stroke="#592128" stroke-width="2"/>
  <text x="112" y="338" class="hint">{fallback_label}</text>
  {bars}
  {lyric_svg}
  <text x="112" y="658" class="hint">WHAT'S UP DANGER</text>
</svg>\n'''


def main() -> None:
    try:
        data = now_playing() or FALLBACK
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"Spotify request failed; using fallback: {error}", file=sys.stderr)
        data = FALLBACK
    OUTPUT.write_text(banner(data), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} — {data['mode']}")


if __name__ == "__main__":
    main()
