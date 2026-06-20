<?php
// GET /data/v1/sp500/api/sequences.php?ticker=AAPL
require __DIR__ . '/_db.php';

$ticker = strtoupper(trim($_GET['ticker'] ?? ''));
if (!$ticker) { http_response_code(400); echo json_encode(['error' => 'ticker required']); exit; }

$st = $db->prepare("SELECT n_sequences FROM summary WHERE ticker=?");
$st->execute([$ticker]);
$row = $st->fetch(PDO::FETCH_ASSOC);
if (!$row) { http_response_code(404); echo json_encode(['error' => 'ticker not found']); exit; }

$n = (int)$row['n_sequences'];
$starts = [];
for ($i = 0; $i < $n; $i++) {
    $st2 = $db->prepare("SELECT ts FROM ticks WHERE ticker=? ORDER BY ts LIMIT 1 OFFSET ?");
    $st2->execute([$ticker, $i * 100]);
    $r = $st2->fetchColumn();
    if ($r) $starts[] = $r;
}
$st3 = $db->prepare("SELECT COUNT(*) FROM ticks WHERE ticker=?");
$st3->execute([$ticker]);

echo json_encode([
    'ticker'      => $ticker,
    'total_rows'  => (int)$st3->fetchColumn(),
    'n_sequences' => $n,
    'timesteps'   => 100,
    'seq_starts'  => $starts,
]);
