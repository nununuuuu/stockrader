import io
import json
import math
import sys
from collections import Counter

import pandas as pd
import requests
import yfinance as yf


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}


def load_valuechain_map(path="valuechain.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f).get("map", {})
    except Exception:
        return {}

    result = {}
    for code, paths in raw.items():
        keys = []
        labels = []
        for item in paths:
            main = str(item.get("main", "其他")).strip() or "其他"
            parts = [p.strip() for p in str(item.get("path", "")).split(">") if p.strip()]
            level2 = parts[1] if len(parts) >= 2 else main
            key = f"{main}::{level2}"
            keys.append(key)
            labels.append(level2)
        result[str(code)] = {
            "keys": sorted(set(keys)),
            "labels": sorted(set(labels)),
        }
    return result


def load_tickers():
    tickers = []
    sources = [
        ("上市", ".TW", "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"),
        ("上櫃", ".TWO", "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"),
    ]
    for market, suffix, url in sources:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.content.decode("utf-8-sig")))
        code_col = next(c for c in df.columns if "代號" in c)
        name_col = next(c for c in df.columns if "名稱" in c)
        for _, row in df.iterrows():
            code = str(row[code_col]).strip()
            if code.endswith(".0"):
                code = code[:-2]
            if code.isdigit() and len(code) == 4:
                tickers.append({
                    "symbol": f"{code}{suffix}",
                    "code": code,
                    "name": str(row[name_col]).strip(),
                    "market": market,
                })
    return tickers


def add_indicators(df):
    df = df.copy().dropna()
    df["sma5"] = df["Close"].rolling(5).mean()
    df["sma20"] = df["Close"].rolling(20).mean()
    df["sma60"] = df["Close"].rolling(60).mean()
    std20 = df["Close"].rolling(20).std()
    df["bb_up"] = df["sma20"] + 2 * std20
    df["bb_low"] = df["sma20"] - 2 * std20
    df["bb_bw"] = (df["bb_up"] - df["bb_low"]) / (df["sma20"] + 1e-9)
    df["vol20"] = df["Volume"].rolling(20).mean()
    return df


def score_technical(meta, raw, valuechain_map):
    if raw is None or raw.empty or len(raw.dropna()) < 90:
        return None

    df = add_indicators(raw)
    if len(df) < 90:
        return None

    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    close = float(today["Close"])
    prev_close = float(yesterday["Close"])
    required = [close, prev_close, today["sma20"], today["sma60"], today["vol20"]]
    if not all(math.isfinite(x) for x in required):
        return None
    if today["Volume"] < 300_000 or df["Volume"].tail(10).mean() < 300_000:
        return None

    pct = (close / prev_close - 1) * 100
    vol_ratio = float(today["Volume"] / (today["vol20"] + 1e-9))
    high5 = float(df["High"].iloc[-6:-1].max())
    high20 = float(df["High"].iloc[-21:-1].max())
    high60 = float(df["High"].iloc[-61:-1].max())
    low20 = float(df["Low"].iloc[-21:-1].min())
    recent_std = float(df["Close"].tail(10).std())
    prior_std = float(df["Close"].iloc[-40:-10].std())
    low_rising = float(df["Low"].tail(5).min()) > float(df["Low"].iloc[-15:-5].min())
    above_ma = close > today["sma20"] and today["sma20"] >= today["sma60"] * 0.96
    dist_sma20 = (close / (today["sma20"] + 1e-9) - 1) * 100
    risk = (close / max(low20, 1e-9) - 1) * 100

    # 不追高模式：先排掉已經噴太遠的標的。
    if pct >= 7.0 or dist_sma20 > 18 or risk > 28:
        return None

    strategies = []
    reasons = []
    technical_flags = []

    if close > today["bb_up"] and 1.15 <= vol_ratio <= 4.8:
        strategies.append("布林突破基礎版")
        reasons.append("收盤突破布林上軌且量能放大")
        technical_flags.append("breakout")

    if close > today["bb_up"] and today["bb_bw"] < 0.16 and 1.1 <= vol_ratio <= 4.5:
        strategies.append("布林突破 SBA")
        reasons.append("布林帶偏窄後向上突破")
        technical_flags.append("squeeze")

    if prior_std > 0 and recent_std < prior_std * 0.70 and close > high5 and above_ma and pct <= 5.5:
        strategies.append("VCP 收斂突破")
        reasons.append("近 10 日波動收斂並突破 5 日高")
        technical_flags.append("vcp")

    if close > high20 and 1.05 <= vol_ratio <= 4.0 and above_ma and pct <= 5.5:
        strategies.append("形態學標準版")
        reasons.append("站上短期平台高點且均線轉強")
        technical_flags.append("pattern")

    if close > high60 and 1.15 <= vol_ratio <= 4.0 and pct <= 6.0:
        strategies.append("形態學進階版")
        reasons.append("突破 60 日壓力區")
        technical_flags.append("pattern_plus")

    # 注意：族群連動先不在這裡直接成立，等全部股票掃完後用 valuechain 群聚數判斷。
    if low_rising and close > high5 and 1.1 <= vol_ratio <= 4.5 and 0.5 <= pct <= 6.5:
        technical_flags.append("group_candidate")

    if not strategies and "group_candidate" not in technical_flags:
        return None

    vc_info = valuechain_map.get(meta["code"], {"keys": [], "labels": []})
    score = (
        len(strategies) * 20
        + min(vol_ratio * 10, 35)
        + min(max(pct, 0) * 2, 16)
        + (10 if low_rising else 0)
        - min(max(risk - 15, 0), 28)
        - min(max(dist_sma20 - 10, 0), 18)
    )

    return {
        "code": meta["code"],
        "name": meta["name"],
        "market": meta["market"],
        "date": str(df.index[-1].date()),
        "price": round(close, 2),
        "change_pct": round(pct, 2),
        "volume_ratio": round(vol_ratio, 2),
        "dist_sma20": round(dist_sma20, 2),
        "risk_from_20d_low": round(risk, 2),
        "strategies": strategies,
        "reasons": reasons,
        "technical_flags": technical_flags,
        "vc_keys": vc_info["keys"],
        "vc_labels": vc_info["labels"],
        "score": round(score, 1),
    }


def apply_group_strategies(results):
    group_counts = Counter()
    group_breakout_counts = Counter()

    for item in results:
        if "group_candidate" not in item["technical_flags"]:
            continue
        for key in item["vc_keys"]:
            group_counts[key] += 1
            if any(flag in item["technical_flags"] for flag in ["breakout", "pattern", "pattern_plus"]):
                group_breakout_counts[key] += 1

    filtered = []
    for item in results:
        best_key = ""
        best_count = 0
        for key in item["vc_keys"]:
            count = group_counts[key]
            if count > best_count:
                best_key = key
                best_count = count

        if "group_candidate" in item["technical_flags"] and best_count >= 3:
            label = best_key.split("::")[-1] if best_key else "同產業鏈"
            if group_breakout_counts[best_key] >= 2 and item["change_pct"] >= 2.0:
                item["strategies"].append("族群連動新版")
                item["reasons"].append(f"{label} 同產業鏈 {best_count} 檔同步轉強，且至少 2 檔突破")
                item["score"] += 28 + best_count * 2
            else:
                item["strategies"].append("族群連動第一版")
                item["reasons"].append(f"{label} 同產業鏈 {best_count} 檔同步轉強")
                item["score"] += 18 + best_count
            item["group_key"] = best_key
            item["group_count"] = best_count

        if item["strategies"]:
            priority = ["族群連動新版", "族群連動第一版", "VCP 收斂突破", "形態學進階版", "形態學標準版", "布林突破 SBA", "布林突破基礎版"]
            item["primary_strategy"] = next((s for s in priority if s in item["strategies"]), item["strategies"][0])
            item["score"] = round(item["score"], 1)
            filtered.append(item)

    filtered.sort(key=lambda x: x["score"], reverse=True)
    return filtered


def main():
    valuechain_map = load_valuechain_map()
    tickers = load_tickers()
    raw_results = []
    batch_size = 100

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        symbols = [x["symbol"] for x in batch]
        data = yf.download(
            symbols,
            period="6mo",
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=False,
        )
        for meta in batch:
            try:
                raw = data[meta["symbol"]] if len(symbols) > 1 else data
                hit = score_technical(meta, raw, valuechain_map)
                if hit:
                    raw_results.append(hit)
            except Exception:
                continue

    results = apply_group_strategies(raw_results)
    print(json.dumps({
        "count": len(results),
        "results": results[:40],
        "note": "原作者風格近似版；族群策略已接 valuechain.json，用同產業鏈同步轉強判斷。興櫃未納入此快掃。",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
