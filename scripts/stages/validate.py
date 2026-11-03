import argparse
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from scripts.vodlib.core import DATA_DIR, read_stage, stage_path, write_json, generated_at


def walk_catalog(source):
    stats = Counter()
    errors = []
    invalid = []

    for category in source.get("categories", []):
        stats["categories"] += 1
        if category.get("error"):
            errors.append(f"category {category.get('id')}: {category['error']}")
        for series in category.get("series", []):
            stats["series"] += 1
            if not series.get("title") or not series.get("url"):
                invalid.append(f"series missing title/url in category {category.get('id')}")
            elif urlparse(series["url"]).scheme not in ("http", "https"):
                invalid.append(f"invalid series URL: {series['url']}")
            if series.get("seasons_error"):
                errors.append(f"seasons {series.get('title')}: {series['seasons_error']}")
            for season in series.get("seasons", []):
                stats["seasons"] += 1
                if season.get("episodes_error"):
                    errors.append(f"episodes {series.get('title')} / {season.get('title')}: {season['episodes_error']}")
                for episode in season.get("episodes", []):
                    stats["episodes"] += 1
                    if not episode.get("title") or not episode.get("url"):
                        invalid.append(f"episode missing title/url: {series.get('title')}")
                    elif urlparse(episode["url"]).scheme not in ("http", "https"):
                        invalid.append(f"invalid episode URL: {episode['url']}")

    return stats, errors, invalid


def main():
    parser = argparse.ArgumentParser(description="Validate extracted VOD catalog before publishing")
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()

    source = read_stage(args.channel, "episodes")
    stats, errors, invalid = walk_catalog(source)
    previous_path = DATA_DIR / f"channel_{args.channel}.json"
    previous = None
    if previous_path.exists():
        import json
        previous = json.loads(previous_path.read_text(encoding="utf-8")).get("statistics", {})

    failures = []
    if stats["series"] == 0:
        failures.append("No series were extracted; refusing to publish an empty catalog.")
    if stats["episodes"] == 0:
        failures.append("No episodes were extracted; refusing to publish an empty catalog.")
    if errors:
        failures.append(f"{len(errors)} request/parser errors were found.")
    if invalid:
        failures.append(f"{len(invalid)} records have invalid required fields.")

    # Protect a previously populated catalog from a silent partial scrape.
    # A real large catalog change should be reviewed before publishing.
    if previous:
        for key in ("series", "episodes"):
            old_count = int(previous.get(key, 0) or 0)
            new_count = int(stats[key])
            if old_count >= 10 and new_count < old_count * 0.35:
                failures.append(
                    f"{key} dropped from {old_count} to {new_count} "
                    "(below 35% of the previous successful run)."
                )

    report = {
        "channel_id": args.channel,
        "generated_at": generated_at(),
        "statistics": dict(stats),
        "errors": errors[:100],
        "invalid_records": invalid[:100],
        "failures": failures,
        "valid": not failures,
    }
    write_json(stage_path(args.channel, "validation"), report)
    print(report)
    if failures:
        raise SystemExit("Catalog validation failed; final JSON was not published.")


if __name__ == "__main__":
    main()
