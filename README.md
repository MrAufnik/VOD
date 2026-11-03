# VOD catalog scraper

Python scraper for channels 11, 12, 13, 23 and 24, based on the existing MediaBox VOD parsers.

## Pipeline

1. `categories.py` — category list from `config/channels.json`
2. `series.py` — series/program cards: title, source URL, poster and description
3. `seasons.py` — discovers season pages for each series
4. `episodes.py` — episode title, URL, poster and description
5. `build_json.py` — writes `data/channel_<id>.json`

Shared HTTP/HTML/JSON helpers live in `scripts/vodlib/core.py`; provider-specific parsing lives in `scripts/vodlib/providers.py`.

## Local run

```bash
python -m pip install -r requirements.txt
python -m scripts.run_channel --channel 11
python -m scripts.run_channel --channel 12
python -m scripts.run_channel --channel 13
python -m scripts.run_channel --channel 23
python -m scripts.run_channel --channel 24
```

Intermediate files are written under `work/channel_<id>/`. Final output is `data/channel_<id>.json`.

## GitHub Actions

The Actions tab contains five independent workflows (one per channel), each with manual dispatch and a daily schedule. There is also a workflow to run all five channels in parallel. Each individual workflow commits only its own JSON file.

## JSON format

```json
{
  "schema_version": 1,
  "channel": {"id": "11", "name": "כאן 11", "provider": "kan"},
  "generated_at": "2026-11-03T00:00:00Z",
  "statistics": {"categories": 5, "series": 0, "seasons": 0, "episodes": 0},
  "categories": [{
    "id": "all",
    "title": "כל התוכניות",
    "url": "https://www.kan.org.il/lobby/kan11/",
    "series": [{
      "title": "שם הסדרה",
      "url": "https://example.invalid/program/",
      "image": "https://example.invalid/poster.jpg",
      "description": "",
      "seasons": [{
        "number": 1,
        "title": "עונה 1",
        "url": "https://example.invalid/program/s1/",
        "episodes": [{
          "number": 1,
          "title": "שם הפרק",
          "url": "https://example.invalid/episode/",
          "image": "https://example.invalid/episode.jpg",
          "description": ""
        }]
      }]
    }]
  }]
}
```

Playback URLs are not resolved by this catalog job. The Android app obtains those through provider-specific playback/ticket operations; such URLs can be temporary and should not be stored as stable catalog links.

Provider markup and APIs can change. Review the first Action run logs and resulting JSON before treating the generated catalog as complete. Intermediate outputs preserve per-category/per-series errors for diagnosis.
