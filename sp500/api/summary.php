<?php
require __DIR__ . '/_db.php';
$rows = $db->query("SELECT ticker, last_close, change_pct, total_volume AS volume, n_sequences FROM summary ORDER BY ticker")->fetchAll(PDO::FETCH_ASSOC);
foreach ($rows as &$r) {
    $r['last_close']  = (float)$r['last_close'];
    $r['change_pct']  = (float)$r['change_pct'];
    $r['volume']      = (float)$r['volume'];
    $r['n_sequences'] = (int)$r['n_sequences'];
}
echo json_encode(array_values($rows));
