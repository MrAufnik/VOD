import argparse
from urllib.parse import quote

from scripts.vodlib.core import channel_config, read_stage, stage_path, write_json, generated_at
from scripts.vodlib.providers import parse_series


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()
    source = read_stage(args.channel, "categories")
    categories = []
    total = 0
    provider = channel_config(args.channel)["provider"]

    for category in source["categories"]:
        try:
            items = parse_series(args.channel, category)
            if provider == "reshet13":
                # Reshet exposes genre/program sections on one VOD page. Split
                # those sections into real JSON categories instead of a flat list.
                grouped = {}
                for item in items:
                    title = (item.pop("category_title", "") or "כל התוכניות").strip()
                    grouped.setdefault(title, []).append(item)
                for title, series_items in grouped.items():
                    categories.append({
                        "id": "reshet-" + quote(title, safe=""),
                        "title": title,
                        "url": category["url"],
                        "series": series_items,
                    })
                    total += len(series_items)
                    print(f"[{args.channel}] {title}: {len(series_items)} series")
            else:
                result = dict(category)
                result["series"] = items
                total += len(items)
                categories.append(result)
                print(f"[{args.channel}] {category['title']}: {len(items)} series")
        except Exception as exc:
            result = dict(category)
            result["series"] = []
            result["error"] = str(exc)
            categories.append(result)
            print(f"[{args.channel}] ERROR {category['title']}: {exc}")

    write_json(stage_path(args.channel, "series"),
               {"channel_id": args.channel, "generated_at": generated_at(),
                "categories": categories, "series_count": total})
    print(f"Channel {args.channel}: {total} series saved across {len(categories)} categories")


if __name__ == "__main__":
    main()
