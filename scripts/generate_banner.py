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
    # Embed the user-supplied artwork so the SVG remains a single reliable asset
    # when GitHub renders it through its image proxy.
    hero_data = "data:image/png;base64," + base64.b64encode(
        (ROOT / "assets" / "miles-hero.png").read_bytes()
    ).decode("ascii")

    bars = "".join(
        f'<rect x="{490 + i * 38}" y="{515 - height}" width="11" height="{height}" rx="5" class="bar"/>'
        for i, height in enumerate((20, 45, 28, 61, 37, 54, 24, 49, 32, 58, 23))
    )
    subtitle = "Now Playing"
    title_fill = "#f4ff00" if not is_playing else "#f8f8f8"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1983" height="793" viewBox="0 0 1983 793" role="img" aria-labelledby="title desc">
  <title id="title">What's Up Danger — {title}</title>
  <desc id="desc">Miles Morales profile banner. {mode}: {title} by {artist}.</desc>
  <defs>
    <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="20" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
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
  <rect x="122" y="215" width="328" height="328" rx="18" fill="#020306"/>
  <g filter="url(#glow)">
    <path d="M282 260 C208 284 193 389 218 480 C232 517 253 538 282 554 C311 538 332 517 346 480 C371 389 356 284 282 260Z" fill="#030304" stroke="#e60622" stroke-width="7"/>
    <path d="M250 324 C215 349 213 405 237 433 C262 421 274 382 270 340Z" fill="#d5eaff" stroke="#f5152c" stroke-width="9"/>
    <path d="M314 324 C349 349 351 405 327 433 C302 421 290 382 294 340Z" fill="#d5eaff" stroke="#f5152c" stroke-width="9"/>
  </g>
  <text x="490" y="304" class="label">{subtitle}</text>
  <text x="490" y="381" class="track">{title}</text>
  <text x="490" y="432" class="artist">by {artist}</text>
  {bars}
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
