import argparse
from scripts.vodlib.core import channel_config, stage_path, write_json, generated_at

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()
    config = channel_config(args.channel)
    payload = {"channel_id": args.channel, "channel_name": config["name"],
               "generated_at": generated_at(), "categories": config["categories"]}
    write_json(stage_path(args.channel, "categories"), payload)
    print(f"Channel {args.channel}: saved {len(payload['categories'])} categories")

if __name__ == "__main__":
    main()
