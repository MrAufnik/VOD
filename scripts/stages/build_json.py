import argparse
from scripts.vodlib.core import read_stage, DATA_DIR, write_json, generated_at

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()
    source = read_stage(args.channel, "episodes")
    config = __import__("scripts.vodlib.core", fromlist=["channel_config"]).channel_config(args.channel)
    series_count = episode_count = season_count = 0
    for category in source["categories"]:
        for series in category.get("series", []):
            series_count += 1
            for season in series.get("seasons", []):
                season_count += 1
                episode_count += len(season.get("episodes", []))
    payload = {
        "schema_version": 1,
        "channel": {"id": args.channel, "name": config["name"], "provider": config["provider"]},
        "generated_at": generated_at(),
        "statistics": {"categories": len(source["categories"]), "series": series_count,
                       "seasons": season_count, "episodes": episode_count},
        "categories": source["categories"]
    }
    target = DATA_DIR / f"channel_{args.channel}.json"
    write_json(target, payload)
    print(f"Wrote {target.relative_to(DATA_DIR.parent)}: {series_count} series, "
          f"{season_count} seasons, {episode_count} episodes")

if __name__ == "__main__":
    main()
