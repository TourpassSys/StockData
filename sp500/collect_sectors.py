"""
Wikipedia S&P 500 목록에서 GICS 섹터 수집 → sectors.json
현재 및 과거 구성 종목 포함 (2013-2018 시대)
"""
import json, re, urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "db" / "sectors.json"

def fetch_wiki():
    """Wikipedia S&P 500 현재 목록 파싱"""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')

    result = {}
    # 첫 번째 테이블 (현재 구성 종목)
    table_m = re.search(r'<table[^>]*id="constituents"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not table_m:
        table_m = re.search(r'<table[^>]*wikitable[^>]*sortable[^>]*>(.*?)</table>', html, re.DOTALL)
    if not table_m:
        print("테이블 못찾음")
        return result

    rows = re.findall(r'<tr>(.*?)</tr>', table_m.group(1), re.DOTALL)
    for row in rows[1:]:  # 헤더 스킵
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
        if len(cells) < 4:
            continue
        ticker  = re.sub(r'<[^>]+>', '', cells[0]).strip().replace('.', '-')
        name    = re.sub(r'<[^>]+>', '', cells[1]).strip()
        sector  = re.sub(r'<[^>]+>', '', cells[2]).strip()
        industry = re.sub(r'<[^>]+>', '', cells[3]).strip() if len(cells) > 3 else ''
        if ticker:
            result[ticker] = {'sector': sector, 'industry': industry, 'name': name}
    return result

def fetch_wiki_changes():
    """Wikipedia S&P 500 과거 변경 목록 (삭제된 종목 섹터 추론)"""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')

    result = {}
    # 두 번째 테이블 (변경 이력)
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    for table in tables[1:]:
        rows = re.findall(r'<tr>(.*?)</tr>', table, re.DOTALL)
        for row in rows[1:]:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
            if len(cells) < 3:
                continue
            # 추가된 종목(added) 파싱
            for cell in cells:
                ticker = re.sub(r'<[^>]+>', '', cell).strip().replace('.', '-')
                if re.match(r'^[A-Z]{1,5}$', ticker):
                    result[ticker] = result.get(ticker, None)
    return result

# 알려진 섹터 매핑 (Wikipedia에 없는 구형 티커 보완)
KNOWN = {
    'AET':  {'sector': 'Health Care',            'industry': 'Managed Health Care',         'name': 'Aetna'},
    'AGN':  {'sector': 'Health Care',            'industry': 'Pharmaceuticals',              'name': 'Allergan'},
    'ALXN': {'sector': 'Health Care',            'industry': 'Biotechnology',                'name': 'Alexion'},
    'ANDV': {'sector': 'Energy',                 'industry': 'Oil & Gas Refining',           'name': 'Andeavor'},
    'ANTM': {'sector': 'Health Care',            'industry': 'Managed Health Care',         'name': 'Anthem'},
    'ATVI': {'sector': 'Communication Services', 'industry': 'Interactive Home Entertainment','name': 'Activision Blizzard'},
    'BF.B': {'sector': 'Consumer Staples',       'industry': 'Distillers & Vintners',        'name': 'Brown-Forman'},
    'BHGE': {'sector': 'Energy',                 'industry': 'Oil & Gas Equipment',          'name': 'Baker Hughes GE'},
    'BRK.B':{'sector': 'Financials',             'industry': 'Multi-Sector Holdings',        'name': 'Berkshire Hathaway'},
    'CBS':  {'sector': 'Communication Services', 'industry': 'Broadcasting',                 'name': 'CBS Corp'},
    'CELG': {'sector': 'Health Care',            'industry': 'Biotechnology',                'name': 'Celgene'},
    'CERN': {'sector': 'Health Care',            'industry': 'Health Care Technology',       'name': 'Cerner'},
    'CHK':  {'sector': 'Energy',                 'industry': 'Oil & Gas Exploration',        'name': 'Chesapeake Energy'},
    'CSRA': {'sector': 'Information Technology', 'industry': 'IT Consulting',                'name': 'CSRA'},
    'CTL':  {'sector': 'Communication Services', 'industry': 'Telecom Services',             'name': 'CenturyLink'},
    'CTXS': {'sector': 'Information Technology', 'industry': 'Application Software',         'name': 'Citrix Systems'},
    'DISCA':{'sector': 'Communication Services', 'industry': 'Broadcasting',                 'name': 'Discovery A'},
    'DISCK':{'sector': 'Communication Services', 'industry': 'Broadcasting',                 'name': 'Discovery C'},
    'DISH': {'sector': 'Communication Services', 'industry': 'Broadcasting',                 'name': 'Dish Network'},
    'DPS':  {'sector': 'Consumer Staples',       'industry': 'Soft Drinks',                  'name': 'Dr Pepper Snapple'},
    'DWDP': {'sector': 'Materials',              'industry': 'Diversified Chemicals',        'name': 'DowDuPont'},
    'ESRX': {'sector': 'Health Care',            'industry': 'Health Care Services',         'name': 'Express Scripts'},
    'ETFC': {'sector': 'Financials',             'industry': 'Investment Banking',           'name': 'E*TRADE'},
    'GGP':  {'sector': 'Real Estate',            'industry': 'Retail REITs',                 'name': 'GGP Inc'},
    'HCN':  {'sector': 'Real Estate',            'industry': 'Health Care REITs',            'name': 'Welltower'},
    'HCP':  {'sector': 'Real Estate',            'industry': 'Health Care REITs',            'name': 'HCP Inc'},
    'HOLX': {'sector': 'Health Care',            'industry': 'Health Care Equipment',        'name': 'Hologic'},
    'JEC':  {'sector': 'Industrials',            'industry': 'Construction & Engineering',   'name': 'Jacobs Engineering'},
    'JNPR': {'sector': 'Information Technology', 'industry': 'Communications Equipment',     'name': 'Juniper Networks'},
    'KORS': {'sector': 'Consumer Discretionary', 'industry': 'Apparel',                      'name': 'Michael Kors'},
    'KSU':  {'sector': 'Industrials',            'industry': 'Railroads',                    'name': 'Kansas City Southern'},
    'LLL':  {'sector': 'Industrials',            'industry': 'Aerospace & Defense',          'name': 'L3 Technologies'},
    'LUK':  {'sector': 'Financials',             'industry': 'Multi-Sector Holdings',        'name': 'Leucadia National'},
    'MON':  {'sector': 'Materials',              'industry': 'Fertilizers & Agri',           'name': 'Monsanto'},
    'MYL':  {'sector': 'Health Care',            'industry': 'Pharmaceuticals',              'name': 'Mylan'},
    'NBL':  {'sector': 'Energy',                 'industry': 'Oil & Gas Exploration',        'name': 'Noble Energy'},
    'NLSN': {'sector': 'Industrials',            'industry': 'Research & Consulting',        'name': 'Nielsen'},
    'PX':   {'sector': 'Materials',              'industry': 'Industrial Gases',             'name': 'Praxair'},
    'RHT':  {'sector': 'Information Technology', 'industry': 'Systems Software',             'name': 'Red Hat'},
    'RTN':  {'sector': 'Industrials',            'industry': 'Aerospace & Defense',          'name': 'Raytheon'},
    'SCG':  {'sector': 'Utilities',              'industry': 'Electric Utilities',           'name': 'SCANA'},
    'SNI':  {'sector': 'Communication Services', 'industry': 'Broadcasting',                 'name': 'Scripps Networks'},
    'SRCL': {'sector': 'Industrials',            'industry': 'Environmental Services',       'name': 'Stericycle'},
    'SYMC': {'sector': 'Information Technology', 'industry': 'Systems Software',             'name': 'Symantec'},
    'TIF':  {'sector': 'Consumer Discretionary', 'industry': 'Specialty Retail',             'name': 'Tiffany'},
    'TMK':  {'sector': 'Financials',             'industry': 'Life & Health Insurance',      'name': 'Torchmark'},
    'TSS':  {'sector': 'Information Technology', 'industry': 'Data Processing',              'name': 'Total System Services'},
    'TWX':  {'sector': 'Communication Services', 'industry': 'Movies & Entertainment',       'name': 'Time Warner'},
    'UTX':  {'sector': 'Industrials',            'industry': 'Aerospace & Defense',          'name': 'United Technologies'},
    'VAR':  {'sector': 'Health Care',            'industry': 'Health Care Equipment',        'name': 'Varian Medical'},
    'VIAB': {'sector': 'Communication Services', 'industry': 'Broadcasting',                 'name': 'Viacom B'},
    'WLTW': {'sector': 'Financials',             'industry': 'Insurance Brokers',            'name': 'Willis Towers Watson'},
    'WYN':  {'sector': 'Consumer Discretionary', 'industry': 'Hotels & Resorts',             'name': 'Wyndham'},
    'XEC':  {'sector': 'Energy',                 'industry': 'Oil & Gas Exploration',        'name': 'Cimarex Energy'},
    'XL':   {'sector': 'Financials',             'industry': 'Property & Casualty',          'name': 'XL Group'},
    'XLNX': {'sector': 'Information Technology', 'industry': 'Semiconductors',               'name': 'Xilinx'},
    'ABC':  {'sector': 'Health Care',            'industry': 'Health Care Distributors',     'name': 'AmerisourceBergen'},
    'ADS':  {'sector': 'Information Technology', 'industry': 'Data Processing',              'name': 'Alliance Data'},
    'ARNC': {'sector': 'Materials',              'industry': 'Aluminum',                     'name': 'Arconic'},
    'CBG':  {'sector': 'Real Estate',            'industry': 'Real Estate Services',         'name': 'CBRE Group'},
    'COG':  {'sector': 'Energy',                 'industry': 'Oil & Gas Exploration',        'name': 'Cabot Oil & Gas'},
    'COH':  {'sector': 'Consumer Discretionary', 'industry': 'Apparel',                      'name': 'Coach'},
    'CXO':  {'sector': 'Energy',                 'industry': 'Oil & Gas Exploration',        'name': 'Concho Resources'},
    'DFS':  {'sector': 'Financials',             'industry': 'Consumer Finance',             'name': 'Discover Financial'},
    'DRE':  {'sector': 'Real Estate',            'industry': 'Industrial REITs',             'name': 'Duke Realty'},
    'FBHS': {'sector': 'Industrials',            'industry': 'Building Products',            'name': 'Fortune Brands'},
    'FL':   {'sector': 'Consumer Discretionary', 'industry': 'Specialty Retail',             'name': 'Foot Locker'},
    'FLIR': {'sector': 'Industrials',            'industry': 'Electronic Equipment',         'name': 'FLIR Systems'},
    'GPS':  {'sector': 'Consumer Discretionary', 'industry': 'Apparel Retail',               'name': 'Gap'},
    'HBI':  {'sector': 'Consumer Discretionary', 'industry': 'Apparel',                      'name': 'Hanesbrands'},
    'HES':  {'sector': 'Energy',                 'industry': 'Oil & Gas Exploration',        'name': 'Hess'},
    'HRS':  {'sector': 'Industrials',            'industry': 'Electronic Equipment',         'name': 'Harris Corp'},
    'IPG':  {'sector': 'Communication Services', 'industry': 'Advertising',                  'name': 'Interpublic Group'},
    'JWN':  {'sector': 'Consumer Discretionary', 'industry': 'Department Stores',            'name': 'Nordstrom'},
    'K':    {'sector': 'Consumer Staples',       'industry': 'Packaged Foods',               'name': 'Kellogg'},
    'MMC':  {'sector': 'Financials',             'industry': 'Insurance Brokers',            'name': 'Marsh & McLennan'},
    'MRO':  {'sector': 'Energy',                 'industry': 'Oil & Gas Exploration',        'name': 'Marathon Oil'},
    'PBCT': {'sector': 'Financials',             'industry': 'Regional Banks',               'name': 'Peoples United'},
    'PDCO': {'sector': 'Health Care',            'industry': 'Health Care Distributors',     'name': 'Patterson'},
    'PKI':  {'sector': 'Health Care',            'industry': 'Health Care Equipment',        'name': 'PerkinElmer'},
    'RE':   {'sector': 'Financials',             'industry': 'Reinsurance',                  'name': 'Everest Re'},
    'SEE':  {'sector': 'Materials',              'industry': 'Metal & Glass Containers',     'name': 'Sealed Air'},
    'VIAB': {'sector': 'Communication Services', 'industry': 'Movies & Entertainment',       'name': 'Viacom'},
    'WBA':  {'sector': 'Consumer Staples',       'industry': 'Drug Retail',                  'name': 'Walgreens Boots'},
    'WRK':  {'sector': 'Materials',              'industry': 'Paper Packaging',              'name': 'WestRock'},
    'CMA':  {'sector': 'Financials',             'industry': 'Diversified Banks',            'name': 'Comerica'},
    'ANSS': {'sector': 'Information Technology', 'industry': 'Application Software',         'name': 'ANSYS'},
    'BLL':  {'sector': 'Materials',              'industry': 'Metal & Glass Containers',     'name': 'Ball Corp'},
}

print("Wikipedia에서 현재 S&P 500 섹터 수집 중...")
wiki_data = fetch_wiki()
print(f"Wikipedia에서 {len(wiki_data)}개 수집")

# 기존 파일 로드
existing = {}
if OUT.exists():
    try:
        existing = json.loads(OUT.read_text())
    except:
        pass

# 병합: Wikipedia → KNOWN → 기존 순서
result = {}

# 전체 티커 목록
import sqlite3
conn = sqlite3.connect('/Users/choids/Documents/Projects/Stock/Virtual StockMarket/db/merged_stocks.db')
tickers = [r[0] for r in conn.execute("SELECT ticker FROM tickers_list ORDER BY ticker").fetchall()]
conn.close()

for ticker in tickers:
    if ticker in wiki_data and wiki_data[ticker]['sector']:
        result[ticker] = wiki_data[ticker]
    elif ticker in KNOWN:
        result[ticker] = KNOWN[ticker]
    elif ticker in existing and existing[ticker]['sector'] != 'Unknown':
        result[ticker] = existing[ticker]
    else:
        result[ticker] = {'sector': 'Unknown', 'industry': '', 'name': ticker}

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))

from collections import Counter
sectors = Counter(v['sector'] for v in result.values())
print(f"\n완료: {len(result)}개 종목")
for s, c in sectors.most_common():
    print(f"  {s}: {c}개")
