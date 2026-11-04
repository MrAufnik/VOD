import argparse
from scripts.vodlib.core import read_stage, stage_path, write_json, generated_at
from scripts.vodlib.providers import find_seasons

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()
    source = read_stage(args.channel, "series")
    categories = []
    total = 0
    for category in source["categories"]:
        out_category = {k: v for k, v in category.items() if k != "series"}
        out_category["series"] = []
        for item in category.get("series", []):
            result = dict(item)
            try:
                result["seasons"] = find_seasons(args.channel, item)
            except Exception as exc:
                result["seasons"] = []
                result["seasons_error"] = str(exc)
            total += len(result["seasons"])
            out_category["series"].append(result)
        categories.append(out_category)
    write_json(stage_path(args.channel, "seasons"),
               {"channel_id": args.channel, "generated_at": generated_at(),
                "categories": categories, "season_count": total})
    print(f"Channel {args.channel}: {total} seasons discovered")

if __name__ == "__main__":
    main()
