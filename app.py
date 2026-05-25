from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import re
import threading
import yfinance as yf
import json
import os
import codecs
import csv
import io
import codecs

# 🌟 確保環境已裝：pip install scrapling playwright browserforge
from scrapling import Fetcher

# 🌟 導入選股引擎
import radar_select 

app = Flask(__name__)
CORS(app)

try:
    codecs.lookup('ms950')
except LookupError:
    codecs.register(lambda name: codecs.lookup('cp950') if name.lower() == 'ms950' else None)

app = Flask(__name__)
CORS(app)

# 🌟 妳的 RapidAPI Key
RAPID_API_KEY = "3eadd849edmshc5413e91ec37d73p1a0159jsn40bd306147ac"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 🌟 全域狀態變數與鎖機制 ---
GLOBAL_STOCK_DB = {}   
GLOBAL_DATA_CACHE = None  # 🌟 存放排行資料快取
RADAR_RESULTS = None    
RADAR_LAST_DATE = ""      # 紀錄最後一次成功掃描的日期
IS_RADAR_RUNNING = False  # 雷達是否正在跑
RADAR_LOCK = threading.Lock()

INIT_PROGRESS = {
    "percentage": 0, "status": "IDLE", "current_item": "", "total_tasks": 0, "current_task_idx": 0, "is_done": False
}

MAP_FILE = "industry_map.json"

# --- 1. 產業地圖掃描邏輯 (含本地存檔) ---

def scrape_all_yahoo_classes():
    global GLOBAL_STOCK_DB, INIT_PROGRESS
    
    if os.path.exists(MAP_FILE):
        print(f"📁 發現本地產業地圖 ({MAP_FILE})，正在載入...")
        try:
            with open(MAP_FILE, 'r', encoding='utf-8') as f:
                GLOBAL_STOCK_DB = json.load(f)
            INIT_PROGRESS["percentage"] = 100
            INIT_PROGRESS["is_done"] = True
            threading.Thread(target=run_radar_background, daemon=True).start()
            return
        except: print(f"❌ 讀取快取失敗，重新啟動線上掃描")

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
        print("✅ 產業地圖收錄完成並存檔。啟動雷達...")
        threading.Thread(target=run_radar_background, daemon=True).start()
    except Exception as e: print(f"地圖掃描異常: {e}")

def run_radar_background(chip_map, top_sectors, industry_db, current_date):
    global RADAR_RESULTS, IS_RADAR_RUNNING, RADAR_LAST_DATE
    with RADAR_LOCK:
        if IS_RADAR_RUNNING: return
        IS_RADAR_RUNNING = True
    try:
        RADAR_RESULTS = radar_select.run_radar_scan(chip_map, top_sectors, industry_db)
        RADAR_LAST_DATE = current_date
    finally:
        with RADAR_LOCK: IS_RADAR_RUNNING = False
        
# --- 2. 核心運算邏輯 ---

def clean_num(val):
    if val is None: return 0.0
    try: return float(str(val).replace('"', '').replace(',', '').replace('=', '').strip())
    except: return 0.0

def get_taiex_info(target_date_str=None):
    try:
        query_date = target_date_str or datetime.now().strftime("%Y%m%d")
        twse_url = f"https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={query_date}"
        twse_res = requests.get(twse_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10).json()
        if twse_res.get('stat') != 'OK': return None

        latest = twse_res['data'][-1]
        off_price = float(latest[4].replace(',', ''))
        off_diff = float(latest[5].replace(',', ''))
        amounts = [float(r[2].replace(',', '')) / 100000000 for r in twse_res['data']]
        vol_ratio = amounts[-1] / (sum(amounts[-5:]) / 5) if len(amounts) >= 5 else 0.0

        twii = yf.Ticker("^TWII")
        history = twii.history(period="150d")
        fmt_date = pd.to_datetime(f"{query_date[:4]}-{query_date[4:6]}-{query_date[6:]}").tz_localize('Asia/Taipei')
        if fmt_date not in history.index:
            history = pd.concat([history, pd.DataFrame({'Close': [off_price]}, index=[fmt_date])])
        else: history.at[fmt_date, 'Close'] = off_price

        return {
            "price": round(off_price, 2), "diff": round(off_diff, 2),
            "pct": round((off_diff / history['Close'].iloc[-2]) * 100, 2),
            "ma20": round(float(history['Close'].rolling(20).mean().iloc[-1]), 2),
            "ma60": round(float(history['Close'].rolling(60).mean().iloc[-1]), 2),
            "vol_ratio": round(float(vol_ratio), 2),
            "is_above_ma20": bool(off_price > history['Close'].rolling(20).mean().iloc[-1]),
            "is_above_ma60": bool(off_price > history['Close'].rolling(60).mean().iloc[-1])
        }
    except: return None

def get_sentiment_data():
    sentiment = {"now": None, "last": None, "week": None, "month": None, "vix": None}
    try:
        url = "https://fear-and-greed-index.p.rapidapi.com/v1/fgi"
        headers = {"x-rapidapi-key": RAPID_API_KEY, "x-rapidapi-host": "fear-and-greed-index.p.rapidapi.com"}
        res = requests.get(url, headers=headers, timeout=10).json()
        if 'fgi' in res:
            f = res['fgi']
            sentiment.update({
                "now": {"score": int(f['now']['value']), "label": f['now']['valueText'].upper()},
                "last": {"score": int(f['previousClose']['value']), "label": f['previousClose']['valueText'].upper()},
                "week": {"score": int(f['oneWeekAgo']['value']), "label": f['oneWeekAgo']['valueText'].upper()},
                "month": {"score": int(f['oneMonthAgo']['value']), "label": f['oneMonthAgo']['valueText'].upper()}
            })
        vix_data = yf.download("^VIX", period="2d", progress=False)
        if not vix_data.empty: sentiment["vix"] = round(float(vix_data['Close'].values.flatten()[-1]), 2)
    except: pass
    return sentiment


def get_precise_summary():
    """ 🌟 修正版：獲取三大法人合計與定錨日期 - 強制降序排列 """
    res = {"foreign": 0.0, "trust": 0.0, "dealer": 0.0, "total": 0.0, "date": ""}
    base = "https://tw.stock.yahoo.com/_td-stock/api/resource/StockServices.trades"
    params = "bkt=&device=desktop&intl=tw&lang=zh-Hant-TW&region=TW&site=finance&tz=Asia/Taipei"
    try:
        t_res = requests.get(f"{base};exchange=TAI;sortBy=-date;limit=1?{params}", headers=HEADERS).json()
        o_res = requests.get(f"{base};exchange=TWO;sortBy=-date;limit=1?{params}", headers=HEADERS).json()
        if 'list' in t_res and len(t_res['list']) > 0:
            l = t_res['list'][0]
            res["date"] = l['date'][:10].replace('-', '')
            res["foreign"] = round((clean_num(l.get('foreignDiffM')) + clean_num(o_res['list'][0].get('foreignDiffM'))) / 100, 2)
            res["trust"] = round((clean_num(l.get('investmentTrustDiffM')) + clean_num(o_res['list'][0].get('investmentTrustDiffM'))) / 100, 2)
            res["dealer"] = round((clean_num(l.get('dealerDiffM')) + clean_num(o_res['list'][0].get('dealerDiffM'))) / 100, 2)
            res["total"] = round(res["foreign"] + res["trust"] + res["dealer"], 2)
    except: pass
    return res

def get_dashboard_totals():
    """ 🌟 修正版：獲取全市場融資券總額 - 強制降序排列 """
    result = {"total_f": 0.0, "total_s": 0}
    base = "https://tw.stock.yahoo.com/_td-stock/api/resource/StockServices.twcredits"
    params = "bkt=&device=desktop&intl=tw&lang=zh-Hant-TW&region=TW&site=finance&tz=Asia/Taipei"
    try:
        t_res = requests.get(f"{base};exchange=TAI;sortBy=-date;limit=1?{params}", headers=HEADERS).json()
        o_res = requests.get(f"{base};exchange=TWO;sortBy=-date;limit=1?{params}", headers=HEADERS).json()
        if 'credits' in t_res:
            l_tai = t_res['credits']['list'][0]
            l_two = o_res['credits']['list'][0]
            result["total_f"] = round((clean_num(l_tai.get('financingChangeM')) + clean_num(l_two.get('financingChangeM'))) / 100, 2)
            result["total_s"] = int(clean_num(l_tai.get('shortChangeVolK')) + clean_num(l_two.get('shortChangeVolK')))
    except: pass
    return result

def get_official_margin_details(d_twse):
    """ 🌟 同步抓取官方個股資券明細 (上市+上櫃) """
    stock_margin_map = {}
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
                stock_margin_map[sid] = {"f_change": clean_num(row[6])-clean_num(row[5]), "s_change": clean_num(row[12])-clean_num(row[11])}
        # 上櫃 OpenAPI
        otc_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance"
        o_resp = session.get(otc_url, headers=HEADERS, timeout=10)
        o_text = o_resp.content.decode('cp950', errors='ignore') if o_resp.status_code == 200 else ""
        if o_text.strip().startswith('['):
            for item in json.loads(o_text):
                sid = str(item.get('SecuritiesCompanyCode', '')).strip()
                stock_margin_map[sid] = {"f_change": clean_num(item.get('MarginPurchaseBalance')) - clean_num(item.get('MarginPurchaseBalancePreviousDay')), "s_change": clean_num(item.get('ShortSaleBalance')) - clean_num(item.get('ShortSaleBalancePreviousDay'))}
    except: pass
    return stock_margin_map


@app.route('/api/init_progress')
def get_init_progress(): return jsonify(INIT_PROGRESS)

@app.route('/api/data')
def get_main_data():
    global GLOBAL_DATA_CACHE, RADAR_RESULTS, RADAR_LAST_DATE
    if not INIT_PROGRESS["is_done"]: return jsonify({"status": "loading"}), 202

    # A. 執行 Yahoo 定錨 (解決 2015 錯誤)
    summary_board = get_precise_summary()
    anchor_date = summary_board.get("date")
    if not anchor_date or int(anchor_date) < 20240101: 
        anchor_date = datetime.now().strftime("%Y%m%d")

    # B. 快取檢查
    if GLOBAL_DATA_CACHE and GLOBAL_DATA_CACHE["date"] == anchor_date:
        return jsonify(GLOBAL_DATA_CACHE)

    start_dt = datetime.strptime(anchor_date, "%Y%m%d")
    for i in range(5):
        d_twse = (start_dt - timedelta(days=i)).strftime("%Y%m%d")
        d_tpex = f"{int(d_twse[:4]) - 1911}/{d_twse[4:6]}/{d_twse[6:]}"
        
        try:
            # 1. 抓取上市排行
            tse_url = f"https://www.twse.com.tw/fund/T86?response=json&date={d_twse}&selectType=ALL"
            tse_res = requests.get(tse_url, headers=HEADERS, timeout=10).json()
            if tse_res.get('stat') != 'OK': continue
            
            # 2. 🌟 補全變數：抓取情緒與資券 (同步解決 undefined)
            taiex = get_taiex_info(d_twse)
            sentiment = get_sentiment_data()
            board_margin = get_dashboard_totals() # 從 Yahoo 拿全市場融資券
            margin_map = get_official_margin_details(d_twse) # 拿官方明細
            
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

            # 標籤注入
            profiles = df['stock_id'].apply(lambda sid: (GLOBAL_STOCK_DB.get(sid, {}).get('electronics') or "一般個股", GLOBAL_STOCK_DB.get(sid, {})))
            df['category'], df['all_tags'] = [p[0] for p in profiles], [p[1] for p in profiles]
            df.loc[df['is_etf'], 'category'] = 'ETF/指數標的'
            df['margin'] = df['stock_id'].apply(lambda x: margin_map.get(x, {"f_change":0, "s_change":0}))

            # 4. 🌟 計算市場寬度 (Market Breadth)
            up_stocks = len(df[(df['total'] > 0) & (~df['is_etf'])])
            down_stocks = len(df[(df['total'] < 0) & (~df['is_etf'])])
            breadth = {"up": up_stocks, "down": down_stocks}

            # 5. 🌟 計算決策燈號 (Resonance Signals)
            inst_buy = summary_board["total"] > 0
            margin_inc = board_margin["total_f"] > 0
            signals = {
                "inst": "買盤力道強勁" if inst_buy else "買盤尚未回流",
                "margin": "籌碼換手乾淨" if not margin_inc and inst_buy else "情緒過熱" if margin_inc and inst_buy else "散戶接盤" if margin_inc else "💤 交投平淡"
            }

            # 6. 族群統計 (非互斥)
            sector_dict = {}
            for _, row in df[~df['is_etf']].iterrows():
                for t_name in set(v for v in row['all_tags'].values() if v and v != "一般個股"):
                    if t_name not in sector_dict: sector_dict[t_name] = {"total":0.0, "f":0.0, "t":0.0, "d":0.0, "comps":[]}
                    s = sector_dict[t_name]
                    s["total"] += float(row['total']); s["f"] += float(row['foreign']); s["t"] += float(row['trust']); s["d"] += float(row['dealer'])
                    s["comps"].append({"stock_id": row['stock_id'], "stock_name": row['stock_name'], "total": row['total']})

            sector_list = []
            for name, s in sector_dict.items():
                tag_type = next((k for k, v in GLOBAL_STOCK_DB.get(s["comps"][0]["stock_id"], {}).items() if v == name), "basic")
                sector_list.append({"name": name, "tag_type": tag_type, "total": round(s["total"],0), "foreign": round(s["f"],0), "trust": round(s["t"],0), "dealer": round(s["d"],0), "top_components": sorted(s["comps"], key=lambda x: x['total'], reverse=True)[:5]})

            # 數據洗淨
            clean_records = json.loads(df.to_json(orient='records'))
            def gen_rank(c): 
                t, o = [r for r in clean_records if r['market']=='tse'], [r for r in clean_records if r['market']=='otc']
                return { "tse_b": sorted([r for r in t if r[c]>0], key=lambda x:x[c], reverse=True)[:500], "tse_s": sorted([r for r in t if r[c]<0], key=lambda x:x[c])[:500], "otc_b": sorted([r for r in o if r[c]>0], key=lambda x:x[c], reverse=True)[:500], "otc_s": sorted([r for r in o if r[c]<0], key=lambda x:x[c])[:500] }

            top_sectors_names = [s['name'] for s in sorted([s for s in sector_list if s['total'] > 0], key=lambda x: x['total'], reverse=True)[:10]]
            chip_map = {str(r['stock_id']): {"f": r['foreign'], "t": r['trust'], "d": r['dealer']} for _, r in df.iterrows()}
            
            # 🌟 最終快取封裝
            GLOBAL_DATA_CACHE = {
                "date": str(d_twse), "taiex": taiex, "sentiment": sentiment, "summary": summary_board, "margin": {"financing": board_margin["total_f"], "short_selling": board_margin["total_s"]},
                "sectors": { "buy": sorted([s for s in sector_list if s['total']>0], key=lambda x:x['total'], reverse=True)[:15], "sell": sorted([s for s in sector_list if s['total']<0], key=lambda x:x['total'])[:15] },
                "rankings": { "total": gen_rank('total'), "foreign": gen_rank('foreign'), "trust": gen_rank('trust'), "dealer": gen_rank('dealer') },
                "breadth": breadth, "signals": signals,
                "radar_ingredients": { "chip_map": chip_map, "top_sectors": top_sectors_names, "date": d_twse }
            }
            if not IS_RADAR_RUNNING: threading.Thread(target=run_radar_background, args=(chip_map, top_sectors_names, GLOBAL_STOCK_DB, d_twse), daemon=True).start()
            
            print(f"✅ 全系統資料定錨: {d_twse}")
            return jsonify(GLOBAL_DATA_CACHE)
        except Exception as e: print(f"❌ 處理錯誤: {e}"); continue
    return jsonify({"error": "No data"}), 404


@app.route('/api/radar/refresh', methods=['POST'])
def manual_radar_refresh():
    global IS_RADAR_RUNNING, GLOBAL_DATA_CACHE, RADAR_RESULTS
    
    if IS_RADAR_RUNNING:
        return jsonify({"status": "error", "message": "雷達正在掃描中"}), 409
        
    if not GLOBAL_DATA_CACHE or "radar_ingredients" not in GLOBAL_DATA_CACHE:
        return jsonify({"status": "error", "message": "尚未獲取基礎資料"}), 400

    # 🌟 關鍵修正 1：清空結果並將進度歸零，這樣前端才會立刻變回 Loading 狀態
    RADAR_RESULTS = None 
    radar_select.PROGRESS = 0 # 重置選股引擎內的進度變數
    
    ing = GLOBAL_DATA_CACHE["radar_ingredients"]
    
    # 🌟 關鍵修正 2：啟動背景掃描
    threading.Thread(
        target=run_radar_background, 
        args=(ing["chip_map"], ing["top_sectors"], GLOBAL_STOCK_DB, ing["date"]), 
        daemon=True
    ).start()
    
    return jsonify({"status": "success"})

@app.route('/api/radar')
def get_radar(): return jsonify(RADAR_RESULTS)

@app.route('/api/radar_progress')
def get_radar_progress(): 
    return jsonify({"progress": getattr(radar_select, 'PROGRESS', 0), "is_running": IS_RADAR_RUNNING})

if __name__ == '__main__':
    threading.Thread(target=scrape_all_yahoo_classes, daemon=True).start()
    app.run(debug=True, port=5000, use_reloader=False)