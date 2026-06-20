"""
이벤트 DB 링크 유효성 검사기
- events.db에서 link_ok가 NULL인 URL들을 배치로 검사
- 결과를 link_ok(1=유효/0=깨짐), link_checked_at에 기록
- 꽤 오래된 뉴스 링크는 깨질 가능성이 높음
"""
import sqlite3, urllib.request, time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "db" / "events.db"
BATCH   = 50       # 한 번에 검사할 수
DELAY   = 0.3      # 요청 간 딜레이


def check_url(url: str, timeout: int = 8) -> int:
    """1=유효, 0=깨짐"""
    if not url:
        return 0
    try:
        req = urllib.request.Request(url, method='HEAD',
                                     headers={'User-Agent': 'Mozilla/5.0 (compatible; LinkChecker/1.0)'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 1 if r.status < 400 else 0
    except Exception:
        try:
            req = urllib.request.Request(url,
                                         headers={'User-Agent': 'Mozilla/5.0 (compatible; LinkChecker/1.0)'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return 1 if r.status < 400 else 0
        except Exception:
            return 0


def main():
    conn = sqlite3.connect(DB_PATH)

    # link_ok가 NULL이고 url이 있는 것 조회
    total_unk = conn.execute(
        "SELECT COUNT(*) FROM events WHERE url IS NOT NULL AND link_ok IS NULL"
    ).fetchone()[0]

    print(f"미확인 링크: {total_unk}건 검사 시작")
    ok_cnt = broken_cnt = 0
    start  = time.time()

    offset = 0
    while True:
        rows = conn.execute(
            "SELECT id, url, date, source FROM events WHERE url IS NOT NULL AND link_ok IS NULL LIMIT ? OFFSET ?",
            (BATCH, offset)
        ).fetchall()
        if not rows:
            break

        for row_id, url, date, source in rows:
            result = check_url(url)
            conn.execute(
                "UPDATE events SET link_ok=?, link_checked_at=? WHERE id=?",
                (result, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), row_id)
            )
            if result:
                ok_cnt += 1
            else:
                broken_cnt += 1
            time.sleep(DELAY)

        conn.commit()
        checked = ok_cnt + broken_cnt
        elapsed = time.time() - start
        eta     = elapsed / checked * (total_unk - checked) if checked else 0
        print(f"  {checked}/{total_unk}  유효:{ok_cnt}  깨짐:{broken_cnt}  ETA:{eta/60:.0f}분")
        offset += BATCH

    conn.close()
    print(f"\n완료: 유효={ok_cnt} 깨짐={broken_cnt}")


if __name__ == '__main__':
    main()
