# Java integration and MediaBox VOD improvements

This note maps the generated channel catalog to the existing Android Java VOD UI and lists the highest-impact fixes found while reviewing the current implementation in MediaBoxIL.

## 1. Recommended integration

Keep the existing Leanback/RecyclerView presentation initially. Replace only the provider-specific catalog scraping in the Android app with a repository that reads:

- `data/channel_11.json`
- `data/channel_12.json`
- `data/channel_13.json`
- `data/channel_23.json`
- `data/channel_24.json`

The JSON contains stable catalog metadata (category, series, season, episode, page URL, image and description). Do not store short-lived stream/ticket URLs in this catalog. Resolve playback URLs through the existing provider-specific playback service when the user selects an episode.

Suggested Java layers:

1. `VodCatalogApi` — fetches one channel JSON document using Retrofit/OkHttp.
2. `VodCatalogRepository` — cache-first read, refresh, schema validation and mapping.
3. `VodCatalogDto` — Gson DTOs matching the JSON schema.
4. `VodGridItemMapper` — maps category/series/episode DTOs into the existing UI model.
5. Existing `Channel12Service`, `Channel13Service`, `ChannelKanService` (or dedicated playback resolvers) — used only to resolve actual playback.

The first migration can preserve `VodGridItem`, `ListRow`, `VodCardPresenter` and the watch database. That keeps the UI change small.

## 2. Critical Java issues found

### P0 — Remove global certificate-validation bypass

`WebapiSingleton.disableCertificateValidation()` installs a trust-all X509TrustManager and a HostnameVerifier that accepts every host. Calls to it appear in the KAN VOD tasks. This disables HTTPS server identity verification globally and exposes every HTTPS request in the process to man-in-the-middle attacks.

Remove these calls. Fix the specific certificate/chain issue or use Android's normal trust store. Never use a trust-all manager in production.

### P0 — Stop mutating shared global HTTP state per service

`GeneralService` and `Channel12Service` call global methods such as `initCookieJarEmpty()`, `clearHeaders()`, `clearBasicToken()`, and `setHeaders()`. A request for one provider can overwrite headers/cookies while another provider is running.

Use one immutable OkHttpClient/Retrofit instance per provider configuration (KAN, Mako, Reshet), or create explicit clients for requests that need different cookies. Keep headers and cookie jars scoped to that client, not global mutable static fields.

### P1 — Fix identity in VodGridItem

The current `VodGridItem.equals()` compares only `id`. In the VOD tasks, `id` is the channel ID (11, 12, 13, 23 or 24), so every item in the same channel compares equal. If adapters, sets, maps or diffing code rely on equality, different series/episodes can collide.

Add an immutable `contentId` and implement `equals/hashCode` using that stable content identity. Do not use the channel ID as the identity of a series or episode.

Recommended identity:
- Series: `channelId + seriesUrl` (or a provider ID when available)
- Episode: `channelId + episodeUrl` (or a provider episode ID)
- Watch progress: `channelId + seriesId + seasonNumber + episodeId`

### P1 — Separate catalog page URL from playback URL

The existing `videoUrl` field is used for program pages and episode links, while playback resolution is handled elsewhere. Make this explicit in the model:

- `pageUrl`: stable provider page used for metadata/navigation
- `playbackUrl`: temporary URL, resolved at playback time only
- `providerContentId`: provider-native identifier when available

This prevents a future catalog refresh from overwriting a ticketed/temporary playback URL.

### P1 — Validate every Retrofit response

Before reading `response.body()`, check `response.isSuccessful()` and that the body is non-null. Avoid direct `getAsString()` on possibly absent/null JSON fields. In particular, the Mako code reads `programLink` without a null guard and constructs URLs by concatenating strings.

Use:
- `TextUtils.isEmpty(value)` instead of `value == ""`
- `Uri.resolve` or `HttpUrl.resolve` instead of `baseUrl + path`
- Gson `has()`, `isJsonNull()` and safe helper methods before reading a field.

### P1 — Replace AsyncTask-based loading

`AsyncTask` is deprecated and the tasks retain Fragment/Activity references. Use a Java `ExecutorService` for one-shot catalog reads, with lifecycle-aware delivery through a ViewModel/LiveData (or a small callback guarded by the Fragment lifecycle). Use WorkManager only for scheduled/background refresh, not for an immediate screen load.

Support cancellation and don't update a detached Fragment.

### P1 — Load watch state once

Several channel tasks open/query `WatchDBHelper` repeatedly inside the per-series loop. Read the channel's watch rows once, build a Map keyed by stable content identity, and map the state onto each DTO. This reduces SQLite calls and fixes fragile title-based matching.

Avoid using a series title as `TMDB_ID`; titles can change and are not unique.

## 3. Provider-specific findings

- **KAN 11:** use the season number from the season URL (for example `/s2/`), not the visible tab order. The newer Java episode task already does this correctly. Keep the newer `.cr-item` episode-card selector and check image/title nodes for null.
- **KAN Kids 23:** the current Java parser requests `itemsToShow=9999`; the Python scraper now mirrors that for the series/episode listing. Keep numeric season sorting and test all seasons rather than trusting page display order.
- **Mako 12 / Channel 24:** use the JSON API shape already present in the Java code (`items`, `root.specialArea.items`, `seasons`, `menu`, `allEpisodes`). Treat missing keys and HTTP errors as failures, not empty lists. Keep Channel 24's filtering separate from Channel 12's general catalogue.
- **Reshet 13:** the older Java code extracts `window.data_query` with a greedy regular expression and assumes internal page-grid keys. This is brittle. Use a JSON-aware extraction step and inspect the current page payload. The public VOD page currently exposes program groupings and a latest-episodes section; the old `/general/programs/` and `/news/13-programs/` category assumptions should not be treated as the complete current catalogue.

## 4. DTO shape

Use typed DTOs rather than building the UI directly from raw Gson objects:

```java
class VodCatalogDto {
    int schema_version;
    ChannelDto channel;
    StatisticsDto statistics;
    List<CategoryDto> categories;
}

class CategoryDto {
    String id;
    String title;
    String url;
    List<SeriesDto> series;
}

class SeriesDto {
    String title;
    String url;
    String image;
    String description;
    List<SeasonDto> seasons;
}

class SeasonDto {
    int number;
    String title;
    String url;
    List<EpisodeDto> episodes;
}

class EpisodeDto {
    int number;
    String title;
    String url;
    String image;
    String description;
}
```

The actual DTOs should also include optional fields such as provider IDs, year, duration and publish date when the source exposes them. Keep them nullable; don't invent values.

## 5. Cache and refresh policy

- Store the last successful channel JSON locally (Room or app-private file).
- Show cached data immediately, then refresh asynchronously.
- Use ETag/Last-Modified when the hosting endpoint supports it.
- If a refresh fails validation, keep the previous successful catalog.
- Keep watch progress in the existing watch database, separate from the remote catalogue.
- Log provider, channel, stage and URL; redact cookies, tokens and signed playback URLs.

## 6. Migration order

1. Add `contentId` and fix `equals/hashCode` in `VodGridItem`.
2. Remove trust-all TLS and isolate provider HTTP clients.
3. Add DTOs + Gson parsing for one channel (start with KAN 11).
4. Map the DTOs to existing `ListRow` / `VodGridItem` and preserve watch state.
5. Verify playback still calls the existing provider resolver.
6. Repeat for Mako 12, Reshet 13, KAN Kids 23 and Channel 24.
7. Remove the old catalog scraping AsyncTasks only after all five channels pass regression tests.

This is a review/integration plan; it does not modify the MediaBoxIL Java application.
