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
import valuechain
import threading


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
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.twse.com.tw/zh/page/trading/exchange/MI_INDEX.html'
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
valuechain_PROGRESS = 0
IS_valuechain_RUNNING = False
MAP_FILE = "industry_map.json"
valuechain_MGR = valuechain.valuechainManager(GLOBAL_STOCK_DB) # 🌟 改為大寫


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
        print(f"[抓取] Yahoo 總額數據日期: {result['date']}")
        
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
    except Exception as e: print(f"Yahoo Commander Error: {e}")
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
            print(f"[抓取] 三大法人 - 最新日期: {res['date']}")
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
        print(f"發現本地產業地圖，正在載入...")
        try:
            with open(MAP_FILE, 'r', encoding='utf-8') as f:
                loaded_stock_db = json.load(f)
            GLOBAL_STOCK_DB.clear()
            GLOBAL_STOCK_DB.update(loaded_stock_db)
            valuechain_MGR.industry_db = GLOBAL_STOCK_DB
            INIT_PROGRESS.update({"percentage": 100, "is_done": True})
            
            threading.Thread(target=initial_data_sync, daemon=True).start()
            return
        except: print(f"讀取快取失敗")

    INIT_PROGRESS["status"] = "SCANNING"
    # 🌟 修正：「上市類股」與「上櫃類股」原本共用同一個 weight_key："basic"，
    # 會導致其中一邊的分類標籤直接覆蓋另一邊，讓 GLOBAL_STOCK_DB（後續 valuechain.py
    # 的 run_full_update() 會拿它當 industry_db 使用）遺失「上市／上櫃」的區分。
    targets = [
        {"title": "電子產業", "weight_key": "electronics"},
        {"title": "概念股", "weight_key": "concepts"},
        {"title": "上市類股", "weight_key": "basic_tse"},
        {"title": "上櫃類股", "weight_key": "basic_otc"},
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
                    if sid not in GLOBAL_STOCK_DB: GLOBAL_STOCK_DB[sid] = {"electronics": "", "concepts": "", "group": "", "basic_tse": "", "basic_otc": ""}
                    GLOBAL_STOCK_DB[sid][item["weight_key"]] = str(item["name"])
            except: continue
        
        with open(MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(GLOBAL_STOCK_DB, f, ensure_ascii=False, indent=4)
        INIT_PROGRESS["is_done"] = True
        print("y股市地圖收錄完成。啟動主動同步任務...")
        threading.Thread(target=initial_data_sync, daemon=True).start()
    except Exception as e: print(f"地圖掃描異常: {e}")

def run_radar_background(chip_map=None, top_sectors=None, industry_db=None, current_date=""):
    global RADAR_RESULTS, IS_RADAR_RUNNING, RADAR_LAST_DATE
    
    with RADAR_LOCK:
        if IS_RADAR_RUNNING: return
        IS_RADAR_RUNNING = True

    try:
        # 1. 準備基礎資料 (直接使用參數，不建立多餘的中間變數)
        cm_data = chip_map if chip_map is not None else {}
        db_data = industry_db if industry_db is not None else GLOBAL_STOCK_DB
        
        # 2. 獲取 Valuechain 運算結果 (從全域快取拿)
        vc_res = None
        if GLOBAL_DATA_CACHE and "valuechain_map" in GLOBAL_DATA_CACHE:
            vc_res = GLOBAL_DATA_CACHE["valuechain_map"]
        
        # 💡 容錯處理：如果快取還沒建立，利用傳入的 top_sectors 構建一個臨時結構
        if not vc_res and top_sectors:
            vc_res = {"top5": [{"key": f"類別::{name}"} for name in top_sectors], "others": []}

        print(f"[雷達啟動] 正在掃描基準日: {current_date or '最新'} | 籌碼對齊: {'YES' if chip_map else 'NO'}")
        
        # 🚀 3. 呼叫雷達掃描 (確保傳入對應的 4 個具名參數)
        results = radar_select.run_radar_scan(
            chip_map=cm_data, 
            valuechain_result=vc_res, 
            vc_mgr=valuechain_MGR, 
            industry_db=db_data
        )
        
        RADAR_RESULTS = results
        RADAR_LAST_DATE = current_date
        print("[雷達完成] 結果已更新。")
        
    except Exception as e:
        print(f"[雷達異常]: {e}")
        import traceback
        traceback.print_exc() 
    finally:
        with RADAR_LOCK: IS_RADAR_RUNNING = False

def initial_data_sync():
    """ 程式啟動後，主動抓取最新籌碼，若當日尚未發布則自動回退至前一交易日 """
    print("[系統初始化] 正在定錨最新日期並同步籌碼...")
    board = get_dashboard_commander()
    
    # 🌟 初始嘗試日期 (從 Yahoo 拿到的日期)
    target_date = board["date"]
    
    if not target_date:
        print("❌ [系統失敗] 無法獲取定錨日期")
        run_radar_background()
        return

    valid_chip_map = None
    final_anchor_date = target_date

    # 🌟 核心修正：進入最多 5 次的回退嘗試 (處理尚未發布或假日)
    for attempt in range(5):
        try:
            print(f"📡 [預抓] 嘗試抓取 {final_anchor_date} 個股籌碼 (第 {attempt+1} 次嘗試)...")
            
            # 抓取上市排行
            tse_url = f"https://www.twse.com.tw/fund/T86?response=json&date={final_anchor_date}&selectType=ALL"
            tse_res = requests.get(tse_url, headers=HEADERS, timeout=20).json()
            
            # 🌟 關鍵判斷：如果證交所說日期太大，或是這天根本沒資料 (stat != 'OK')
            if tse_res.get('stat') != 'OK' or 'data' not in tse_res:
                print(f"  ⚠️ {final_anchor_date} 證交所尚未發布明細，往前回退一天...")
                # 日期減一天
                dt = datetime.strptime(final_anchor_date, "%Y%m%d") - timedelta(days=1)
                final_anchor_date = dt.strftime("%Y%m%d")
                continue # 重新跑下一輪迴圈

            # 2. 如果上市成功，接著抓上櫃並解析
            chip_map = {}
            for r in tse_res['data']:
                if len(r) > 18:
                    sid = str(r[0]).strip()
                    chip_map[sid] = {"f": clean_num(r[4])/1000, "t": clean_num(r[10])/1000}

            # 抓取上櫃排行
            d_tpex = f"{int(final_anchor_date[:4])-1911}/{final_anchor_date[4:6]}/{final_anchor_date[6:]}"
            otc_url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&d={d_tpex}"
            otc_res = requests.get(otc_url, headers=HEADERS, timeout=20).json()
            
            otc_rows = otc_res['tables'][0].get('data', []) if ('tables' in otc_res and len(otc_res['tables']) > 0) else (otc_res.get('aaData', []) or otc_res.get('data', []))

            if otc_rows:
                for r in otc_rows:
                    if len(r) > 13:
                        sid = str(r[0]).strip()
                        chip_map[sid] = {"f": clean_num(r[4])/1000, "t": clean_num(r[13])/1000}
                
                print(f"✅ 成功定錨！使用日期: {final_anchor_date}")
                valid_chip_map = chip_map
                break # 成功了，跳出 5 次嘗試的迴圈
            else:
                # 🌟 修正：原本這裡上市成功、但上櫃回傳空值時，既沒有 break，
                # 也沒有把 final_anchor_date 往前推一天，會導致下一輪 attempt
                # 重複嘗試同一天，白白浪費重試次數、最後很容易 5 次都失敗。
                print(f"  ⚠️ {final_anchor_date} 上櫃資料為空，往前回退一天...")
                dt = datetime.strptime(final_anchor_date, "%Y%m%d") - timedelta(days=1)
                final_anchor_date = dt.strftime("%Y%m%d")
            
        except Exception as e:
            print(f"  ❌ 嘗試 {final_anchor_date} 時發生異常: {e}")
            dt = datetime.strptime(final_anchor_date, "%Y%m%d") - timedelta(days=1)
            final_anchor_date = dt.strftime("%Y%m%d")

    # 🌟 最終步驟：根據「真正成功」的日期啟動任務
    if valid_chip_map:
        # 1. 啟動歷史補齊 (傳入真正抓到資料的那天)
        print(f"📢 [系統] 以 {final_anchor_date} 為起點，啟動背景自動補齊...")
        threading.Thread(
            target=valuechain_MGR.sync_historical_data, 
            args=(final_anchor_date,), 
            daemon=True
        ).start()
        
        # 2. 啟動雷達
        run_radar_background(
            chip_map=valid_chip_map, 
            top_sectors=[], 
            industry_db=GLOBAL_STOCK_DB, 
            current_date=final_anchor_date
        )
    else:
        print("❌ [雷達警告] 連續嘗試失敗，執行無籌碼掃描。")
        run_radar_background()
        
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
    # 🌟 修正：下面第 5 天回溯迴圈找到的實際交易日 d_twse，可能跟這裡剛算出來的 anchor_date
    # 不同（例如今天資料還沒公布，往前抓到昨天）。之前把 GLOBAL_DATA_CACHE["date"]（存的是
    # d_twse）拿來跟每次重新計算的 anchor_date 比對，兩者根本不是同一個變數，快取永遠對不上，
    # 導致每次呼叫都重新打一輪外部 API。這裡改成比對「上次計算時所使用的 anchor_date」。
    if GLOBAL_DATA_CACHE and GLOBAL_DATA_CACHE.get("anchor_date") == anchor_date:
        return jsonify(GLOBAL_DATA_CACHE)

    start_dt = datetime.strptime(anchor_date, "%Y%m%d")
    for i in range(5):
        d_twse = (start_dt - timedelta(days=i)).strftime("%Y%m%d")
        d_tpex = f"{int(d_twse[:4])-1911}/{d_twse[4:6]}/{d_twse[6:]}"
        print(f"🔍 [同步] 排行資料對齊嘗試: {d_twse}")
        
        try:
            # 1. 抓取上市排行
            tse_url = f"https://www.twse.com.tw/fund/T86?response=json&date={d_twse}&selectType=ALL"
            tse_res = requests.get(tse_url, headers=HEADERS, timeout=30).json()
            if tse_res.get('stat') != 'OK' or not tse_res.get('data'): continue
            
            # 2. 抓取同步數據
            taiex = get_taiex_info(d_twse)
            sentiment = get_sentiment_data()
            margin_map = get_official_margin_details(d_twse) # 💡 這裡拿到了個股融資明細

            stale_warnings = []
            if sentiment["actual_date"] and sentiment["actual_date"] != d_twse: stale_warnings.append(f"情緒({sentiment['actual_date']})")
            if board["date"] != d_twse: stale_warnings.append(f"資券總額({board['date']})")

            # 3. 處理上市櫃排行資料
            df_tse = pd.DataFrame(tse_res['data'])
            df_tse = pd.DataFrame({'stock_id': df_tse.iloc[:, 0].str.strip(), 'stock_name': df_tse.iloc[:, 1].str.strip(), 'foreign': df_tse.iloc[:, 4].apply(clean_num)/1000, 'trust': df_tse.iloc[:, 10].apply(clean_num)/1000, 'dealer': df_tse.iloc[:, 11].apply(clean_num)/1000, 'total': df_tse.iloc[:, 18].apply(clean_num)/1000, 'market': 'tse'})
            
            otc_url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&d={d_tpex}"
            otc_json = requests.get(otc_url, headers=HEADERS).json()
            otc_rows = otc_json.get('aaData', []) or otc_json.get('data', []) or (otc_json.get('tables', [{}])[0].get('data', []) if 'tables' in otc_json else [])
            df_otc = pd.DataFrame({'stock_id': [str(r[0]).strip() for r in otc_rows], 'stock_name': [str(r[1]).strip() for r in otc_rows], 'foreign': [clean_num(r[4])/1000 for r in otc_rows], 'trust': [clean_num(r[13])/1000 for r in otc_rows], 'dealer': [clean_num(r[22])/1000 for r in otc_rows], 'total': [clean_num(r[23])/1000 for r in otc_rows], 'market': 'otc'})

            df = pd.concat([df_tse, df_otc], ignore_index=True).fillna(0)
            df['stock_id'] = df['stock_id'].astype(str).str.strip().apply(lambda x: "".join(filter(str.isdigit, x)))
            df['is_etf'] = df['stock_id'].apply(lambda x: len(x) != 4 or x.startswith('00'))
            
            # --- 💡 這裡開始準備傳給 valuechain_MGR 的資料 ---
            
            # 建立個股法人籌碼字典
            current_chip_map = {
                str(r['stock_id']): {'total': r['total']} 
                for _, r in df.iterrows()
            }

            def get_stock_profile(sid):
                tags = GLOBAL_STOCK_DB.get(sid, {"electronics":"", "concepts":"", "group":"", "basic_tse":"", "basic_otc":""})
                clean_tags = {k: str(v).strip() for k, v in tags.items()}
                primary = (clean_tags.get('electronics') or clean_tags.get('concepts') or clean_tags.get('group')
                           or clean_tags.get('basic_tse') or clean_tags.get('basic_otc') or "一般個股")
                return primary, clean_tags
            
            # 注入標籤與資券
            profiles = df['stock_id'].apply(get_stock_profile)
            df['category'], df['all_tags'] = [p[0] for p in profiles], [p[1] for p in profiles]
            df.loc[df['is_etf'], 'category'] = 'ETF/指數標的'
            df['margin'] = df['stock_id'].apply(lambda x: margin_map.get(x, {"f_change":0, "s_change":0}))

            # 4. 決策維度
            up_stocks = len(df[(df['total'] > 0) & (~df['is_etf'])])
            down_stocks = len(df[(df['total'] < 0) & (~df['is_etf'])])
            
            inst_sig = "買盤力道強勁" if board["inst_total"] > 0 else "買盤尚未回流"
            margin_sig = "交投平淡"
            if board["margin_f"] < 0 and board["inst_total"] > 0: margin_sig = "籌碼換手乾淨"
            elif board["margin_f"] > 50: margin_sig = "情緒過熱"
            elif board["margin_f"] > 0 and board["inst_total"] < 0: margin_sig = "散戶接盤"
                
            # 5. 族群統計
            sector_dict = {}
            for _, row in df[~df['is_etf']].iterrows():
                for t_name in set(v for v in row['all_tags'].values() if v and v != "一般個股"):
        

                    sub_sector_name = t_name 
        
                    if ">" in t_name:
                        parts = [p.strip() for p in t_name.split(">")]
                        if len(parts) >= 2:
                            sub_sector_name = parts[1] 
        
                    if sub_sector_name not in sector_dict:
                        sector_dict[sub_sector_name] = {"total": 0.0, "f": 0.0, "t": 0.0, "d": 0.0, "comps": []}
            
                    s = sector_dict[sub_sector_name]
                    s["total"] += float(row['total'])
                    s["f"] += float(row['foreign'])
                    s["t"] += float(row['trust'])
                    s["d"] += float(row['dealer'])
                    s["comps"].append({"stock_id": row['stock_id'], "stock_name": row['stock_name'], "total": row['total']})
                    
            sector_list = []
            for name, s in sector_dict.items():
                if abs(s["total"]) < 1: continue
                sector_list.append({"name": name, "total": round(s["total"],0), "foreign": round(s["f"],0), "trust": round(s["t"],0), "dealer": round(s["d"],0), "top_components": sorted(s["comps"], key=lambda x: x['total'], reverse=True)[:5]})

            # --- 6. 外部組件 (熱門產業：帶入法人與融資合力) ---
            try:
                # 💡 傳入剛剛準備好的 chip_map 與 margin_map
                valuechain_result = valuechain_MGR.get_valuechain_industry_data(
                    d_twse, 
                    GLOBAL_STOCK_DB, 
                    chip_map=current_chip_map, 
                    margin_map=margin_map
                )
            except Exception as e:
                print(f"熱門產業計算失敗: {e}")
                valuechain_result = {"resonance": [], "top5": [], "others": []}

            # --- 7. 排行榜格式化 ---
            clean_records = json.loads(df.to_json(orient='records'))
            def gen_rank(c):
                t, o = [r for r in clean_records if r['market']=='tse'], [r for r in clean_records if r['market']=='otc']
                return {
                    "tse_b": sorted([r for r in t if r[c]>0], key=lambda x:x[c], reverse=True)[:100],
                    "tse_s": sorted([r for r in t if r[c]<0], key=lambda x:x[c])[:100],
                    "otc_b": sorted([r for r in o if r[c]>0], key=lambda x:x[c], reverse=True)[:100],
                    "otc_s": sorted([r for r in o if r[c]<0], key=lambda x:x[c])[:100]
                }

            # --- 8. 最終資料封裝 ---
            final_data = {
                "date": str(d_twse),
                # 🌟 修正：一併存下本次用來定錨的 anchor_date，供下次請求做快取比對用
                # （避免跟上面的 d_twse 搞混，這是兩個不同階段的日期變數）
                "anchor_date": anchor_date,
                "taiex": taiex,
                "sentiment": sentiment,
                "valuechain_map": valuechain_result or {"resonance": [], "top5": [], "others": []},
                "chip_map": current_chip_map, 
                "margin_map": margin_map,
                "summary": {"foreign": board["inst_f"], "trust": board["inst_t"], "dealer": board["inst_d"], "total": board["inst_total"]},
                "margin": {"financing": board["margin_f"], "short_selling": board["margin_s"], "ratio": board["ratio"], "tse_ratio": board["tse_ratio"], "otc_ratio": board["otc_ratio"]},
                "sectors": {
                    "buy": sorted([s for s in sector_list if s['total']>0], key=lambda x:x['total'], reverse=True)[:15],
                    "sell": sorted([s for s in sector_list if s['total']<0], key=lambda x:x['total'])[:15]
                },
                "rankings": {
                    "total": gen_rank('total'), "foreign": gen_rank('foreign'), "trust": gen_rank('trust'), "dealer": gen_rank('dealer')
                },
                "breadth": {"up": up_stocks, "down": down_stocks},
                "signals": {"inst": inst_sig, "margin": margin_sig},
                "stale_warnings": stale_warnings,
                "radar_ingredients": { 
                    "chip_map": {str(r['stock_id']): {"f": r['foreign'], "t": r['trust']} for r in clean_records}, 
                    "top_sectors": [s['name'] for s in sorted([s for s in sector_list if s['total'] > 0], key=lambda x: x['total'], reverse=True)[:10]],
                    "date": d_twse 
                }
            }

            GLOBAL_DATA_CACHE = final_data
            
            # 啟動雷達
            if not IS_RADAR_RUNNING:
                ing = final_data["radar_ingredients"]
                threading.Thread(target=run_radar_background, args=(ing["chip_map"], ing["top_sectors"], GLOBAL_STOCK_DB, d_twse), daemon=True).start()

            return jsonify(GLOBAL_DATA_CACHE)
            
        except Exception as e:
            print(f"處理錯誤: {e}")
            continue

    return jsonify({"error": "No data available"}), 404

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

@app.route('/api/admin/update_valuechain_map', methods=['POST'])
def force_update_valuechain_map():
    global IS_valuechain_RUNNING, valuechain_PROGRESS
    if IS_valuechain_RUNNING:
        return jsonify({"status": "busy", "message": "同步正在進行中"}), 400
    
    def run_task():
        global IS_valuechain_RUNNING, valuechain_PROGRESS, GLOBAL_DATA_CACHE
        IS_valuechain_RUNNING = True
        valuechain_PROGRESS = 0
        try:
            def update_cb(p):
                global valuechain_PROGRESS
                valuechain_PROGRESS = p
            
            valuechain_MGR.run_full_update(progress_cb=update_cb)
            
            GLOBAL_DATA_CACHE = None
            valuechain_PROGRESS = 100
        except Exception as e:
            print(f"地圖同步失敗: {e}")
        finally:
            IS_valuechain_RUNNING = False

    threading.Thread(target=run_task, daemon=True).start()
    return jsonify({"status": "started", "message": "獨立產業鏈正在重新載入"})

@app.route('/api/valuechain_map')
def get_valuechain_map_api():
    global GLOBAL_DATA_CACHE
    
    # 如果快取裡已經有算好的產業數據（包含 5D/20D），直接回傳
    if GLOBAL_DATA_CACHE and "valuechain_map" in GLOBAL_DATA_CACHE:
        # 檢查內容是否真的有 5D 數據，避免抓到舊的 0.00 快取
        vc_data = GLOBAL_DATA_CACHE["valuechain_map"]
        if "top5" in vc_data and len(vc_data["top5"]) > 0:
            # 🌟 修正：valuechain.py 的 get_valuechain_industry_data() 實際回傳的欄位名稱是
            # "inst_net_5d" / "inst_net_20d"，不是 "net_force_5d"。原本這裡的判斷條件因為
            # key 名稱對不上，恆為 False，導致這段快取捷徑永遠不會命中，每次都被迫走下面
            # 重新計算的分支。
            if "inst_net_5d" in vc_data["top5"][0]:
                # 🟢 修正：vc_data 本身就是運算結果，直接回傳它即可
                return jsonify(vc_data)

    # 如果只有基礎數據，主動重算一次完整的歷史對齊
    if GLOBAL_DATA_CACHE and "chip_map" in GLOBAL_DATA_CACHE:
        try:
            print("🔄 [API] 偵測到歷史數據缺口，主動發起完整產業統計...")
            hot_result = valuechain_MGR.get_valuechain_industry_data(
                GLOBAL_DATA_CACHE["date"],
                GLOBAL_STOCK_DB,
                chip_map=GLOBAL_DATA_CACHE["chip_map"],
                margin_map=GLOBAL_DATA_CACHE["margin_map"]
            )
            if hot_result:
                GLOBAL_DATA_CACHE["valuechain_map"] = hot_result
                return jsonify(hot_result)
        except Exception as e:
            print(f"[API] 主動計算失敗: {e}")

    return jsonify({"status": "loading", "resonance": [], "top5": [], "others": []}), 202

@app.route('/api/valuechain_progress')
def get_valuechain_progress():
    global valuechain_PROGRESS, IS_valuechain_RUNNING
    return jsonify({"progress": valuechain_PROGRESS, "is_running": IS_valuechain_RUNNING})

if __name__ == '__main__':
    threading.Thread(target=scrape_all_yahoo_classes, daemon=True).start()
    app.run(debug=True, port=5000, use_reloader=False)
