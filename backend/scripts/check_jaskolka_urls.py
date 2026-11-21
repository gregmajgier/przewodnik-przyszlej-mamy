"""Ręczna weryfikacja: czy wszystkie adresy z app/data/jaskolka.json odpowiadają (HTTP 200).

Uruchom: .venv/bin/python scripts/check_jaskolka_urls.py
Nie jest częścią testów (wymaga internetu).
"""

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "app" / "data" / "jaskolka.json"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "pl"}


def check(url: str) -> tuple[str, str]:
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30)
        return url, str(r.status)
    except Exception as e:  # noqa: BLE001
        return url, f"BŁĄD {str(e)[:60]}"


def main() -> None:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    urls = {f["url"] for f in d["foundations"]}
    urls |= {i["source_url"] for s in d["situations"] for i in s["checklist"]}
    with ThreadPoolExecutor(8) as ex:
        for url, status in ex.map(check, sorted(urls)):
            print(status, url)


if __name__ == "__main__":
    main()
