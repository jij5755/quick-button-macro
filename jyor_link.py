"""JYOR(부속 인식 앱) 품목 연동 — 버튼 아래에 연결된 품목의 '구경 · 가격'을 항상 표시(2026-10-05).

버튼 데이터의 "erp_code"(JYOR 품목번호 = 경영박사 내부코드)로 JYOR DB(`pipefitter.db`)를 **읽기만** 한다.
가격 규칙은 JYOR와 같다: 행 소비가(sale_price) → 가격 캐시(price_cache, 바코드) → 매핑 단가(unit_price).
DB 경로는 실행 폴더의 `jyor_link.json` {"db_path": "..."}가 있으면 그것, 없으면 메인 PC 기본 경로.
DB가 없거나 잠겨 있으면 조용히 빈 결과(버튼 표시만 비고, 매크로는 그대로 동작).
"""
import json
import os
import sqlite3

DEFAULT_DB_PATH = r"C:\Users\JY1\jYOR\JYObjectRecognition\pipefitter.db"
CONFIG_FILE = "jyor_link.json"
REFRESH_MS = 30_000          # 30초마다 다시 읽음(JYOR에서 가격·품목을 바꾸면 따라옴)


def db_path() -> str:
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            p = (json.load(f) or {}).get("db_path")
            if p:
                return str(p)
    except (OSError, ValueError):
        pass
    return DEFAULT_DB_PATH


def lookup(codes, path=None) -> dict:
    """{품목번호: {"name", "caliber", "price"}} — 없는 번호는 빠진다. 실패하면 {}."""
    codes = sorted({str(c).strip() for c in codes or () if str(c or "").strip()})
    path = path or db_path()
    if not codes or not os.path.exists(path):
        return {}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return {}
    try:
        conn.row_factory = sqlite3.Row
        q = ",".join("?" * len(codes))
        rows = conn.execute(f"SELECT erp_code, barcode, name, caliber, sale_price, unit_price "
                            f"FROM mapping WHERE erp_code IN ({q})", codes).fetchall()
        cache = {}
        bcs = sorted({(r["barcode"] or "").strip() for r in rows if (r["barcode"] or "").strip()})
        if bcs:
            try:
                q2 = ",".join("?" * len(bcs))
                cache = {b: p for b, p in conn.execute(
                    f"SELECT barcode, price FROM price_cache WHERE barcode IN ({q2})", bcs)}
            except sqlite3.Error:
                cache = {}
        out = {}
        for r in rows:
            price = _positive(r["sale_price"]) or _positive(cache.get((r["barcode"] or "").strip())) \
                or _positive(r["unit_price"])
            out[str(r["erp_code"]).strip()] = {"name": r["name"] or "", "caliber": r["caliber"] or "",
                                               "price": price}
        return out
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def _positive(v):
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def info_text(info) -> str:
    """버튼 아래 한 줄: '15A  ₩4,900' (값 없는 칸은 빼고, 둘 다 없으면 '')."""
    if not info:
        return ""
    parts = []
    if info.get("caliber"):
        parts.append(str(info["caliber"]))
    if info.get("price"):
        parts.append(f"₩{int(info['price']):,}")
    return "  ".join(parts)
