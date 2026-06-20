#!/usr/bin/env python3
"""
5년치 일봉 데이터를 기존 stocks.db의 daily 테이블에 통합
- 기존: minute ticks (2017-09-11 ~ 2018-02-16) 에서 집계된 daily
- 추가: all_stocks_5yr.csv daily (2013-02-08 ~ 2018-02-07)
- 병합: 5yr 데이터를 우선, 이후 구간은 minute-derived daily 유지
"""
import os, sqlite3
import pandas as pd

BASE    = os.path.dirname(os.path.abspath(__file__))
DB      = os.path.join(BASE, 'db', 'stocks.db')
CSV_5YR = '/Users/choids/Downloads/archive_5y/all_stocks_5yr.csv'

print("5yr CSV 로딩...")
df = pd.read_csv(CSV_5YR, parse_dates=['date'])
df['date'] = df['date'].dt.strftime('%Y-%m-%d')
df.rename(columns={'Name': 'ticker'}, inplace=True)
df = df[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']]
df = df.dropna(subset=['open', 'close'])

print(f"  rows: {len(df):,}  tickers: {df['ticker'].nunique()}  range: {df['date'].min()} ~ {df['date'].max()}")

conn = sqlite3.connect(DB)
cur  = conn.cursor()

# daily 테이블에 5yr 데이터 UPSERT (기존 레코드 우선 유지 — minute-derived가 더 정밀)
# → INSERT OR IGNORE: 이미 있는 날짜/티커는 그대로, 없는 날짜는 추가
print("daily 테이블에 5yr 데이터 삽입 중...")
rows = list(df.itertuples(index=False, name=None))
cur.executemany(
    "INSERT OR IGNORE INTO daily(ticker, date, open, high, low, close, volume) VALUES(?,?,?,?,?,?,?)",
    rows
)
conn.commit()
print(f"  삽입 완료: {cur.rowcount:,}행 추가")

# tickers_list 갱신 (5yr에만 있는 종목 추가)
tickers_5yr = df['ticker'].unique().tolist()
cur.executemany("INSERT OR IGNORE INTO tickers_list VALUES(?)", [(t,) for t in tickers_5yr])
conn.commit()

# summary 갱신: 5yr 기간 기준으로 change_pct 재계산
print("summary 재계산 중...")
cur.execute("SELECT DISTINCT ticker FROM daily ORDER BY ticker")
all_tickers = [r[0] for r in cur.fetchall()]

updated = 0
for ticker in all_tickers:
    # daily 전체 기간 첫/마지막 종가
    cur.execute(
        "SELECT close FROM daily WHERE ticker=? ORDER BY date ASC LIMIT 1", (ticker,)
    )
    r_first = cur.fetchone()
    cur.execute(
        "SELECT close FROM daily WHERE ticker=? ORDER BY date DESC LIMIT 1", (ticker,)
    )
    r_last = cur.fetchone()
    cur.execute(
        "SELECT SUM(volume) FROM daily WHERE ticker=?", (ticker,)
    )
    r_vol = cur.fetchone()
    cur.execute(
        "SELECT n_sequences FROM summary WHERE ticker=?", (ticker,)
    )
    r_seq = cur.fetchone()

    if not r_first or not r_last:
        continue

    first_close = float(r_first[0])
    last_close  = float(r_last[0])
    chg = ((last_close - first_close) / first_close * 100) if first_close else 0
    vol = float(r_vol[0]) if r_vol and r_vol[0] else 0
    n_seq = int(r_seq[0]) if r_seq else 0

    cur.execute("""
        INSERT INTO summary(ticker, last_close, change_pct, total_volume, n_sequences)
        VALUES(?,?,?,?,?)
        ON CONFLICT(ticker) DO UPDATE SET
            last_close=excluded.last_close,
            change_pct=excluded.change_pct,
            total_volume=excluded.total_volume
    """, (ticker, round(last_close, 4), round(chg, 4), vol, n_seq))
    updated += 1

conn.commit()

# 최종 통계
cur.execute("SELECT COUNT(*) FROM daily")
total_daily = cur.fetchone()[0]
cur.execute("SELECT MIN(date), MAX(date) FROM daily")
date_range = cur.fetchone()
cur.execute("SELECT COUNT(DISTINCT ticker) FROM daily")
n_tickers = cur.fetchone()[0]

conn.close()

print(f"\n=== 병합 완료 ===")
print(f"daily 총: {total_daily:,}행  ({date_range[0]} ~ {date_range[1]})")
print(f"종목 수:  {n_tickers}개")
print(f"summary 갱신: {updated}개")
