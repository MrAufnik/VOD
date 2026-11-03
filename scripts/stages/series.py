import argparse
from scripts.vodlib.core import read_stage, stage_path, write_json, generated_at
from scripts.vodlib.providers import parse_series

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()
    source = read_stage(args.channel, "categories")
    categories = []
    total = 0
    for category in source["categories"]:
        result = dict(category)
        try:
            result["series"] = parse_series(args.channel, category)
        except Exception as exc:
            result["series"] = []
            result["error"] = str(exc)
        total += len(result["series"])
        categories.append(result)
        print(f"[{args.channel}] {category['title']}: {len(result['series'])} series")
    write_json(stage_path(args.channel, "series"),
               {"channel_id": args.channel, "generated_at": generated_at(),
                "categories": categories, "series_count": total})
    print(f"Channel {args.channel}: {total} series saved")

if __name__ == "__main__":
    main()
