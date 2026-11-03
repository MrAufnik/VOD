from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .core import (
    absolute, add_query, clean_title, embedded_json, first_text, first_value,
    get_json, get_text, page_url_without_query, soup_for, walk_objects,
)

def parse_kan_series(category: dict[str, Any]) -> list[dict[str, Any]]:
    html = get_text(category["url"])
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Same card selector used by Channel11VodAsyncTask.
    for card in soup.select("card vods-by-category"):
        link = card.select_one(".card-link.d-inline-block[href]")
        image = card.select_one(".block-img .img-full")
        if not link:
            continue
        url = absolute(category["url"], link.get("href"))
        if not url or url in seen:
            continue
        seen.add(url)
        title = clean_title((image.get("title") or image.get("alt") or "") if image else "")
        if not title:
            title = first_text(card, [".card-title", ".title", "h2", "h3"])
        description = first_text(card, [".card-body .mb-3", ".details", ".card-text"])
        image_url = absolute(category["url"], image.get("src", "")) if image else ""
        if image_url:
            image_url = image_url.split("?")[0]
        results.append({"title": title, "url": url, "image": image_url, "description": description})
    # Current KAN lobby pages may use cr-item cards rather than the legacy custom element.
    if not results:
        for link in soup.select("a.cr-item[href]"):
            url = absolute(category["url"], link.get("href"))
            if not url or url in seen:
                continue
            seen.add(url)
            img = link.select_one("img")
            results.append({
                "title": clean_title(first_text(link, [".cr-title"]) or (img.get("alt", "") if img else "")),
                "url": url,
                "image": absolute(category["url"], (img.get("src") or img.get("data-src") or "")) if img else "",
                "description": first_text(link, [".cr-subtitle", ".cr-text p"]),
            })
    return [item for item in results if item["url"]]

def parse_kan_kids_series(category: dict[str, Any]) -> list[dict[str, Any]]:
    html = get_text(category["url"])
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Channel23VodAsyncTask reads digitalSeries from page scripts.
    for script in soup.select("script"):
        raw = script.string or script.get_text()
        match = re.search(r"digitalSeries\s*:\s*(\[.*?\])\s*[,;]", raw, re.S)
        if not match:
            match = re.search(r"digitalSeries\s*:\s*(\[.*?\])\s*\}", raw, re.S)
        if match:
            try:
                items = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            for item in items if isinstance(items, list) else []:
                url = absolute(category["url"], first_value(item, "Url", "url", "pageUrl"))
                if not url or url in seen:
                    continue
                seen.add(url)
                results.append({
                    "title": clean_title(first_value(item, "ImageAlt", "Title", "title", "Name")),
                    "url": url,
                    "image": absolute(category["url"], first_value(item, "Image", "image", "pic")),
                    "description": first_value(item, "Description", "description", "altText"),
                })
    # Fallback to cards for KAN Kids redesigns.
    if not results:
        for link in soup.select("a.cr-item[href], a.card-link[href]"):
            url = absolute(category["url"], link.get("href"))
            if not url or url in seen:
                continue
            seen.add(url)
            img = link.select_one("img")
            results.append({
                "title": clean_title(first_text(link, [".cr-title", ".card-title"]) or (img.get("alt", "") if img else "")),
                "url": url,
                "image": absolute(category["url"], (img.get("src") or img.get("data-src") or "")) if img else "",
                "description": first_text(link, [".cr-subtitle", ".card-text"]),
            })
    return results

def _mako_items(payload: Any) -> list[dict[str, Any]]:
    results = []
    # Channel12VodJsonAsyncTask reads root.items[] with title/pic/pageUrl/altText.
    for obj in walk_objects(payload):
        items = obj.get("items")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = first_value(item, "title", "name")
                url = first_value(item, "pageUrl", "url", "link")
                image = first_value(item, "pic", "image", "imageUrl", "poster")
                desc = first_value(item, "altText", "description", "brief", "subtitle")
                if title and url:
                    results.append({"title": title, "url": url, "image": image, "description": desc})
    # Mako page may wrap JSON in a script.
    return results

def parse_mako_series(category: dict[str, Any], *, channel24: bool = False) -> list[dict[str, Any]]:
    url = category["url"]
    try:
        payload = get_json(url, referer="https://www.mako.co.il/")
    except Exception:
        html = get_text(url, referer="https://www.mako.co.il/")
        payloads = embedded_json(html)
        payload = payloads[0] if payloads else {}
    results = _mako_items(payload)
    if channel24:
        # Java Channel24VodAsyncTask reads root.specialArea.items and filters live
        # channel entries; accept the same fields but traverse the full response.
        for obj in walk_objects(payload):
            items = obj.get("specialArea")
            if isinstance(items, dict):
                items = items.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = first_value(item, "title", "name", "programTitle")
                link = first_value(item, "url", "link", "pageUrl", "programLink")
                image = first_value(item, "pic", "image", "imageUrl", "poster")
                desc = first_value(item, "brief", "plot", "description", "subtitle")
                if title and link and title.lower() != "ערוץ 24 live":
                    results.append({"title": title, "url": link, "image": image, "description": desc})
    deduped, seen = [], set()
    for item in results:
        item["url"] = absolute(url, item["url"])
        item["image"] = absolute(url, item.get("image", ""))
        key = item["url"]
        if key and key not in seen:
            seen.add(key)
            item["title"] = clean_title(item["title"])
            deduped.append(item)
    return deduped

def _reshet_payloads(url: str) -> list[Any]:
    html = get_text(url, referer="https://13tv.co.il/")
    return embedded_json(html)

def parse_reshet_series(category: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Current Reshet VOD pages expose visible program cards in the HTML.
    # Read these first; retain the legacy embedded posts parser below as fallback.
    html = get_text(category["url"], referer="https://13tv.co.il/")
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.select("a[href]"):
        href = absolute(category["url"], anchor.get("href"))
        if not href or href in seen:
            continue
        image_node = anchor.select_one("img")
        title = first_text(anchor, ["h2", "h3", ".title", ".card-title"])
        if not title and image_node is not None:
            title = image_node.get("alt", "").strip()
        if not title:
            title = anchor.get_text(" ", strip=True)
        path = urlparse(href).path.lower()
        if not title or len(title) > 120:
            continue
        if any(token in path for token in ("/article/", "/news/", "/video/")):
            continue
        if image_node is None and not any(token in path for token in ("/shows/", "/programs/")):
            continue
        if re.search(r"(פרק\s*\d+|episode\s*\d+)", title, re.I):
            continue
        image = ""
        if image_node is not None:
            image = image_node.get("src") or image_node.get("data-src") or image_node.get("data-lazy-src") or ""
        seen.add(href)
        results.append({
            "title": clean_title(title), "url": href,
            "image": absolute(category["url"], image),
            "description": first_text(anchor, [".description", ".subtitle", "p"])
        })
    for payload in _reshet_payloads(category["url"]):
        for obj in walk_objects(payload):
            posts = obj.get("posts")
            if not isinstance(posts, list):
                continue
            for post in posts:
                if not isinstance(post, dict):
                    continue
                title = first_value(post, "title", "name", "post_title")
                url = first_value(post, "url", "link", "permalink", "pageUrl", "slug")
                image = first_value(post, "image", "image_url", "thumbnail", "poster", "featured_image")
                desc = first_value(post, "description", "excerpt", "subtitle", "summary")
                if isinstance(post.get("title"), dict):
                    title = first_value(post["title"], "text", "rendered")
                if isinstance(post.get("image"), dict):
                    image = first_value(post["image"], "url", "src", "srcset")
                if title and url:
                    full = absolute(category["url"], url)
                    if full not in seen:
                        seen.add(full)
                        results.append({"title": clean_title(title), "url": full,
                                        "image": absolute(category["url"], image), "description": desc})
    # The app's Next.js data can be nested under props.pageProps.page.Content.PageGrid.
    return results

def parse_series(channel: str, category: dict[str, Any]) -> list[dict[str, Any]]:
    provider = str(channel_config(channel)["provider"])
    if provider == "kan":
        return parse_kan_series(category)
    if provider == "kan_kids":
        return parse_kan_kids_series(category)
    if provider == "mako":
        return parse_mako_series(category)
    if provider == "mako24":
        return parse_mako_series(category, channel24=True)
    if provider == "reshet13":
        return parse_reshet_series(category)
    raise ValueError(f"No series parser for provider: {provider}")

def channel_config(channel: str) -> dict[str, Any]:
    from .core import channel_config as _channel_config
    return _channel_config(channel)

def find_seasons(channel: str, series: dict[str, Any]) -> list[dict[str, Any]]:
    provider = channel_config(channel)["provider"]
    url = series["url"]
    seasons: list[dict[str, Any]] = []
    seen: set[str] = set()
    if provider in ("kan", "kan_kids"):
        # Match the Android KAN Kids parser: request the full episode/season list.
        page_url = add_query(url, itemsToShow="9999") if provider == "kan_kids" else url
        html = get_text(page_url)
        soup = BeautifulSoup(html, "html.parser")
        selectors = ["a.program-season-tab[href]"] if provider == "kan" else ["a[href]"]
        for link in soup.select(",".join(selectors)):
            href = absolute(url, link.get("href"))
            match = re.search(r"/(?:s|עונה-)(\d+)/?$", href.rstrip("/") + "/")
            if not match:
                match = re.search(r"/s(\d+)/?$", href)
            if match and href not in seen:
                seen.add(href)
                number = int(match.group(1))
                seasons.append({"number": number, "title": f"עונה {number}", "url": href})
        if not seasons:
            seasons.append({"number": 1, "title": "פרקים", "url": url})
        return sorted(seasons, key=lambda x: x["number"], reverse=(provider == "kan_kids"))
    if provider in ("mako", "mako24"):
        page = add_query(url, platform="responsive")
        try:
            payload = get_json(page, referer="https://www.mako.co.il/")
        except Exception:
            payloads = embedded_json(get_text(page, referer="https://www.mako.co.il/"))
            payload = payloads[0] if payloads else {}
        for obj in walk_objects(payload):
            entries = obj.get("seasons")
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    season_url = first_value(entry, "pageUrl", "url", "link")
                    title = first_value(entry, "seasonTitle", "title", "name")
                    if season_url:
                        full = absolute(url, season_url)
                        if full not in seen:
                            seen.add(full)
                            number_match = re.search(r"(\d+)", title or full)
                            number = int(number_match.group(1)) if number_match else len(seasons) + 1
                            seasons.append({"number": number, "title": title or f"עונה {number}", "url": full})
        return seasons or [{"number": 1, "title": "פרקים", "url": page}]
    if provider == "reshet13":
        html = get_text(url, referer="https://13tv.co.il/")
        candidates: set[str] = set()
        # Season URLs may be present in embedded data or ordinary anchors.
        for match in re.finditer(r"""(?:https?:)?//[^"']+|/[^"']*season-\d+/episodes/""", html):
            candidate = match.group(0).replace("\\/", "/")
            if re.search(r"/season-(\d+)/episodes/", candidate):
                candidates.add(absolute(url, candidate))
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.select("a[href]"):
            href = absolute(url, anchor.get("href"))
            if re.search(r"/season-(\d+)/episodes/?$", href):
                candidates.add(href)
        for season_url in sorted(candidates):
            match = re.search(r"/season-(\d+)/episodes/", season_url)
            if not match:
                continue
            number = int(match.group(1))
            if season_url not in seen:
                seen.add(season_url)
                seasons.append({"number": number, "title": f"עונה {number}", "url": season_url})
        return sorted(seasons, key=lambda x: x["number"]) or [{"number": 1, "title": "פרקים", "url": url}]
    raise ValueError(f"No season parser for provider: {provider}")

def parse_kan_episodes(season: dict[str, Any], series: dict[str, Any], channel: str) -> list[dict[str, Any]]:
    page_url = add_query(season["url"], itemsToShow="9999") if channel == "23" else season["url"]
    html = get_text(page_url)
    soup = BeautifulSoup(html, "html.parser")
    episodes = []
    seen = set()
    if channel == "11":
        nodes = soup.select("a.cr-item[href]")
        for node in nodes:
            url = absolute(season["url"], node.get("href"))
            if not url or url in seen:
                continue
            seen.add(url)
            img = node.select_one(".cr-card img")
            title = first_text(node, [".cr-title"]) or (img.get("alt", "") if img else "")
            episodes.append({
                "title": clean_title(title) or f"פרק {len(episodes)+1}",
                "url": url,
                "image": absolute(season["url"], (img.get("src") or img.get("data-src") or "") if img else ""),
                "description": first_text(node, [".cr-subtitle", ".cr-text p", ".cr-text"]),
                "number": len(episodes) + 1,
            })
    else:
        # Channel23VodEpisodesAsyncTask uses .seasons-item.kids and card-row card-overlay.
        for section in soup.select(".seasons-item.kids"):
            season_title = first_text(section, [".h2"]) or season["title"]
            for card in section.select(".card.card-row.card-row-md.card-overlay"):
                link = card.select_one(".card-link[href]")
                if not link:
                    continue
                url = absolute(season["url"], link.get("href"))
                if not url or url in seen:
                    continue
                seen.add(url)
                img = card.select_one(".img-full")
                episodes.append({
                    "title": clean_title(first_text(card, [".card-title"])),
                    "url": url,
                    "image": absolute(season["url"], (img.get("src") or img.get("data-src") or "") if img else ""),
                    "description": first_text(card, [".card-text"]),
                    "season_title": season_title,
                    "number": len(episodes) + 1,
                })
    return episodes

def parse_mako_episodes(season: dict[str, Any], series: dict[str, Any]) -> list[dict[str, Any]]:
    url = add_query(season["url"], platform="responsive")
    try:
        payload = get_json(url, referer="https://www.mako.co.il/")
    except Exception:
        payloads = embedded_json(get_text(url, referer="https://www.mako.co.il/"))
        payload = payloads[0] if payloads else {}
    episodes = []
    seen = set()
    # Channel12VodEpisodesJsonAsyncTask reads each season's menu and its allEpisodes item.
    for obj in walk_objects(payload):
        menu = obj.get("menu")
        if not isinstance(menu, list):
            continue
        for menu_item in menu:
            if not isinstance(menu_item, dict):
                continue
            if str(menu_item.get("id", "")).lower() not in ("allepisodes", "all_episodes", "all episodes"):
                continue
            for child in walk_objects(menu_item):
                title = first_value(child, "title", "episodeTitle", "name")
                link = first_value(child, "pageUrl", "url", "link", "videoUrl")
                image = first_value(child, "pic", "image", "imageUrl", "poster")
                desc = first_value(child, "altText", "description", "subtitle", "brief")
                if title and link:
                    full = absolute(url, link)
                    if full not in seen:
                        seen.add(full)
                        episodes.append({"title": clean_title(title), "url": full,
                                         "image": absolute(url, image), "description": desc,
                                         "number": len(episodes) + 1})
    # Fallback for API revisions: pick structured episode-like objects.
    if not episodes:
        for obj in walk_objects(payload):
            title = first_value(obj, "episodeTitle", "title", "name")
            link = first_value(obj, "pageUrl", "url", "link")
            if title and link and any(k in obj for k in ("episodeNumber", "episode", "videoId", "video_id")):
                full = absolute(url, link)
                if full not in seen:
                    seen.add(full)
                    episodes.append({"title": clean_title(title), "url": full,
                                     "image": absolute(url, first_value(obj, "pic", "image", "poster")),
                                     "description": first_value(obj, "description", "subtitle", "altText"),
                                     "number": len(episodes) + 1})
    return episodes

def parse_reshet_episodes(season: dict[str, Any], series: dict[str, Any]) -> list[dict[str, Any]]:
    html = get_text(season["url"], referer="https://13tv.co.il/")
    episodes = []
    seen = set()
    # The Android implementation reads the embedded data_query and scans season episode
    # objects for title, image, video id and episode links. Walk nested JSON rather than
    # binding to unstable obfuscated property names.
    for payload in embedded_json(html):
        for obj in walk_objects(payload):
            title = first_value(obj, "title", "name", "episodeTitle", "subtitle")
            link = first_value(obj, "url", "link", "pageUrl", "permalink")
            image = first_value(obj, "image", "thumbnail", "poster", "imageUrl")
            video_id = first_value(obj, "videoId", "video_id", "id")
            if title and (link or video_id) and any(k in obj for k in ("video", "videoId", "video_id", "episode", "post_type")):
                full = absolute(season["url"], link) if link else ""
                key = full or video_id
                if key and key not in seen:
                    seen.add(key)
                    episodes.append({"title": clean_title(title), "url": full,
                                     "video_id": video_id, "image": absolute(season["url"], image),
                                     "description": first_value(obj, "description", "excerpt", "summary"),
                                     "number": len(episodes) + 1})
    # Also inspect anchors for episode pages.
    if not episodes:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = absolute(season["url"], link.get("href"))
            text = link.get_text(" ", strip=True)
            if href and text and re.search(r"(פרק|episode)", text, re.I) and href not in seen:
                seen.add(href)
                img = link.select_one("img")
                episodes.append({"title": clean_title(text), "url": href,
                                 "image": absolute(season["url"], (img.get("src") or "") if img else ""),
                                 "description": "", "number": len(episodes) + 1})
    return episodes

def parse_episodes(channel: str, season: dict[str, Any], series: dict[str, Any]) -> list[dict[str, Any]]:
    provider = channel_config(channel)["provider"]
    if provider in ("kan", "kan_kids"):
        return parse_kan_episodes(season, series, channel)
    if provider in ("mako", "mako24"):
        return parse_mako_episodes(season, series)
    if provider == "reshet13":
        return parse_reshet_episodes(season, series)
    return []
