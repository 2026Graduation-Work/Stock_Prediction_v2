"""GDELT로 삼성전자 뉴스 가져오기 (무료, 키 불필요).

사용법:
    python gdelt_samsung.py                          # 최근 기사
    python gdelt_samsung.py 2026-05-20 2026-05-27     # 기간 지정(시작 끝)

주의:
- GDELT DOC API는 '최근 약 3개월'만 검색돼.
- GDELT는 '5초에 1회' 속도 제한이 있어 → 너무 자주 호출하면 안내 텍스트가 오고,
  이 스크립트는 그 경우 잠시 기다렸다 자동 재시도한다.
"""
import sys
import time

import requests

URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "Mozilla/5.0"}
QUERY = "삼성전자"  # 한글 검색어 → 자연히 한국어 기사 위주

params = {
    "query": QUERY,
    "mode": "ArtList",
    "format": "json",
    "maxrecords": "25",
    "sort": "DateDesc",
}
if len(sys.argv) >= 3:  # 기간 지정 (YYYY-MM-DD YYYY-MM-DD)
    params["startdatetime"] = sys.argv[1].replace("-", "") + "000000"
    params["enddatetime"] = sys.argv[2].replace("-", "") + "235959"


def fetch(tries: int = 4):
    """연결 오류·속도제한 시 6초 간격으로 재시도."""
    for i in range(1, tries + 1):
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"[시도 {i}] 연결 오류({e.__class__.__name__}) → 6초 후 재시도")
            time.sleep(6)
            continue
        text = r.text.strip()
        if "Please limit requests" in text or not text.startswith("{"):
            print(f"[시도 {i}] GDELT 속도제한/비JSON 응답 → 6초 후 재시도")
            time.sleep(6)
            continue
        return r
    return None


r = fetch()
if r is None:
    print("실패: GDELT가 계속 응답하지 않음. 잠시 후 다시 실행해줘.")
    sys.exit(1)

print("status:", r.status_code)
articles = r.json().get("articles", [])
print("기사 수:", len(articles))
for a in articles:
    print(f"{a.get('seendate', '')}  {a.get('title', '')[:70]}  ({a.get('domain', '')})")
