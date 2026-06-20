"""
S&P 500 주가 외부요인 이벤트 수집기
수집원:
  1. FRED (pandas_datareader) — 금리·CPI·GDP·실업률
  2. SEC EDGAR — 8-K(임원변동/주요공시), 10-Q/10-K(실적)
  3. yfinance — 어닝 히스토리 (EPS 서프라이즈)
  4. Yahoo Finance news — 최근 뉴스 헤드라인

출력: sp500/db/events.db
"""
import sqlite3, json, time
from datetime import datetime
from pathlib import Path
import urllib.request, gzip
import yfinance as yf

BASE   = Path(__file__).parent
DB_PATH      = BASE / "db" / "events.db"
TICKERS_DB   = BASE / "db" / "stocks.db"
CIK_MAP_PATH = BASE / "db" / "cik_map.json"

EDGAR_HEADERS = {'User-Agent': 'StockDashboard/1.0 cuidacheng@gmail.com', 'Accept-Encoding': 'gzip'}

ITEM_MAP = {
    '2.02': ('EARNINGS',    4, '실적발표'),
    '5.02': ('MANAGEMENT',  3, '임원변동'),
    '1.01': ('POLICY',      3, '중요계약'),
    '1.03': ('LEGAL',       4, '파산/구조조정'),
    '2.01': ('COMPETITOR',  3, '사업양수도'),
    '7.01': ('ANALYST',     2, '공정공시'),
    '8.01': ('PRODUCT',     3, '기타중요공시'),
    '5.03': ('MANAGEMENT',  3, '정관변경'),
    '4.01': ('ANALYST',     3, '회계법인변경'),
    '9.01': ('EARNINGS',    2, '재무제표첨부'),
}

# ── DB 초기화 ──────────────────────────────────────────────────────────────
def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker     TEXT,
            sector     TEXT,
            date       TEXT NOT NULL,
            time       TEXT,
            title      TEXT NOT NULL,
            summary    TEXT,
            url        TEXT,
            category   TEXT NOT NULL,
            sentiment  INTEGER DEFAULT 0,
            impact     INTEGER DEFAULT 3,
            scope      TEXT DEFAULT 'MARKET',
            source     TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ticker, date, title, source)
        );
        CREATE INDEX IF NOT EXISTS idx_events_date        ON events(date);
        CREATE INDEX IF NOT EXISTS idx_events_ticker_date ON events(ticker, date);
        CREATE INDEX IF NOT EXISTS idx_events_scope_date  ON events(scope, date);
        CREATE INDEX IF NOT EXISTS idx_events_category    ON events(category, date);
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
    """)
    conn.commit()

# ────────────────────────────────────────────────────────────────────────────
# SOURCE 1: FRED — 거시경제 지표
# ────────────────────────────────────────────────────────────────────────────
def fetch_fred(conn):
    from pandas_datareader.data import DataReader
    import pandas as pd

    SERIES = {
        'DFEDTARU': ('MACRO', 5, '연준 기준금리 상한',     True,  '%'),
        'DFEDTARL': ('MACRO', 4, '연준 기준금리 하한',     True,  '%'),
        'CPIAUCSL': ('MACRO', 4, 'CPI (소비자물가지수)',   False, ''),
        'UNRATE':   ('MACRO', 3, '미국 실업률',            False, '%'),
        'A191RL1Q225SBEA': ('MACRO', 4, '미국 GDP 성장률 (QoQ)', False, '%'),
        'DGS10':    ('MACRO', 3, '미국 10년 국채금리',     True,  '%'),
    }

    print("[FRED] 거시경제 지표 수집 중...")
    total = 0
    try:
        df = DataReader(list(SERIES.keys()), 'fred', '2013-01-01', '2026-12-31')
    except Exception as e:
        print(f"  FRED 일괄 조회 실패: {e}")
        return

    rows = []
    for series_id, (cat, imp, label, invert_sentiment, unit) in SERIES.items():
        col = df[series_id].dropna()
        prev = None
        for dt, val in col.items():
            date_str = dt.strftime('%Y-%m-%d')
            if prev is None:
                prev = val
                continue
            diff = val - prev
            if abs(diff) < 0.001:
                prev = val
                continue
            # 감성: 금리·국채는 인상이 주식에 부정
            base_sentiment = 1 if diff > 0 else -1
            sentiment = -base_sentiment if invert_sentiment else base_sentiment
            arrow = '▲' if diff > 0 else '▼'
            title = f"{label} {arrow} {val:.2f}{unit} ({'+' if diff>0 else ''}{diff:.2f}{unit})"
            rows.append((None, None, date_str, None, title, None, None,
                         cat, sentiment, imp, 'MARKET', f'FRED/{series_id}'))
            prev = val

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO events(ticker,sector,date,time,title,summary,url,category,sentiment,impact,scope,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            rows
        )
        conn.commit()
        total = len(rows)
    print(f"  FRED 합계: {total}건")

# ────────────────────────────────────────────────────────────────────────────
# SOURCE 2: SEC EDGAR — 8-K / 10-Q / 10-K 공시
# ────────────────────────────────────────────────────────────────────────────
def fetch_edgar_ticker(conn, ticker: str, cik: str, sector: str = None) -> int:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        req = urllib.request.Request(url, headers=EDGAR_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            try:
                data = json.loads(gzip.decompress(raw))
            except Exception:
                data = json.loads(raw)

        filings = data.get('filings', {}).get('recent', {})
        forms   = filings.get('form', [])
        dates   = filings.get('filingDate', [])
        descs   = filings.get('primaryDocument', [])
        accs    = filings.get('accessionNumber', [])
        items_f = filings.get('items', [])

        rows = []
        for i, form in enumerate(forms):
            if form not in ('8-K', '10-Q', '10-K'):
                continue
            fdate = dates[i] if i < len(dates) else ''
            if not fdate or fdate < '2013-01-01':
                continue
            items_raw = items_f[i] if i < len(items_f) else ''
            acc = accs[i].replace('-', '') if i < len(accs) else ''
            doc = descs[i] if i < len(descs) else ''
            cik_int = int(cik)
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{doc}" if acc and doc else None

            if form == '10-Q':
                rows.append((ticker, sector, fdate, None,
                             f"{ticker} 분기보고서 (10-Q)", None, doc_url,
                             'EARNINGS', 0, 3, 'STOCK', 'SEC/10-Q'))
            elif form == '10-K':
                rows.append((ticker, sector, fdate, None,
                             f"{ticker} 연간보고서 (10-K)", None, doc_url,
                             'EARNINGS', 0, 4, 'STOCK', 'SEC/10-K'))
            elif form == '8-K' and items_raw:
                matched = False
                for item_key, (cat, imp, label) in ITEM_MAP.items():
                    if item_key in items_raw:
                        title = f"{ticker} {label} (8-K {item_key})"
                        rows.append((ticker, sector, fdate, None, title, items_raw,
                                     doc_url, cat, 0, imp, 'STOCK', 'SEC/8-K'))
                        matched = True
                        break
                if not matched:
                    rows.append((ticker, sector, fdate, None,
                                 f"{ticker} 주요공시 (8-K)", items_raw, doc_url,
                                 'PRODUCT', 0, 2, 'STOCK', 'SEC/8-K'))

        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO events(ticker,sector,date,time,title,summary,url,category,sentiment,impact,scope,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                rows
            )
            conn.commit()
        return len(rows)
    except Exception as e:
        return 0

# ────────────────────────────────────────────────────────────────────────────
# SOURCE 3: yfinance 어닝 히스토리 (EPS 서프라이즈)
# ────────────────────────────────────────────────────────────────────────────
def fetch_earnings(conn, ticker: str, sector: str = None) -> int:
    try:
        import pandas as pd
        t = yf.Ticker(ticker)
        hist = t.earnings_history
        if hist is None or (hasattr(hist, 'empty') and hist.empty):
            return 0
        rows = []
        for _, row in hist.iterrows():
            dt = str(row.name)[:10] if hasattr(row.name, '__str__') else ''
            if not dt or dt < '2013-01-01':
                continue
            eps_actual   = row.get('epsActual')
            eps_estimate = row.get('epsEstimate')
            surp_pct     = row.get('surprisePercent', None)
            if eps_actual is None or (eps_actual != eps_actual):
                continue
            # 감성
            sentiment = 0
            if surp_pct is not None and surp_pct == surp_pct:
                if surp_pct > 10:    sentiment = 2
                elif surp_pct > 0:   sentiment = 1
                elif surp_pct < -10: sentiment = -2
                else:                sentiment = -1
            # 제목
            arrow = ''
            if eps_estimate and eps_estimate == eps_estimate:
                diff  = eps_actual - eps_estimate
                arrow = f" (예상 ${eps_estimate:.2f}, {'▲' if diff>=0 else '▼'}{abs(diff):.2f})"
            title = f"{ticker} 실적 EPS ${eps_actual:.2f}{arrow}"
            summary = None
            if surp_pct is not None and surp_pct == surp_pct:
                summary = f"EPS 서프라이즈: {surp_pct:+.1f}%"
            rows.append((ticker, sector, dt, None, title, summary, None,
                         'EARNINGS', sentiment, 4, 'STOCK', 'yfinance/earnings'))
        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO events(ticker,sector,date,time,title,summary,url,category,sentiment,impact,scope,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                rows
            )
            conn.commit()
        return len(rows)
    except Exception:
        return 0

# ────────────────────────────────────────────────────────────────────────────
# SOURCE 4: Yahoo Finance 최근 뉴스
# ────────────────────────────────────────────────────────────────────────────
KW_CAT = [
    (['earn','eps','revenue','profit','quarter','results','beat','miss'],  'EARNINGS',   3),
    (['ceo','cfo','appoint','resign','hire','fire','executive','officer'], 'MANAGEMENT', 3),
    (['launch','release','unveil','new product','iphone','new model'],     'PRODUCT',    2),
    (['lawsuit','fine','penalty','regulat','antitrust','ban','block'],     'POLICY',     3),
    (['upgrade','downgrade','target price','buy','sell','hold','analyst'], 'ANALYST',    2),
    (['merger','acqui','takeover','deal','partnership'],                    'COMPETITOR', 3),
    (['war','sanction','tariff','trade','geopolit'],                        'GEO',        4),
]

def classify_news(title: str):
    tl = title.lower()
    for kws, cat, imp in KW_CAT:
        if any(w in tl for w in kws):
            return cat, imp
    return 'PRODUCT', 2

def fetch_yf_news(conn, ticker: str, sector: str = None) -> int:
    try:
        t = yf.Ticker(ticker)
        news = t.news
        if not news:
            return 0
        rows = []
        for n in news[:30]:
            pub = n.get('providerPublishTime', 0)
            if not pub:
                continue
            dt  = datetime.fromtimestamp(pub).strftime('%Y-%m-%d')
            tm  = datetime.fromtimestamp(pub).strftime('%H:%M')
            if dt < '2013-01-01':
                continue
            title  = n.get('title', '').strip()
            url    = n.get('link', '')
            source = n.get('publisher', '')
            if not title:
                continue
            cat, imp = classify_news(title)
            rows.append((ticker, sector, dt, tm, title, None, url,
                         cat, 0, imp, 'STOCK', f'YF/{source}'))
        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO events(ticker,sector,date,time,title,summary,url,category,sentiment,impact,scope,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                rows
            )
            conn.commit()
        return len(rows)
    except Exception:
        return 0

# ── 메인 ──────────────────────────────────────────────────────────────────
def main():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    # 1. FRED 거시경제
    fetch_fred(conn)

    # CIK 맵 로드
    cik_map = json.loads(CIK_MAP_PATH.read_text()) if CIK_MAP_PATH.exists() else {}

    # 종목 목록
    src = sqlite3.connect(TICKERS_DB)
    tickers = [r[0] for r in src.execute("SELECT ticker FROM tickers_list ORDER BY ticker").fetchall()]
    src.close()

    # 이미 수집된 종목 스킵
    done = {r[0] for r in conn.execute(
        "SELECT DISTINCT ticker FROM events WHERE ticker IS NOT NULL AND source LIKE 'SEC/%'"
    ).fetchall()}
    remaining = [t for t in tickers if t not in done]

    print(f"\n[종목별] {len(tickers)}종목 | 완료 {len(done)} | 남은 {len(remaining)}")
    start = __import__('time').time()

    for idx, ticker in enumerate(remaining, 1):
        cik = cik_map.get(ticker)
        edgar_cnt = 0
        if cik:
            edgar_cnt = fetch_edgar_ticker(conn, ticker, cik)
            time.sleep(0.2)

        earn_cnt = fetch_earnings(conn, ticker)
        time.sleep(0.3)

        news_cnt = fetch_yf_news(conn, ticker)
        time.sleep(0.5)

        elapsed = __import__('time').time() - start
        eta = elapsed / idx * (len(remaining) - idx)
        print(f"  [{idx:3d}/{len(remaining)}] {ticker:6s}  EDGAR:{edgar_cnt:3d}  EPS:{earn_cnt:2d}  뉴스:{news_cnt:2d}  ETA:{eta/60:.0f}분")

    # 최종 통계
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    cats  = conn.execute("SELECT category, COUNT(*) FROM events GROUP BY category ORDER BY COUNT(*) DESC").fetchall()
    conn.close()
    print(f"\n{'='*50}")
    print(f"총 이벤트: {total:,}건")
    for cat, cnt in cats:
        print(f"  {cat:12s}: {cnt:,}")
    print(f"저장: {DB_PATH}")

if __name__ == '__main__':
    main()
