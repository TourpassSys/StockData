<?php
/**
 * S&P 500 API
 * Endpoints:
 *   GET /data/v1/sp500/api/tickers
 *   GET /data/v1/sp500/api/scaler
 *   GET /data/v1/sp500/api/summary
 *   GET /data/v1/sp500/api/stock/{ticker}?mode=daily|minute&normalized=true|false&trading=true|false&seq=N&limit=N
 *   GET /data/v1/sp500/api/sequences/{ticker}
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

// ── DB 연결 ────────────────────────────────────────────
$DB_PATH = __DIR__ . '/../db/stocks.db';
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

// ── 라우팅 ────────────────────────────────────────────
$uri   = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$path  = preg_replace('#^.*?/sp500/api#', '', $uri);   // /tickers, /stock/AAPL 등
$parts = array_values(array_filter(explode('/', $path)));

$SCALER = [
    'price_max'  => 1961.45,
    'price_min'  => 3.42,
    'volume_max' => 23145858.0,
    'volume_min' => 100.0,
    'timesteps'  => 100,
];

switch ($parts[0] ?? '') {

    // ── /tickers ────────────────────────────
    case 'tickers':
        $rows = $db->query("SELECT ticker FROM tickers_list ORDER BY ticker")->fetchAll(PDO::FETCH_COLUMN);
        echo json_encode(array_values($rows));
        break;

    // ── /scaler ─────────────────────────────
    case 'scaler':
        echo json_encode($SCALER);
        break;

    // ── /summary ────────────────────────────
    case 'summary':
        $rows = $db->query("SELECT ticker, last_close, change_pct, total_volume AS volume, n_sequences FROM summary ORDER BY ticker")->fetchAll(PDO::FETCH_ASSOC);
        foreach ($rows as &$r) {
            $r['last_close']  = (float)$r['last_close'];
            $r['change_pct']  = (float)$r['change_pct'];
            $r['volume']      = (float)$r['volume'];
            $r['n_sequences'] = (int)$r['n_sequences'];
        }
        echo json_encode(array_values($rows));
        break;

    // ── /stock/{ticker} ─────────────────────
    case 'stock':
        $ticker     = strtoupper($parts[1] ?? '');
        $mode       = $_GET['mode']       ?? 'daily';    // daily | minute
        $normalized = ($_GET['normalized'] ?? 'false') === 'true';
        $seq        = isset($_GET['seq']) ? (int)$_GET['seq'] : null;
        $limit      = (int)($_GET['limit'] ?? 780);

        if (!$ticker) { err(400, 'ticker required'); }

        // 존재 확인
        $st = $db->prepare("SELECT 1 FROM tickers_list WHERE ticker=?");
        $st->execute([$ticker]);
        if (!$st->fetch()) { err(404, 'ticker not found'); }

        if ($mode === 'daily') {
            $st = $db->prepare(
                "SELECT date AS ts, open, high, low, close, volume FROM daily WHERE ticker=? ORDER BY date"
            );
            $st->execute([$ticker]);
        } else {
            // minute
            if ($seq !== null) {
                $offset = $seq * 100;
                $st = $db->prepare(
                    "SELECT ts, open, high, low, close, volume FROM ticks WHERE ticker=? ORDER BY ts LIMIT 100 OFFSET ?"
                );
                $st->execute([$ticker, $offset]);
            } else {
                $st = $db->prepare(
                    "SELECT ts, open, high, low, close, volume FROM ticks WHERE ticker=? ORDER BY ts DESC LIMIT ?"
                );
                $st->execute([$ticker, $limit]);
            }
        }

        $rows = $st->fetchAll(PDO::FETCH_ASSOC);
        if ($mode === 'minute' && $seq === null) {
            $rows = array_reverse($rows);
        }

        $out = ['ticker'=>$ticker, 'mode'=>$mode, 'normalized'=>$normalized,
                'timestamps'=>[], 'open'=>[], 'high'=>[], 'low'=>[], 'close'=>[], 'volume'=>[]];

        $pm = $SCALER['price_max'] - $SCALER['price_min'];
        $vm = $SCALER['volume_max'] - $SCALER['volume_min'];

        foreach ($rows as $r) {
            $o = (float)$r['open'];  $h = (float)$r['high'];
            $l = (float)$r['low'];   $c = (float)$r['close'];
            $v = (float)$r['volume'];

            if ($normalized) {
                $o = round(($o - $SCALER['price_min'])  / $pm, 6);
                $h = round(($h - $SCALER['price_min'])  / $pm, 6);
                $l = round(($l - $SCALER['price_min'])  / $pm, 6);
                $c = round(($c - $SCALER['price_min'])  / $pm, 6);
                $v = round(($v - $SCALER['volume_min']) / $vm, 6);
            } else {
                $o = round($o,4); $h = round($h,4);
                $l = round($l,4); $c = round($c,4);
                $v = round($v,2);
            }

            $out['timestamps'][] = $r['ts'];
            $out['open'][]       = $o;
            $out['high'][]       = $h;
            $out['low'][]        = $l;
            $out['close'][]      = $c;
            $out['volume'][]     = $v;
        }

        echo json_encode($out);
        break;

    // ── /sequences/{ticker} ─────────────────
    case 'sequences':
        $ticker = strtoupper($parts[1] ?? '');
        if (!$ticker) { err(400, 'ticker required'); }

        $st = $db->prepare("SELECT n_sequences FROM summary WHERE ticker=?");
        $st->execute([$ticker]);
        $row = $st->fetch(PDO::FETCH_ASSOC);
        if (!$row) { err(404, 'ticker not found'); }

        $n = (int)$row['n_sequences'];

        // 각 시퀀스 시작 ts
        $starts = [];
        for ($i = 0; $i < $n; $i++) {
            $st2 = $db->prepare("SELECT ts FROM ticks WHERE ticker=? ORDER BY ts LIMIT 1 OFFSET ?");
            $st2->execute([$ticker, $i * 100]);
            $r = $st2->fetch(PDO::FETCH_COLUMN);
            if ($r) $starts[] = $r;
        }

        // total_rows
        $st3 = $db->prepare("SELECT COUNT(*) FROM ticks WHERE ticker=?");
        $st3->execute([$ticker]);
        $total = (int)$st3->fetchColumn();

        echo json_encode([
            'ticker'      => $ticker,
            'total_rows'  => $total,
            'n_sequences' => $n,
            'timesteps'   => 100,
            'seq_starts'  => $starts,
        ]);
        break;

    default:
        err(404, 'endpoint not found');
}

if (!function_exists('err')) {
    function err(int $code, string $msg): void {
        http_response_code($code);
        echo json_encode(['error' => $msg]);
        exit;
    }
}
