"""HLS relay: fetches googlevideo playlists/segments and rewrites URIs.

Livestreams are served over HLS. The master/media playlists reference other
playlists and segments by URL; if those point straight at googlevideo, the
browser fetches them directly and gets CORS-blocked (or IP/token-rejected).
This relay re-fetches every playlist server-side and rewrites each URI to
route back through this same endpoint, so every request (manifest, sub
manifest, segment) goes through our proxy chain.
"""

from __future__ import annotations

import re
import urllib.request
from urllib.parse import quote, urljoin

_TIMEOUT = 15
_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
_MANIFEST_TYPES = ("mpegurl", "vnd.apple.mpegurl")
_URI_ATTR_RE = re.compile(r'URI="([^"]+)"')


class RelayError(RuntimeError):
    """Raised when the upstream fetch fails."""


def _relay_url(relay_base: str, target: str) -> str:
    return f"{relay_base}?url={quote(target, safe='')}"


def _rewrite_manifest(text: str, base_url: str, relay_base: str) -> str:
    out_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        if stripped.startswith("#"):
            def _sub(match: re.Match[str]) -> str:
                target = urljoin(base_url, match.group(1))
                return f'URI="{_relay_url(relay_base, target)}"'

            out_lines.append(_URI_ATTR_RE.sub(_sub, line))
            continue
        # Plain URI line: a sub-playlist (master) or a segment (media playlist).
        target = urljoin(base_url, stripped)
        out_lines.append(_relay_url(relay_base, target))
    return "\n".join(out_lines) + "\n"


def fetch_and_rewrite(
    url: str, relay_base: str, range_header: str | None, method: str = "GET"
) -> tuple[int, str, bytes]:
    """Fetch ``url``, rewriting it if it's an HLS playlist.

    Returns ``(status_code, content_type, body)``. Runs blocking I/O — call
    via ``asyncio.to_thread``.
    """
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}, method=method)
    if range_header:
        req.add_header("Range", range_header)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            body = resp.read()
    except Exception as exc:  # noqa: BLE001 — surfaced as 502 by the caller
        raise RelayError(f"upstream fetch failed: {exc}") from exc

    is_manifest = url.endswith(".m3u8") or any(t in content_type.lower() for t in _MANIFEST_TYPES)
    if is_manifest:
        rewritten = _rewrite_manifest(body.decode("utf-8", errors="replace"), url, relay_base)
        return status, "application/vnd.apple.mpegurl", rewritten.encode()
    return status, content_type, body
