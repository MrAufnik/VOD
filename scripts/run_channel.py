import argparse
import subprocess
import sys

STAGES = ("categories", "series", "seasons", "episodes", "build_json")

def main():
    parser = argparse.ArgumentParser(description="Run all VOD extraction stages for one channel")
    parser.add_argument("--channel", required=True, choices=("11", "12", "13", "23", "24"))
    args = parser.parse_args()
    for stage in STAGES:
        print(f"\n=== {args.channel}: {stage} ===", flush=True)
        subprocess.run([sys.executable, "-m", f"scripts.stages.{stage}",
                        "--channel", args.channel], check=True)

if __name__ == "__main__":
    main()
