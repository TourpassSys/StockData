<?php
require __DIR__ . '/_db.php';
$rows = $db->query("SELECT ticker FROM tickers_list ORDER BY ticker")->fetchAll(PDO::FETCH_COLUMN);
echo json_encode(array_values($rows));
