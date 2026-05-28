from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import re
import threading
import yfinance as yf
import json
import io
import csv
import os
import codecs
from scrapling import Fetcher
import radar_select 

# --- 步驟 0：修補編碼與環境配置 ---
try:
    codecs.lookup('ms950')
except LookupError:
    codecs.register(lambda name: codecs.lookup('cp950') if name.lower() == 'ms950' else None)

app = Flask(__name__)
CORS(app)

RAPID_API_KEY = "3eadd849edmshc5413e91ec37d73p1a0159jsn40bd306147ac"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://tw.stock.yahoo.com/'
}

# --- 全域狀態變數 ---
GLOBAL_STOCK_DB = {}   
GLOBAL_DATA_CACHE = None  
RADAR_RESULTS = None    
RADAR_LAST_DATE = ""      
IS_RADAR_RUNNING = False  
RADAR_LOCK = threading.Lock()
INIT_PROGRESS = {
    "percentage": 0, "status": "IDLE", "current_item": "", "total_tasks": 0, "current_task_idx": 0, "is_done": False
}
MAP_FILE = "industry_map.json"

# --- 1. 核心抓取工具 ---

def clean_num(val):
    if val is None: return 0.0
    try: return float(str(val).replace('"', '').replace(',', '').replace('=', '').strip())
    except: return 0.0

def get_taiex_info(target_date_str):
    """ 抓取加權指數真實價格、均線與量比 """
    try:
        print(f"📡 [抓取] 加權指數 - 目標日期: {target_date_str}")
        twse_url = f"https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={target_date_str}"
        twse_res = requests.get(twse_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10).json()
        if twse_res.get('stat') != 'OK': return None

        latest = twse_res['data'][-1]
        off_price = float(latest[4].replace(',', ''))
        off_diff = float(latest[5].replace(',', ''))
        amounts = [float(r[2].replace(',', '')) / 100000000 for r in twse_res['data']]
        vol_ratio = amounts[-1] / (sum(amounts[-5:]) / 5) if len(amounts) >= 5 else 0.0

        twii = yf.Ticker("^TWII")
        history = twii.history(period="150d")
        fmt_date = pd.to_datetime(f"{target_date_str[:4]}-{target_date_str[4:6]}-{target_date_str[6:]}").tz_localize('Asia/Taipei')
        if fmt_date not in history.index:
            history = pd.concat([history, pd.DataFrame({'Close': [off_price]}, index=[fmt_date])])
        else: history.at[fmt_date, 'Close'] = off_price

        return {
            "price": round(off_price, 2), "diff": round(off_diff, 2),
            "pct": round((off_diff / (off_price - off_diff)) * 100, 2),
            "ma20": round(float(history['Close'].rolling(20).mean().iloc[-1]), 2),
            "ma60": round(float(history['Close'].rolling(60).mean().iloc[-1]), 2),
            "vol_ratio": round(float(vol_ratio), 2),
            "is_above_ma20": bool(off_price > history['Close'].rolling(20).mean().iloc[-1]),
            "is_above_ma60": bool(off_price > history['Close'].rolling(60).mean().iloc[-1])
        }
    except: return None

def get_sentiment_data():
    """ 獲取 CNN 情緒完整歷史與 VIX """
    sentiment = {"now": None, "last": None, "week": None, "month": None, "vix": None, "actual_date": ""}
    try:
        url = "https://fear-and-greed-index.p.rapidapi.com/v1/fgi"
        headers = {"x-rapidapi-key": RAPID_API_KEY, "x-rapidapi-host": "fear-and-greed-index.p.rapidapi.com"}
        res = requests.get(url, headers=headers, timeout=10).json()
        if 'fgi' in res:
            f = res['fgi']
            dt = res.get('lastUpdated', {}).get('humanDate', '')[:10].replace('-', '')
            print(f"📡 [抓取] 市場情緒 - 數據日期: {dt}")
            sentiment.update({
                "now": {"score": int(f['now']['value']), "label": f['now']['valueText'].upper()},
                "last": {"score": int(f['previousClose']['value']), "label": f['previousClose']['valueText'].upper()},
                "week": {"score": int(f['oneWeekAgo']['value']), "label": f['oneWeekAgo']['valueText'].upper()},
                "month": {"score": int(f['oneMonthAgo']['value']), "label": f['oneMonthAgo']['valueText'].upper()},
                "actual_date": dt
            })
        vix = yf.download("^VIX", period="2d", progress=False)
        if not vix.empty: sentiment["vix"] = round(float(vix['Close'].values.flatten()[-1]), 2)
    except: pass
    return sentiment

def get_dashboard_commander():
    """ 🌟 數據指揮官：獲取 Yahoo 結算總額、日期與加權券資比 """
    result = {"date": "", "inst_total": 0.0, "inst_f": 0.0, "inst_t": 0.0, "inst_d": 0.0, "margin_f": 0.0, "margin_s": 0, "ratio": 0.0, "tse_ratio": 0.0, "otc_ratio": 0.0}
    base = "https://tw.stock.yahoo.com/_td-stock/api/resource/StockServices"
    params = "limit=2;sortBy=-date?bkt=&device=desktop&intl=tw&lang=zh-Hant-TW&region=TW&site=finance&tz=Asia/Taipei"
    try:
        t_tse = requests.get(f"{base}.trades;exchange=TAI;{params}", headers=HEADERS).json()
        t_otc = requests.get(f"{base}.trades;exchange=TWO;{params}", headers=HEADERS).json()
        c_tse = requests.get(f"{base}.twcredits;exchange=TAI;{params}", headers=HEADERS).json()
        c_otc = requests.get(f"{base}.twcredits;exchange=TWO;{params}", headers=HEADERS).json()
        
        idx = 0
        l_tse = t_tse.get('list', [])
        l_c_tse = c_tse.get('credits', {}).get('list', [])
        if len(l_tse) > 1 and clean_num(l_tse[0].get('foreignDiffM')) == 0 and clean_num(l_c_tse[0].get('financingChangeM')) == 0:
            idx = 1
            
        tl_tse, tl_otc = t_tse['list'][idx], t_otc['list'][idx]
        cl_tse, cl_otc = c_tse['credits']['list'][idx], c_otc['credits']['list'][idx]
        
        result["date"] = tl_tse['date'][:10].replace('-', '')
        print(f"📡 [定錨] Yahoo 總額數據日期: {result['date']}")
        
        # 法人加總 (億)
        result["inst_f"] = (clean_num(tl_tse.get('foreignDiffM')) + clean_num(tl_otc.get('foreignDiffM'))) / 100
        result["inst_t"] = (clean_num(tl_tse.get('investmentTrustDiffM')) + clean_num(tl_otc.get('investmentTrustDiffM'))) / 100
        result["inst_d"] = (clean_num(tl_tse.get('dealerDiffM')) + clean_num(tl_otc.get('dealerDiffM'))) / 100
        result["inst_total"] = round(result["inst_f"] + result["inst_t"] + result["inst_d"], 2)
        
        # 融資券加總與加權比率
        result["margin_f"] = round((clean_num(cl_tse.get('financingChangeM')) + clean_num(cl_otc.get('financingChangeM'))) / 100, 2)
        result["margin_s"] = int(clean_num(cl_tse.get('shortChangeVolK')) + clean_num(cl_otc.get('shortChangeVolK')))
        
        tb, ob = clean_num(cl_tse.get('financingTotalM')), clean_num(cl_otc.get('financingTotalM'))
        tr, or_ = clean_num(cl_tse.get('shortFinancingPercent')), clean_num(cl_otc.get('shortFinancingPercent'))
        result["ratio"] = round(((tr * tb) + (or_ * ob)) / (tb + ob), 2) if (tb + ob) > 0 else 0.0
        result["tse_ratio"], result["otc_ratio"] = round(tr, 2), round(or_, 2)
    except Exception as e: print(f"❌ Yahoo Commander Error: {e}")
    return result

def get_precise_summary():
    """ 獲取三大法人合計與定錨日期 """
    res = {"foreign": 0.0, "trust": 0.0, "dealer": 0.0, "total": 0.0, "date": ""}
    base = "https://tw.stock.yahoo.com/_td-stock/api/resource/StockServices.trades"
    params = "bkt=&device=desktop&intl=tw&lang=zh-Hant-TW&region=TW&site=finance&tz=Asia/Taipei"
    try:
        t_res = requests.get(f"{base};exchange=TAI;sortBy=-date;limit=1?{params}", headers=HEADERS).json()
        o_res = requests.get(f"{base};exchange=TWO;sortBy=-date;limit=1?{params}", headers=HEADERS).json()
        if 'list' in t_res and len(t_res['list']) > 0:
            l = t_res['list'][0]
            res["date"] = l['date'][:10].replace('-', '')
            print(f"📡 [定錨] 三大法人 - 最新日期: {res['date']}")
            res["foreign"] = round((clean_num(l.get('foreignDiffM')) + clean_num(o_res['list'][0].get('foreignDiffM'))) / 100, 2)
            res["trust"] = round((clean_num(l.get('investmentTrustDiffM')) + clean_num(o_res['list'][0].get('investmentTrustDiffM'))) / 100, 2)
            res["dealer"] = round((clean_num(l.get('dealerDiffM')) + clean_num(o_res['list'][0].get('dealerDiffM'))) / 100, 2)
            res["total"] = round(res["foreign"] + res["trust"] + res["dealer"], 2)
    except: pass
    return res

def get_official_margin_details(d_twse):
    """ 抓取 1269 檔以上官方明細 """
    stock_map = {}
    session = requests.Session()
    try:
        # 上市 CSV
        det_url = f"https://www.twse.com.tw/exchangeReport/MI_MARGN?response=csv&date={d_twse}&selectType=ALL"
        session.get("https://www.twse.com.tw/zh/marginTrading/MI_MARGN.html", headers=HEADERS, timeout=5)
        d_resp = session.get(det_url, headers=HEADERS, timeout=10)
        d_resp.encoding = 'cp950'
        for row in csv.reader(io.StringIO(d_resp.text)):
            if len(row) < 13: continue
            sid = row[0].replace('"', '').replace('=', '').strip()
            if re.match(r'^\d', sid):
                stock_map[sid] = {"f_change": clean_num(row[6])-clean_num(row[5]), "s_change": clean_num(row[12])-clean_num(row[11])}
        # 上櫃 OpenAPI
        otc_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance"
        o_resp = requests.get(otc_url, headers=HEADERS, timeout=10)
        o_text = o_resp.content.decode('cp950', errors='ignore') if o_resp.status_code == 200 else ""
        if o_text.strip().startswith('['):
            for item in json.loads(o_text):
                sid = str(item.get('SecuritiesCompanyCode', '')).strip()
                stock_map[sid] = {"f_change": clean_num(item.get('MarginPurchaseBalance')) - clean_num(item.get('MarginPurchaseBalancePreviousDay')), "s_change": clean_num(item.get('ShortSaleBalance')) - clean_num(item.get('ShortSaleBalancePreviousDay'))}
    except: pass
    return stock_map

# --- 2. 產業地圖邏輯 (持久化) ---

def scrape_all_yahoo_classes():
    global GLOBAL_STOCK_DB, INIT_PROGRESS
    
    if os.path.exists(MAP_FILE):
        print(f"📁 發現本地產業地圖，正在載入...")
        try:
            with open(MAP_FILE, 'r', encoding='utf-8') as f:
                GLOBAL_STOCK_DB = json.load(f)
            INIT_PROGRESS.update({"percentage": 100, "is_done": True})
            
            # 🌟 關鍵修正：地圖讀完後，去跑「主動同步」
            threading.Thread(target=initial_data_sync, daemon=True).start()
            return
        except: print(f"❌ 讀取快取失敗")

    INIT_PROGRESS["status"] = "SCANNING"
    targets = [
        {"title": "電子產業", "weight_key": "electronics"},
        {"title": "概念股", "weight_key": "concepts"},
        {"title": "上市類股", "weight_key": "basic"},
        {"title": "上櫃類股", "weight_key": "basic"},
        {"title": "集團股", "weight_key": "group"}
    ]
    try:
        page = Fetcher.get("https://tw.stock.yahoo.com/class/")
        all_h2 = page.css('h2')
        category_links = []
        for t in targets:
            target_h2 = next((h2 for h2 in all_h2 if t['title'] in h2.text), None)
            if not target_h2: continue
            parent_div = target_h2.parent.parent
            links = parent_div.css('ul a[href*="class-quote?"]')
            for l in links:
                category_links.append({"url": "https://tw.stock.yahoo.com" + l.attrib['href'], "name": l.text.strip(), "weight_key": t['weight_key']})
        
        total = len(category_links)
        INIT_PROGRESS["total_tasks"] = total
        for idx, item in enumerate(category_links):
            INIT_PROGRESS["current_item"] = item["name"]
            INIT_PROGRESS["percentage"] = int((idx / total) * 100)
            try:
                cat_page = Fetcher.get(item["url"])
                ids = re.findall(r'/quote/(\d{4})', cat_page.text)
                for sid in list(set(ids)):
                    if sid not in GLOBAL_STOCK_DB: GLOBAL_STOCK_DB[sid] = {"electronics": "", "concepts": "", "group": "", "basic": ""}
                    GLOBAL_STOCK_DB[sid][item["weight_key"]] = str(item["name"])
            except: continue
        
        with open(MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(GLOBAL_STOCK_DB, f, ensure_ascii=False, indent=4)
        INIT_PROGRESS["is_done"] = True
        print("✅ 產業地圖收錄完成。啟動主動同步任務...")
        threading.Thread(target=initial_data_sync, daemon=True).start()
    except Exception as e: print(f"地圖掃描異常: {e}")

def run_radar_background(chip_map=None, top_sectors=None, industry_db=None, current_date=""):
    global RADAR_RESULTS, IS_RADAR_RUNNING, RADAR_LAST_DATE
    
    with RADAR_LOCK:
        if IS_RADAR_RUNNING: return
        IS_RADAR_RUNNING = True

    try:
        # 確保即便沒傳參數（初次啟動），內部邏輯也能運作
        cm = chip_map if chip_map is not None else {}
        ts = top_sectors if top_sectors is not None else []
        db = industry_db if industry_db is not None else GLOBAL_STOCK_DB
        
        print(f"🚀 [雷達啟動] 正在掃描基準日: {current_date or '最新'} | 籌碼對齊: {'YES' if chip_map else 'NO'}")
        
        # 執行掃描
        results = radar_select.run_radar_scan(cm, ts, db)
        
        RADAR_RESULTS = results
        RADAR_LAST_DATE = current_date
        print("✅ [雷達完成] 結果已更新。")
    except Exception as e:
        print(f"❌ [雷達異常]: {e}")
    finally:
        with RADAR_LOCK: IS_RADAR_RUNNING = False

def initial_data_sync():
    """ 程式啟動後，立刻抓取最新籌碼並啟動雷達 """
    print("🚀 [系統初始化] 正在定錨最新日期並同步籌碼...")
    board = get_dashboard_commander()
    anchor_date = board["date"]
    
    if anchor_date:
        try:
            margin_map = get_official_margin_details(anchor_date)
            print(f"📡 已取得 {anchor_date} 基礎籌碼，啟動後台雷達...")
            run_radar_background(chip_map={}, top_sectors=[], current_date=anchor_date)
        except:
            run_radar_background() # 萬一 API 沒出，跑純技術版保底
    else:
        run_radar_background() # 萬一連不上 Yahoo，跑純技術版保底

# --- 3. 核心 API 路由 ---
@app.route('/api/init_progress')
def get_init_progress(): return jsonify(INIT_PROGRESS)

@app.route('/api/data')
def get_main_data():
    global GLOBAL_DATA_CACHE, RADAR_RESULTS, RADAR_LAST_DATE
    if not INIT_PROGRESS["is_done"]: return jsonify({"status": "loading"}), 202

    # A. 執行指揮官定錨
    board = get_dashboard_commander()
    anchor_date = board["date"]
    if not anchor_date or int(anchor_date) < 20240101: anchor_date = datetime.now().strftime("%Y%m%d")

    # B. 快取檢查
    if GLOBAL_DATA_CACHE and GLOBAL_DATA_CACHE["date"] == anchor_date: return jsonify(GLOBAL_DATA_CACHE)

    start_dt = datetime.strptime(anchor_date, "%Y%m%d")
    for i in range(5):
        d_twse = (start_dt - timedelta(days=i)).strftime("%Y%m%d")
        d_tpex = f"{int(d_twse[:4])-1911}/{d_twse[4:6]}/{d_twse[6:]}"
        print(f"🔍 [同步] 排行資料對齊嘗試: {d_twse}")
        
        try:
            # 1. 抓取上市排行
            tse_url = f"https://www.twse.com.tw/fund/T86?response=json&date={d_twse}&selectType=ALL"
            tse_res = requests.get(tse_url, headers=HEADERS, timeout=10).json()
            if tse_res.get('stat') != 'OK' or not tse_res.get('data'): continue
            
            # 2. 抓取同步數據
            taiex = get_taiex_info(d_twse)
            sentiment = get_sentiment_data()
            margin_map = get_official_margin_details(d_twse)

            stale_warnings = []
            if sentiment["actual_date"] and sentiment["actual_date"] != d_twse: stale_warnings.append(f"情緒({sentiment['actual_date']})")
            if board["date"] != d_twse: stale_warnings.append(f"資券總額({board['date']})")

            # 3. 🌟 解決上櫃排行消失問題
            df_tse = pd.DataFrame(tse_res['data'])
            df_tse = pd.DataFrame({'stock_id': df_tse.iloc[:, 0].str.strip(), 'stock_name': df_tse.iloc[:, 1].str.strip(), 'foreign': df_tse.iloc[:, 4].apply(clean_num)/1000, 'trust': df_tse.iloc[:, 10].apply(clean_num)/1000, 'dealer': df_tse.iloc[:, 11].apply(clean_num)/1000, 'total': df_tse.iloc[:, 18].apply(clean_num)/1000, 'market': 'tse'})
            
            # 修正：精準對應櫃買中心 JSON
            otc_url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&d={d_tpex}"
            otc_json = requests.get(otc_url, headers=HEADERS).json()
            otc_rows = otc_json.get('aaData', []) or otc_json.get('data', []) or (otc_json.get('tables', [{}])[0].get('data', []) if 'tables' in otc_json else [])
            
            df_otc = pd.DataFrame({'stock_id': [str(r[0]).strip() for r in otc_rows], 'stock_name': [str(r[1]).strip() for r in otc_rows], 'foreign': [clean_num(r[4])/1000 for r in otc_rows], 'trust': [clean_num(r[13])/1000 for r in otc_rows], 'dealer': [clean_num(r[22])/1000 for r in otc_rows], 'total': [clean_num(r[23])/1000 for r in otc_rows], 'market': 'otc'})

            df = pd.concat([df_tse, df_otc], ignore_index=True).fillna(0)
            df['raw_id'] = df['stock_id'].astype(str).str.strip()
            df['is_etf'] = df['raw_id'].apply(lambda x: len(x) != 4 or x.startswith('00'))
            df['stock_id'] = df['raw_id'].apply(lambda x: "".join(filter(str.isdigit, x)))
            df['margin'] = df['stock_id'].apply(lambda x: margin_map.get(x, {"f_change":0, "s_change":0}))
            
            def get_stock_profile(sid):
                tags = GLOBAL_STOCK_DB.get(sid, {"electronics":"", "concepts":"", "group":"", "basic":""})
                clean_tags = {k: str(v).strip() for k, v in tags.items()}
                primary = (clean_tags.get('electronics') or clean_tags.get('concepts') or clean_tags.get('group') or clean_tags.get('basic') or "一般個股")
                return primary, clean_tags
            
            # 注入標籤與資券
            profiles = df['stock_id'].apply(get_stock_profile)
            df['category'], df['all_tags'] = [p[0] for p in profiles], [p[1] for p in profiles]
            df.loc[df['is_etf'], 'category'] = 'ETF/指數標的'
            df['margin'] = df['stock_id'].apply(lambda x: margin_map.get(x, {"f_change":0, "s_change":0}))

            # 4. 決策維度
            up_stocks, down_stocks = len(df[(df['total'] > 0) & (~df['is_etf'])]), len(df[(df['total'] < 0) & (~df['is_etf'])])
            breadth = {"up": up_stocks, "down": down_stocks}
            signals = {
                "inst": "買盤力道強勁" if board["inst_total"] > 0 else "買盤尚未回流",
                "margin": "籌碼換手乾淨" if board["margin_f"] < 0 and board["inst_total"] > 0 else "情緒過熱" if board["margin_f"] > 50 else "⚠️ 散戶接盤" if board["margin_f"] > 0 and board["inst_total"] < 0 else "💤 交投平淡"
            }

            # 5. 族群統計 (非互斥)
            sector_dict = {}
            for _, row in df[~df['is_etf']].iterrows():
                for t_name in set(v for v in row['all_tags'].values() if v and v != "一般個股"):
                    if t_name not in sector_dict: sector_dict[t_name] = {"total":0.0, "f":0.0, "t":0.0, "d":0.0, "comps":[]}
                    s = sector_dict[t_name]
                    s["total"] += float(row['total']); s["f"] += float(row['foreign']); s["t"] += float(row['trust']); s["d"] += float(row['dealer'])
                    s["comps"].append({"stock_id": row['stock_id'], "stock_name": row['stock_name'], "total": row['total']})

            sector_list = []
            for name, s in sector_dict.items():
                if abs(s["total"]) < 1: continue
                tag_type = next((k for k, v in GLOBAL_STOCK_DB.get(s["comps"][0]["stock_id"], {}).items() if v == name), "basic")
                sector_list.append({"name": name, "tag_type": tag_type, "total": round(s["total"],0), "foreign": round(s["f"],0), "trust": round(s["t"],0), "dealer": round(s["d"],0), "top_components": sorted(s["comps"], key=lambda x: x['total'], reverse=True)[:5]})

            # 數據洗淨
            clean_records = json.loads(df.to_json(orient='records'))
            def gen_rank(c):
                t, o = [r for r in clean_records if r['market']=='tse'], [r for r in clean_records if r['market']=='otc']
                return { "tse_b": sorted([r for r in t if r[c]>0], key=lambda x:x[c], reverse=True)[:500], "tse_s": sorted([r for r in t if r[c]<0], key=lambda x:x[c])[:500], "otc_b": sorted([r for r in o if r[c]>0], key=lambda x:x[c], reverse=True)[:500], "otc_s": sorted([r for r in o if r[c]<0], key=lambda x:x[c])[:500] }

            # 🌟 最終快取封裝
            top_sectors_names = [s['name'] for s in sorted([s for s in sector_list if s['total'] > 0], key=lambda x: x['total'], reverse=True)[:10]]
            chip_map = {str(r['stock_id']): {"f": r['foreign'], "t": r['trust'], "d": r['dealer']} for _, r in df.iterrows()}
            
            GLOBAL_DATA_CACHE = {
                "date": str(d_twse), "taiex": taiex, "sentiment": sentiment, 
                "summary": {"foreign": board["inst_f"], "trust": board["inst_t"], "dealer": board["inst_d"], "total": board["inst_total"]},
                "margin": {"financing": board["margin_f"], "short_selling": board["margin_s"], "ratio": board["ratio"], "tse_ratio": board["tse_ratio"], "otc_ratio": board["otc_ratio"]},
                "sectors": { "buy": sorted([s for s in sector_list if s['total']>0], key=lambda x:x['total'], reverse=True)[:15], "sell": sorted([s for s in sector_list if s['total']<0], key=lambda x:x['total'])[:15] },
                "rankings": { "total": gen_rank('total'), "foreign": gen_rank('foreign'), "trust": gen_rank('trust'), "dealer": gen_rank('dealer') },
                "breadth": breadth, "signals": signals, "stale_warnings": stale_warnings,
                "radar_ingredients": { "chip_map": chip_map, "top_sectors": top_sectors_names, "date": d_twse }
            }
            if not IS_RADAR_RUNNING: threading.Thread(target=run_radar_background, args=(chip_map, top_sectors_names, GLOBAL_STOCK_DB, d_twse), daemon=True).start()
            
            print(f"✅ 全系統資料對齊: {d_twse} (Stale: {stale_warnings})")
            return jsonify(GLOBAL_DATA_CACHE)
        except Exception as e: print(f"❌ 處理錯誤: {e}"); continue
    return jsonify({"error": "No data"}), 404

# --- 輔助路由 ---
@app.route('/api/radar/refresh', methods=['POST'])
def manual_radar_refresh():
    global IS_RADAR_RUNNING, GLOBAL_DATA_CACHE, RADAR_RESULTS
    if IS_RADAR_RUNNING or not GLOBAL_DATA_CACHE: return jsonify({"status": "error"}), 400
    RADAR_RESULTS, radar_select.PROGRESS = None, 0
    ing = GLOBAL_DATA_CACHE["radar_ingredients"]
    threading.Thread(target=run_radar_background, args=(ing["chip_map"], ing["top_sectors"], GLOBAL_STOCK_DB, ing["date"]), daemon=True).start()
    return jsonify({"status": "success"})

@app.route('/api/radar')
def get_radar(): return jsonify(RADAR_RESULTS)

@app.route('/api/radar_progress')
def get_radar_progress(): return jsonify({"progress": getattr(radar_select, 'PROGRESS', 0), "is_running": IS_RADAR_RUNNING})

if __name__ == '__main__':
    threading.Thread(target=scrape_all_yahoo_classes, daemon=True).start()
    app.run(debug=True, port=5000, use_reloader=False)