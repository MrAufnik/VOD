from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "channels.json"
WORK_DIR = ROOT / "work"
DATA_DIR = ROOT / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}

def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

def channel_config(channel: str) -> dict[str, Any]:
    channels = load_config()["channels"]
    key = str(channel)
    if key not in channels:
        raise ValueError(f"Unsupported channel: {channel}")
    return channels[key]

_SESSION: requests.Session | None = None

def session() -> requests.Session:
    # Reuse TCP connections across the many pages in one catalog run.
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(HEADERS)
        _SESSION.headers.update({"Accept": "text/html,application/json,application/xhtml+xml,*/*"})
    return _SESSION

def get_text(url: str, *, referer: str | None = None, timeout: int = 35) -> str:
    headers = {"Referer": referer} if referer else None
    last_error = None
    for attempt in range(3):
        try:
            response = session().get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed: {url}: {last_error}") from last_error

def get_json(url: str, *, referer: str | None = None) -> Any:
    body = get_text(url, referer=referer)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        soup = BeautifulSoup(body, "html.parser")
        for node in soup.select('script[type="application/json"], script#__NEXT_DATA__'):
            raw = node.string or node.get_text()
            if raw.strip():
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"Response was not JSON: {url}")

def soup_for(url: str) -> BeautifulSoup:
    return BeautifulSoup(get_text(url), "html.parser")

def absolute(base: str, value: str | None) -> str:
    value = (value or "").strip()
    return urljoin(base, value) if value else ""

def clean_title(value: str | None) -> str:
    value = (value or "").replace("_", " ")
    removals = [
        "Poster 239 360", "Poster Image Small", "Poster image small",
        "Poster Image Big", "Poster image big", "239X360", "1200X1800",
        "1200 1800", "1800X1200", "1920X800", "1920X1080",
        " לוגו חדש", " לוגו", "פוסטר קטן",
    ]
    for number in range(2, 8):
        removals.extend([f"{number} Poster Image Small", f"{number} Poster image small",
                         f"{number} Poster Image Big", f"{number} Poster image big"])
    for marker in removals + ["(1)", "(2)", "(3)", "(4)", "(5)", "(6)", "(7)", "(14)"]:
        value = value.replace(marker, "")
    return re.sub(r"\s+", " ", value).strip()

def first_text(node: Any, selectors: list[str]) -> str:
    for selector in selectors:
        found = node.select_one(selector) if hasattr(node, "select_one") else None
        if found:
            text = found.get_text(" ", strip=True)
            if text:
                return text
    return ""

def image_from(node: Any, base: str) -> str:
    if node is None:
        return ""
    for attr in ("src", "data-src", "data-lazy-src", "srcset"):
        value = node.get(attr, "")
        if value:
            if attr == "srcset":
                value = value.split(",")[0].strip().split(" ")[0]
            return absolute(base, value.split("?")[0])
    return ""

def _decode_json_at(raw: str, start: int) -> tuple[Any, int] | None:
    """Decode one JSON value from JS without truncating nested objects by regex."""
    try:
        return json.JSONDecoder().raw_decode(raw, start)
    except json.JSONDecodeError:
        return None

def embedded_json(html: str) -> list[Any]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[Any] = []
    fingerprints: set[str] = set()
    for script in soup.find_all("script"):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        candidates: list[Any] = []
        script_type = (script.get("type") or "").lower()
        if "json" in script_type or script.get("id") == "__NEXT_DATA__":
            try:
                candidates.append(json.loads(raw))
            except json.JSONDecodeError:
                pass
        # Reshet 13 publishes window.data_query = { ... }; JSONDecoder correctly
        # handles nested braces, escaped strings and arrays.
        for match in re.finditer(r"(?:window\.)?data_query\s*=\s*", raw):
            pos = match.end()
            while pos < len(raw) and raw[pos].isspace():
                pos += 1
            if pos < len(raw) and raw[pos] in "{[":
                decoded = _decode_json_at(raw, pos)
                if decoded:
                    candidates.append(decoded[0])
        if not candidates and raw[:1] in "{[":
            try:
                candidates.append(json.loads(raw))
            except json.JSONDecodeError:
                pass
        for value in candidates:
            fingerprint = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            if fingerprint not in fingerprints:
                fingerprints.add(fingerprint)
                found.append(value)
    return found
def assignment_json(html: str, variable: str) -> list[Any]:
    """Extract JSON assigned to a JavaScript variable using a balanced JSON decoder."""
    values: list[Any] = []
    pattern = re.compile(r"(?:" + re.escape(variable) + r")\s*=\s*")
    for match in pattern.finditer(html):
        pos = match.end()
        while pos < len(html) and html[pos].isspace():
            pos += 1
        if pos >= len(html) or html[pos] not in "{[":
            continue
        decoded = _decode_json_at(html, pos)
        if decoded:
            values.append(decoded[0])
    return values

def walk_objects(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_objects(child)

def first_value(obj: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    return ""

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def stage_path(channel: str, stage: str) -> Path:
    return WORK_DIR / f"channel_{channel}" / f"{stage}.json"

def read_stage(channel: str, stage: str) -> Any:
    path = stage_path(channel, stage)
    if not path.exists():
        raise FileNotFoundError(f"Missing stage output: {path}. Run the previous stage first.")
    return json.loads(path.read_text(encoding="utf-8"))

def generated_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def page_url_without_query(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl()

def add_query(url: str, **params: str) -> str:
    from urllib.parse import urlencode, urlunparse
    parsed = urlparse(url)
    existing = parse_qs(parsed.query)
    for key, value in params.items():
        existing[key] = [value]
    query = urlencode(existing, doseq=True)
    return urlunparse(parsed._replace(query=query))
