# StockData

주식 시장 데이터 분석 · 시각화 · ML 파이프라인 모음

## 메뉴

| 섹션 | 설명 | 데이터 |
|---|---|---|
| [S&P 500](sp500/) | 502개 종목 일봉/분봉 대시보드 | 2013–2018 (5년) |

## 배포 URL

`https://stock.mulsaem.net/data/v1/`

## 구조

```
StockData/
├── index.html          ← 메인 메뉴
└── sp500/
    ├── index.html  ← S&P 500 대시보드
    ├── api/
    │   └── index.php   ← PHP API (SQLite)
    ├── db/             ← 데이터 파일 (gitignore)
    │   ├── snp500_2018_2017_stock.csv  (분봉, 648MB)
    │   └── stocks.db                   (SQLite, 2.1GB)
    ├── convert_to_sqlite.py  ← CSV → SQLite 변환 (1회)
    ├── merge_5yr.py          ← 5년치 일봉 병합
    └── deploy/
        ├── nginx.conf
        └── setup.sh
```

## 데이터 소스

- **분봉 (1min)**: [nickdl/alpha](https://github.com/nickdl/alpha) — Alpha Vantage API로 수집한 S&P 500 분봉 데이터 (2017-09 ~ 2018-02)
- **일봉 (5yr)**: [Kaggle S&P 500 stock data](https://www.kaggle.com/datasets/camnugent/sandp500) — 2013-02 ~ 2018-02

## 서버 설치

```bash
# 1. 파일 업로드
bash sp500/deploy/upload.sh

# 2. 서버에서 실행
cd /data/www/stock.mulsaem.net/data/v1
python3 sp500/convert_to_sqlite.py   # CSV → SQLite (1회)
python3 sp500/merge_5yr.py           # 5년치 병합 (1회)
sudo bash sp500/deploy/setup.sh      # nginx 설정
```

## API 엔드포인트

```
GET /data/v1/sp500/api/tickers
GET /data/v1/sp500/api/summary
GET /data/v1/sp500/api/scaler
GET /data/v1/sp500/api/stock/{ticker}?mode=daily|minute&normalized=true&seq=N
GET /data/v1/sp500/api/sequences/{ticker}
```
