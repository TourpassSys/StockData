<?php
// GET /data/v1/sp500/api/stock.php?ticker=AAPL&mode=daily|minute&normalized=true&trading=true&seq=N&limit=N
require __DIR__ . '/_db.php';

$ticker     = strtoupper(trim($_GET['ticker'] ?? ''));
$mode       = $_GET['mode']       ?? 'daily';
$normalized = ($_GET['normalized'] ?? 'false') === 'true';
$seq        = isset($_GET['seq']) ? (int)$_GET['seq'] : null;
$limit      = (int)($_GET['limit'] ?? 780);

if (!$ticker) { http_response_code(400); echo json_encode(['error' => 'ticker required']); exit; }

$st = $db->prepare("SELECT 1 FROM tickers_list WHERE ticker=?");
$st->execute([$ticker]);
if (!$st->fetch()) { http_response_code(404); echo json_encode(['error' => 'ticker not found']); exit; }

if ($mode === 'daily') {
    $st = $db->prepare("SELECT date AS ts, open, high, low, close, volume FROM daily WHERE ticker=? AND open IS NOT NULL AND close IS NOT NULL ORDER BY date");
    $st->execute([$ticker]);
} else {
    if ($seq !== null) {
        $st = $db->prepare("SELECT ts, open, high, low, close, volume FROM ticks WHERE ticker=? ORDER BY ts LIMIT 100 OFFSET ?");
        $st->execute([$ticker, $seq * 100]);
    } else {
        $st = $db->prepare("SELECT ts, open, high, low, close, volume FROM ticks WHERE ticker=? ORDER BY ts DESC LIMIT ?");
        $st->execute([$ticker, $limit]);
    }
}

$rows = $st->fetchAll(PDO::FETCH_ASSOC);
if ($mode === 'minute' && $seq === null) $rows = array_reverse($rows);

$out = ['ticker'=>$ticker,'mode'=>$mode,'normalized'=>$normalized,
        'timestamps'=>[],'open'=>[],'high'=>[],'low'=>[],'close'=>[],'volume'=>[]];

$pm = SCALER['price_max'] - SCALER['price_min'];
$vm = SCALER['volume_max'] - SCALER['volume_min'];

foreach ($rows as $r) {
    $o=(float)$r['open']; $h=(float)$r['high'];
    $l=(float)$r['low'];  $c=(float)$r['close']; $v=(float)$r['volume'];
    if ($normalized) {
        $o=round(($o-SCALER['price_min'])/$pm,6); $h=round(($h-SCALER['price_min'])/$pm,6);
        $l=round(($l-SCALER['price_min'])/$pm,6); $c=round(($c-SCALER['price_min'])/$pm,6);
        $v=round(($v-SCALER['volume_min'])/$vm,6);
    } else {
        $o=round($o,4); $h=round($h,4); $l=round($l,4); $c=round($c,4); $v=round($v,2);
    }
    $out['timestamps'][]=$r['ts']; $out['open'][]=$o; $out['high'][]=$h;
    $out['low'][]=$l; $out['close'][]=$c; $out['volume'][]=$v;
}
echo json_encode($out);
