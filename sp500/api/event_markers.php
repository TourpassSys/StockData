<?php
// GET /sp500/api/event_markers.php?ticker=AAPL&from=2018-01-01&to=2018-12-31
// 날짜별 이벤트 존재 여부 + 최대 impact + 대표 카테고리 반환
// 차트 마커 렌더링용 경량 API
require __DIR__ . '/_db.php';

$DB_EVENTS = __DIR__ . '/../db/events.db';
if (!file_exists($DB_EVENTS)) {
    echo json_encode(['markers' => [], 'status' => 'db_not_ready']);
    exit;
}
try {
    $edb = new PDO('sqlite:' . $DB_EVENTS);
    $edb->exec('PRAGMA journal_mode=WAL; PRAGMA cache_size=2000;');
} catch (Exception $e) {
    echo json_encode(['markers' => []]);
    exit;
}

$ticker = strtoupper(trim($_GET['ticker'] ?? ''));
$from   = trim($_GET['from'] ?? '');
$to     = trim($_GET['to']   ?? '');

if (!$from || !$to) {
    http_response_code(400);
    echo json_encode(['error' => 'from/to required']);
    exit;
}

// 날짜별 집계: 최대 impact, 대표 카테고리, 긍부정 집계
if ($ticker) {
    $sql = "SELECT date,
                   MAX(impact) as max_impact,
                   SUM(CASE WHEN sentiment > 0 THEN 1 ELSE 0 END) as pos,
                   SUM(CASE WHEN sentiment < 0 THEN 1 ELSE 0 END) as neg,
                   COUNT(*) as cnt,
                   GROUP_CONCAT(DISTINCT category) as categories
            FROM events
            WHERE (ticker = ? OR scope = 'MARKET')
              AND date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date";
    $st = $edb->prepare($sql);
    $st->execute([$ticker, $from, $to]);
} else {
    $sql = "SELECT date,
                   MAX(impact) as max_impact,
                   SUM(CASE WHEN sentiment > 0 THEN 1 ELSE 0 END) as pos,
                   SUM(CASE WHEN sentiment < 0 THEN 1 ELSE 0 END) as neg,
                   COUNT(*) as cnt,
                   GROUP_CONCAT(DISTINCT category) as categories
            FROM events
            WHERE scope = 'MARKET' AND date >= ? AND date <= ?
            GROUP BY date ORDER BY date";
    $st = $edb->prepare($sql);
    $st->execute([$from, $to]);
}

$markers = [];
foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
    $net = (int)$r['pos'] - (int)$r['neg'];
    $markers[$r['date']] = [
        'impact'     => (int)$r['max_impact'],
        'count'      => (int)$r['cnt'],
        'sentiment'  => $net > 0 ? 1 : ($net < 0 ? -1 : 0),
        'categories' => explode(',', $r['categories'] ?? ''),
    ];
}
echo json_encode(['markers' => $markers]);
