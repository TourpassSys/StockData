<?php
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

$DB_PATH = __DIR__ . '/../db/merged_stocks.db';
if (!file_exists($DB_PATH)) {
    http_response_code(503);
    echo json_encode(['error' => 'DB not found. Run convert_to_sqlite.py first.']);
    exit;
}
try {
    $db = new PDO('sqlite:' . $DB_PATH);
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->exec('PRAGMA journal_mode=WAL; PRAGMA cache_size=8000;');
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage()]);
    exit;
}

define('SCALER', [
    'price_max'  => 1961.45,
    'price_min'  => 3.42,
    'volume_max' => 23145858.0,
    'volume_min' => 100.0,
    'timesteps'  => 100,
]);
