<?php
// GET /sp500/api/events.php
// ?ticker=AAPL&date=2018-01-05
// ?date=2018-01-05&scope=MARKET
// ?ticker=AAPL&date_from=2018-01-01&date_to=2018-12-31
require __DIR__ . '/_db.php';

$DB_EVENTS = __DIR__ . '/../db/events.db';
if (!file_exists($DB_EVENTS)) {
    echo json_encode(['events' => [], 'count' => 0, 'status' => 'db_not_ready']);
    exit;
}
try {
    $edb = new PDO('sqlite:' . $DB_EVENTS);
    $edb->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $edb->exec('PRAGMA journal_mode=WAL; PRAGMA cache_size=4000;');
} catch (Exception $e) {
    echo json_encode(['events' => [], 'count' => 0, 'status' => 'db_error']);
    exit;
}

$ticker    = strtoupper(trim($_GET['ticker']    ?? ''));
$date      = trim($_GET['date']      ?? '');
$date_from = trim($_GET['date_from'] ?? '');
$date_to   = trim($_GET['date_to']   ?? '');
$scope     = strtoupper(trim($_GET['scope'] ?? ''));
$category  = strtoupper(trim($_GET['category'] ?? ''));
$limit     = min((int)($_GET['limit'] ?? 50), 200);

$where = [];
$params = [];

if ($ticker) {
    // 종목 이벤트 + 시장 전체 이벤트
    $where[] = '(ticker = ? OR scope = \'MARKET\')';
    $params[] = $ticker;
} elseif ($scope) {
    $where[] = 'scope = ?';
    $params[] = $scope;
}

if ($date) {
    $where[] = 'date = ?';
    $params[] = $date;
} elseif ($date_from && $date_to) {
    $where[] = 'date >= ? AND date <= ?';
    $params[] = $date_from;
    $params[] = $date_to;
}

if ($category) {
    $where[] = 'category = ?';
    $params[] = $category;
}

$sql = 'SELECT id, ticker, sector, date, time, title, summary, url,
               category, sentiment, impact, scope, source,
               link_ok, link_checked_at
        FROM events'
     . ($where ? ' WHERE ' . implode(' AND ', $where) : '')
     . ' ORDER BY date DESC, impact DESC, id DESC'
     . ' LIMIT ' . $limit;

try {
    $st = $edb->prepare($sql);
    $st->execute($params);
    $rows = $st->fetchAll(PDO::FETCH_ASSOC);
} catch (Exception $e) {
    echo json_encode(['events' => [], 'count' => 0, 'status' => 'table_not_ready']);
    exit;
}

foreach ($rows as &$r) {
    $r['sentiment'] = (int)$r['sentiment'];
    $r['impact']    = (int)$r['impact'];
    // link_ok: NULL=미확인, 1=유효, 0=깨짐
    $r['link_ok']   = $r['link_ok'] === null ? null : (int)$r['link_ok'];
}
echo json_encode(['events' => array_values($rows), 'count' => count($rows)]);
