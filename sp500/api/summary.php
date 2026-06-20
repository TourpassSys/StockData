<?php
require __DIR__ . '/_db.php';

$rows = $db->query(
    "SELECT ticker, last_close, change_pct, total_volume AS volume, n_sequences FROM summary ORDER BY ticker"
)->fetchAll(PDO::FETCH_ASSOC);

// sectors.json 병합
$sectorMap = [];
$sf = __DIR__ . '/../db/sectors.json';
if (file_exists($sf)) {
    $sectorMap = json_decode(file_get_contents($sf), true) ?: [];
}

foreach ($rows as &$r) {
    $r['last_close']  = (float)$r['last_close'];
    $r['change_pct']  = (float)$r['change_pct'];
    $r['volume']      = (float)$r['volume'];
    $r['n_sequences'] = (int)$r['n_sequences'];
    $info = $sectorMap[$r['ticker']] ?? [];
    $r['sector']   = $info['sector']   ?? 'Unknown';
    $r['industry'] = $info['industry'] ?? '';
    $r['name']     = $info['name']     ?? $r['ticker'];
}
echo json_encode(array_values($rows));
