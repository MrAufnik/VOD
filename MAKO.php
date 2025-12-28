<?php
/**
 * MAKO.php
 *
 * Redirects directly to the MASTER index.m3u8
 * with hdntl token as QUERY PARAMETER
 *
 * Usage:
 *   MAKO.php?channel=24
 */

header("Access-Control-Allow-Origin: *");

/* =========================
 * 1. CHANNEL
 * ========================= */
$channel = strtolower(trim($_GET['channel'] ?? ''));
if ($channel === '') {
    http_response_code(400);
    exit("Missing channel");
}

/* =========================
 * 2. CHANNEL MAP
 * ========================= */
$channels = [
    "12"     => "https://mako-streaming.akamaized.net/n12/hls/live/2103938/k12/index.m3u8",
    "24"     => "https://mako-streaming.akamaized.net/direct/hls/live/2035340/ch24live/index.m3u8",
    "erets"  => "https://mako-streaming.akamaized.net/free/hls/live/2111419/erets/index.m3u8",
    "savri"  => "https://mako-streaming.akamaized.net/free/hls/live/2111419/savri/index.m3u8",
    "hatuna" => "https://mako-streaming.akamaized.net/free/hls/live/2111419/hatuna/index.m3u8",
    "ninja"  => "https://mako-streaming.akamaized.net/free/hls/live/2111419/ninja/index.m3u8",
    "kohav"  => "https://mako-streaming.akamaized.net/free/hls/live/2111419/kohav/index.m3u8",
];

if (!isset($channels[$channel])) {
    http_response_code(404);
    exit("Unknown channel");
}

/* =========================
 * 3. FETCH TOKEN (hdntl)
 * ========================= */
$tokenUrl = "https://mass.mako.co.il/ClicksStatistics/entitlementsServicesV2.jsp?et=gt&lp=&rv=AKAMAI";

$opts = [
    "http" => [
        "method" => "GET",
        "header" =>
            "User-Agent: Mozilla/5.0\r\n" .
            "Referer: https://www.mako.co.il/\r\n"
    ]
];

$context = stream_context_create($opts);
$response = file_get_contents($tokenUrl, false, $context);

if ($response === false ||
    !preg_match('/"ticket"\s*:\s*"([^"]+)"/', $response, $m)) {
    http_response_code(500);
    exit("Failed to fetch token");
}

$hdntl = $m[1]; // already "hdntl=exp=..."

/* =========================
 * 4. BUILD FINAL URL
 * ========================= */
$finalUrl = $channels[$channel];
$finalUrl .= (str_contains($finalUrl, '?') ? '&' : '?') . $hdntl;

/* =========================
 * 5. REDIRECT
 * ========================= */
header("Location: $finalUrl", true, 302);
exit;
