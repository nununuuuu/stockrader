import requests
import json
import time
import os
import random
from datetime import datetime, timedelta
from valuechain import valuechainManager

# 🌟 全新的瀏覽器模擬配置
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'X-Requested-With': 'XMLHttpRequest',
    'Connection': 'keep-alive',
}

HISTORY_FILE = "industry_history.json"
REQUIRED_KEYS = {"net_force", "inst_net", "change"}

def clean_float(val):
    if val is None: return 0.0
    s = str(val).replace(',', '').replace(' ', '').strip()
    if s in ['', '--', '---']: return 0.0
    try: return float(s)
    except: return 0.0

def get_trading_days(count=25):
    days = []
    now = datetime.now()
    curr = now if now.hour >= 18 else now - timedelta(days=1)
    while len(days) < count:
        if curr.weekday() < 5: days.append(curr.strftime("%Y%m%d"))
        curr -= timedelta(days=1)
    return days

def fetch_json_pro(session, url, label, referer):
    """ 深度模擬瀏覽器抓取 JSON """
    # 加上證交所必要的毫秒時間戳記
    timestamp = int(time.time() * 1000)
    final_url = f"{url}&_={timestamp}" if "?" in url else f"{url}?_={timestamp}"
    
    session.headers.update({'Referer': referer})
    
    for i in range(3): # 最多重試 3 次
        try:
            resp = session.get(final_url, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                # 🌟 關鍵：如果資料不存在，休息一下再試一次，因為我們知道這天有開盤
                if data.get('stat') != 'OK' and "沒有符合條件的資料" in str(data.get('stat')):
                    print(f"  ⚠️ {label} 觸發證交所軟封鎖，等待 {15 * (i+1)} 秒後重試...")
                    time.sleep(15 * (i+1))
                    continue
                return data
            else:
                print(f"  ❌ {label} HTTP 錯誤: {resp.status_code}")
        except Exception as e:
            print(f"  ❌ {label} 請求異常: {e}")
        time.sleep(5)
    return None

def backfill():
    if not os.path.exists("industry_map.json"):
        print("❌ 找不到 industry_map.json")
        return

    with open("industry_map.json", "r", encoding="utf-8") as f:
        industry_db = json.load(f)

    mgr = valuechainManager(industry_db)
    target_dates = get_trading_days(30)
    
    # 🌟 建立 Session 並先獲取 Cookie
    session = requests.Session()
    session.headers.update(HEADERS)
    print("🔑 正在獲取證交所連線門票 (Cookie)...")
    try:
        session.get("https://www.twse.com.tw/zh/page/trading/exchange/T86.html", timeout=10)
        time.sleep(2)
    except: pass

    print(f"🚀 啟動【深度模擬回填】...")

    for d_str in target_dates:
        # 完整性檢查
        if d_str in mgr.history_data and mgr.history_data[d_str]:
            day_content = mgr.history_data[d_str]
            sample = next(iter(day_content.values()))
            if REQUIRED_KEYS.issubset(sample.keys()): continue

        print(f"\n[📅 同步日期: {d_str}]")
        try:
            # 1. 上市資料 (T86 & MI_INDEX)
            t_i = fetch_json_pro(session, 
                f"https://www.twse.com.tw/fund/T86?response=json&date={d_str}&selectType=ALL", 
                "上市籌碼", "https://www.twse.com.tw/zh/page/trading/exchange/T86.html")
            
            if not t_i or t_i.get('stat') != 'OK':
                print(f"  ❌ {d_str} 無法通過證交所驗證，跳過。")
                continue

            time.sleep(random.uniform(3, 5))
            t_p = fetch_json_pro(session, 
                f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={d_str}&type=ALLBUT0999", 
                "上市價格", "https://www.twse.com.tw/zh/page/trading/exchange/MI_INDEX.html")

            # 2. 上櫃資料 (保持原狀)
            d_otc = f"{int(d_str[:4])-1911}/{d_str[4:6]}/{d_str[6:]}"
            o_i = session.get(f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&d={d_otc}").json()
            o_p = session.get(f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&d={d_otc}&o=json").json()

            # --- 數據解析與聚合 (同前 logic) ---
            full_inst, full_margin, full_price = {}, {}, {}
            for r in t_i.get('data', []):
                if len(r) > 18: full_inst[str(r[0]).strip()] = clean_float(r[18])
            o_i_data = o_i['tables'][0].get('data', []) if o_i and 'tables' in o_i else []
            for r in o_i_data:
                if len(r) > 23: full_inst[str(r[0]).strip()] = clean_float(r[23])

            #MI_INDEX
            for k in ['data9', 'data8', 'data10', 'data7']:
                if k in t_p:
                    for r in t_p[k]:
                        if len(r) > 10:
                            sid, close, chg_v = str(r[0]).strip(), clean_float(r[8]), clean_float(r[10])
                            if close == 0: continue
                            sign = -1 if 'green' in str(r[9]) or '-' in str(r[9]) else 1
                            full_price[sid] = {"p": close, "c": chg_v * sign}
                    break
            #OTC Price
            o_p_data = o_p['tables'][0].get('data', []) if o_p and 'tables' in o_p else []
            for r in o_p_data:
                if len(r) > 3:
                    full_price[str(r[0]).strip()] = {"p": clean_float(r[2]), "c": clean_float(r[3])}

            daily_snapshot = {}
            count = 0
            for sid, info in full_price.items():
                paths = mgr.valuechain_map.get(sid)
                if not paths or sid not in full_inst: continue
                count += 1
                inst_billion = (full_inst[sid] * info['p']) / 100000000
                prev_close = info['p'] - info['c']
                pct = (info['c'] / prev_close * 100) if prev_close != 0 else 0
                unique_groups = {mgr._valuechain_group_key(p) for p in paths}
                for g in unique_groups:
                    if g not in daily_snapshot: daily_snapshot[g] = {"nf": 0.0, "inst": 0.0, "cs": []}
                    daily_snapshot[g]["nf"] += inst_billion
                    daily_snapshot[g]["inst"] += inst_billion
                    daily_snapshot[g]["cs"].append(pct)

            if daily_snapshot:
                mgr.history_data[d_str] = {
                    k: { "net_force": round(v["nf"], 2), "inst_net": round(v["inst"], 2), "change": round(sum(v["cs"])/len(v["cs"]), 2) } 
                    for k, v in daily_snapshot.items()
                }
                mgr._save_history()
                print(f"  ✅ {d_str} 完成！對齊 {count} 檔個股")
            
            time.sleep(random.randint(12, 18)) # 06/26 被盯上了，休息久一點

        except Exception as e:
            print(f"  ❌ {d_str} 發生錯誤: {e}")
            time.sleep(20)

    print("\n🎉 補齊結束。")

if __name__ == "__main__":
    backfill()
