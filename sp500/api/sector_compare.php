<?php
// GET /sp500/api/sector_compare.php?tickers=AAPL,MSFT,GOOG&from=2021-01-01&to=2026-12-31
// → {"dates":[...],"series":{"AAPL":[...],"MSFT":[...]}}
require __DIR__ . '/_db.php';

$raw     = trim($_GET['tickers'] ?? '');
$from    = trim($_GET['from']    ?? '');
$to      = trim($_GET['to']      ?? date('Y-m-d'));
$limit   = min((int)($_GET['limit'] ?? 10), 20);  // 최대 20개 종목

if (!$raw || !$from) {
    http_response_code(400);
    echo json_encode(['error' => 'tickers and from required']);
    exit;
}

// 티커 정제: 알파뉴메릭 + 점/하이픈만 허용
$tickers = array_slice(
    array_filter(
        array_map('trim', explode(',', $raw)),
        fn($t) => preg_match('/^[A-Z0-9.\-]{1,10}$/', $t)
    ),
    0, $limit
);

if (empty($tickers)) {
    echo json_encode(['dates' => [], 'series' => (object)[]]);
    exit;
}

// IN 절 준비 (파라미터 바인딩)
$placeholders = implode(',', array_fill(0, count($tickers), '?'));
$params = array_merge($tickers, [$from, $to]);

$sql = "SELECT ticker, date, close FROM daily
        WHERE ticker IN ($placeholders)
          AND date >= ? AND date <= ?
        ORDER BY ticker, date";

try {
    $st = $db->prepare($sql);
    $st->execute($params);
    $rows = $st->fetchAll(PDO::FETCH_ASSOC);
} catch (Exception $e) {
    echo json_encode(['dates' => [], 'series' => (object)[]]);
    exit;
}

// 날짜 유니온 + 시리즈 구성
$dateSet = [];
$series  = [];
foreach ($rows as $r) {
    $dateSet[$r['date']] = true;
    $series[$r['ticker']][$r['date']] = (float)$r['close'];
}
ksort($dateSet);
$dates = array_keys($dateSet);

$out = [];
foreach ($series as $ticker => $map) {
    $arr = [];
    foreach ($dates as $d) {
        $arr[] = isset($map[$d]) ? round($map[$d], 4) : null;
    }
    $out[$ticker] = $arr;
}

echo json_encode(['dates' => $dates, 'series' => $out ?: (object)[]]);
