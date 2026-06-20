<?php
// GET /sp500/api/sectors.php
// → {"AAPL":{"sector":"Technology","industry":"...","name":"..."},...}
require __DIR__ . '/_db.php';
$f = __DIR__ . '/../db/sectors.json';
if (!file_exists($f)) {
    echo json_encode([]);
} else {
    header('Cache-Control: public, max-age=3600');
    echo file_get_contents($f);
}
