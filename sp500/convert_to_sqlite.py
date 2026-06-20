#!/usr/bin/env python3
"""
CSV → SQLite 변환 (1회 실행)
출력: db/stocks.db
"""
import os, sqlite3, math
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
CSV  = os.path.join(BASE, 'db', 'snp500_2018_2017_stock.csv')
DB   = os.path.join(BASE, 'db', 'stocks.db')

TIMESTEPS   = 100
TRADE_START = pd.Timestamp('09:30:00').time()
TRADE_END   = pd.Timestamp('16:00:00').time()

if os.path.exists(DB):
    os.remove(DB)
    print("기존 DB 삭제")

print("CSV 로딩...")
raw = pd.read_csv(CSV, header=[0,1], index_col=0, skiprows=[2])
raw.index = pd.to_datetime(raw.index)
tickers = sorted(raw.columns.get_level_values(0).unique().tolist())
print(f"종목 수: {len(tickers)}")

# 거래 시간 마스크
mask = (raw.index.time >= TRADE_START) & (raw.index.time <= TRADE_END)
raw_trade = raw[mask]

conn = sqlite3.connect(DB)
cur  = conn.cursor()

cur.executescript("""
CREATE TABLE ticks (
    ticker  TEXT NOT NULL,
    ts      TEXT NOT NULL,
    open    REAL,
    high    REAL,
    low     REAL,
    close   REAL,
    volume  REAL
);
CREATE INDEX idx_ticks ON ticks(ticker, ts);

CREATE TABLE daily (
    ticker  TEXT NOT NULL,
    date    TEXT NOT NULL,
    open    REAL,
    high    REAL,
    low     REAL,
    close   REAL,
    volume  REAL,
    PRIMARY KEY(ticker, date)
);
CREATE INDEX idx_daily ON daily(ticker);

CREATE TABLE summary (
    ticker       TEXT PRIMARY KEY,
    last_close   REAL,
    change_pct   REAL,
    total_volume REAL,
    n_sequences  INTEGER
);

CREATE TABLE tickers_list (
    ticker TEXT PRIMARY KEY
);
""")

print("데이터 삽입 중...")
total = len(tickers)
for i, ticker in enumerate(tickers, 1):
    df = raw_trade[ticker].apply(pd.to_numeric, errors='coerce').dropna(how='all')
    if df.empty:
        continue

    # ticks
    rows = [
        (ticker, str(ts), row['open'], row['high'], row['low'], row['close'], row['volume'])
        for ts, row in df.iterrows()
    ]
    cur.executemany(
        "INSERT INTO ticks(ticker,ts,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
        rows
    )

    # daily (resample)
    d = df.resample('D').agg(
        open=('open','first'), high=('high','max'),
        low=('low','min'),    close=('close','last'),
        volume=('volume','sum')
    ).dropna(how='all')
    drows = [
        (ticker, str(date.date()), r['open'], r['high'], r['low'], r['close'], r['volume'])
        for date, r in d.iterrows()
    ]
    cur.executemany(
        "INSERT INTO daily(ticker,date,open,high,low,close,volume) VALUES(?,?,?,?,?,?,?)",
        drows
    )

    # summary
    closes = df['close'].dropna()
    if len(closes) >= 2:
        chg = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0] * 100
        n_seq = math.floor(len(df) / TIMESTEPS)
        cur.execute(
            "INSERT INTO summary VALUES(?,?,?,?,?)",
            (ticker, round(float(closes.iloc[-1]),4),
             round(float(chg),4), float(df['volume'].sum()), n_seq)
        )

    # ticker list
    cur.execute("INSERT OR IGNORE INTO tickers_list VALUES(?)", (ticker,))

    if i % 50 == 0 or i == total:
        conn.commit()
        print(f"  {i}/{total} ({ticker})")

conn.commit()
conn.close()

size_mb = os.path.getsize(DB) / 1024 / 1024
print(f"\n완료: {DB}  ({size_mb:.1f} MB)")
