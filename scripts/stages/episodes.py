import argparse
from scripts.vodlib.core import read_stage, stage_path, write_json, generated_at
from scripts.vodlib.providers import parse_episodes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()
    source = read_stage(args.channel, "seasons")
    categories = []
    total = 0
    for category in source["categories"]:
        out_category = {k: v for k, v in category.items() if k != "series"}
        out_category["series"] = []
        for item in category.get("series", []):
            result = {k: v for k, v in item.items() if k != "seasons"}
            result["seasons"] = []
            for season in item.get("seasons", []):
                season_result = dict(season)
                try:
                    season_result["episodes"] = parse_episodes(args.channel, season, item)
                except Exception as exc:
                    season_result["episodes"] = []
                    season_result["episodes_error"] = str(exc)
                total += len(season_result["episodes"])
                result["seasons"].append(season_result)
            out_category["series"].append(result)
        categories.append(out_category)
    write_json(stage_path(args.channel, "episodes"),
               {"channel_id": args.channel, "generated_at": generated_at(),
                "categories": categories, "episode_count": total})
    print(f"Channel {args.channel}: {total} episodes extracted")

if __name__ == "__main__":
    main()
