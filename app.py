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
# 🌟 確保安裝：pip install scrapling
from scrapling import Fetcher

# 🌟 導入選股引擎
import radar_select 

app = Flask(__name__)
CORS(app)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 全域狀態變數 ---
GLOBAL_STOCK_DB = {}   
RADAR_RESULTS = None    

INIT_PROGRESS = {
    "percentage": 0, "status": "IDLE", "current_item": "", "total_tasks": 0, "current_task_idx": 0, "is_done": False
}

MAP_FILE = "industry_map.json"

# --- 1. 產業地圖掃描邏輯 ---

def scrape_all_yahoo_classes():
    global GLOBAL_STOCK_DB, INIT_PROGRESS
    
    if os.path.exists(MAP_FILE):
        print(f"📁 發現本地產業地圖，正在載入...")
        try:
            with open(MAP_FILE, 'r', encoding='utf-8') as f:
                GLOBAL_STOCK_DB = json.load(f)
            INIT_PROGRESS["percentage"] = 100
            INIT_PROGRESS["is_done"] = True
            threading.Thread(target=run_radar_background, daemon=True).start()
            return
        except:
            print(f"❌ 讀取本地檔案失敗，重新啟動線上掃描")

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
            target_h2 = None
            for h2 in all_h2:
                if t['title'] in h2.text:
                    target_h2 = h2
                    break
            
            if not target_h2: continue
            
            # Scrapling 的 parent() 鏈接
            parent_div = target_h2.parent().parent()
            # 🌟 修正點：使用 .attrib 獲取屬性
            links = parent_div.css('ul a[href*="class-quote?"]')
            for l in links:
                category_links.append({
                    "url": "https://tw.stock.yahoo.com" + l.attrib['href'],
                    "name": l.text.strip(),
                    "weight_key": t['weight_key']
                })
        
        total = len(category_links)
        INIT_PROGRESS["total_tasks"] = total
        for idx, item in enumerate(category_links):
            INIT_PROGRESS["current_item"] = item["name"]
            INIT_PROGRESS["percentage"] = int((idx / total) * 100)
            try:
                cat_page = Fetcher.get(item["url"])
                ids = re.findall(r'/quote/(\d{4})', cat_page.content)
                # 🌟 修正點：確保 GLOBAL_STOCK_DB 內的所有值都是 string 而非 set
                for sid in list(set(ids)):
                    if sid not in GLOBAL_STOCK_DB: 
                        GLOBAL_STOCK_DB[sid] = {"electronics": "", "concepts": "", "group": "", "basic": ""}
                    GLOBAL_STOCK_DB[sid][item["weight_key"]] = str(item["name"])
            except: continue
        
        with open(MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(GLOBAL_STOCK_DB, f, ensure_ascii=False, indent=4)

        INIT_PROGRESS["is_done"] = True
        print("✅ 產業地圖收錄完成。啟動初始雷達掃描...")
        threading.Thread(target=run_radar_background, daemon=True).start()
    except Exception as e:
        print(f"地圖掃描異常: {e}")

def run_radar_background(chip_map=None, top_sectors=None, industry_db=None):
    global RADAR_RESULTS
    # 確保傳入 radar_select 的也是清理過的資料
    RADAR_RESULTS = radar_select.run_radar_scan(chip_map, top_sectors, industry_db or GLOBAL_STOCK_DB)

# --- 2. 核心運算邏輯 ---

def clean_num(val):
    try: return float(str(val).replace(',', '').strip())
    except: return 0.0

def get_taiex_info(target_date_str=None):
    try:
        query_date = target_date_str or datetime.now().strftime("%Y%m%d")
        print(f"加權指數資料 - {query_date}...", end="")

        twse_url = f"https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={query_date}"
        twse_res = requests.get(twse_url, headers=HEADERS, timeout=10).json()
        
        if twse_res.get('stat') != 'OK': 
            print(" [未更新]") 
            return None

        latest_market_data = twse_res['data'][-1]
        official_price = float(latest_market_data[4].replace(',', ''))
        official_diff = float(latest_market_data[5].replace(',', ''))
        
        amounts = [float(r[2].replace(',', '')) / 100000000 for r in twse_res['data']]
        vol_ratio = 0.0
        if len(amounts) >= 5:
            vol_ratio = amounts[-1] / (sum(amounts[-5:]) / 5)

        twii = yf.Ticker("^TWII")
        history = twii.history(period="150d")
        fmt_date = pd.to_datetime(f"{query_date[:4]}-{query_date[4:6]}-{query_date[6:]}").tz_localize('Asia/Taipei')

        if fmt_date not in history.index:
            new_row = pd.DataFrame({'Close': [official_price]}, index=[fmt_date])
            history = pd.concat([history, new_row])
        else:
            history.at[fmt_date, 'Close'] = official_price

        c_ma20 = history['Close'].rolling(window=20).mean().iloc[-1]
        c_ma60 = history['Close'].rolling(window=60).mean().iloc[-1]
        prev_close = history['Close'].iloc[-2]

        print(" [資料對齊]")
        return {
            "price": round(official_price, 2), "diff": round(official_diff, 2),
            "pct": round((official_diff / prev_close) * 100, 2),
            "ma20": round(c_ma20, 2), "ma60": round(c_ma60, 2),
            "vol_ratio": round(float(vol_ratio), 2),
            "is_above_ma20": bool(official_price > c_ma20),
            "is_above_ma60": bool(official_price > c_ma60),
            "date": query_date
        }
    except Exception as e:
        print(f" [異常: {e}]")
        return None

def get_precise_summary():
    res_data = {"foreign": 0.0, "trust": 0.0, "dealer": 0.0, "total": 0.0, "date": ""}
    url = "https://tw.stock.yahoo.com/institutional-trading/"
    try:
        page = Fetcher.get(url)

        # 🌟 1. 抓取日期：根據妳的診斷 Log，屬性名稱是 'datatime'
        time_tags = page.css('time')
        for t in time_tags:
            # 同時檢查 'datatime' (妳看到的) 與 'datetime' (標準格式)
            raw_date = t.attrib.get('datatime') or t.attrib.get('datetime') or t.text
            
            if raw_date:
                match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', raw_date)
                if match:
                    res_data["date"] = "".join(match.groups())
                    print(f"法人合計日期定錨 - {res_data['date']}")
                    break

        # 2. 抓取法人買賣金額數值
        spans = page.css('span[class*="c-trend-"]')
        all_vals = []
        for s in spans:
            val_text = s.text.replace(',', '').strip()
            num_match = re.search(r'(-?\d+\.?\d*)', val_text)
            if num_match:
                all_vals.append(float(num_match.group(1)))

        # 按照 Yahoo 結構 (0,1,2=上市; 4,5,6=上櫃)
        if len(all_vals) >= 7:
            res_data['foreign'] = round(all_vals[0] + all_vals[4], 2)
            res_data['trust']   = round(all_vals[1] + all_vals[5], 2)
            res_data['dealer']  = round(all_vals[2] + all_vals[6], 2)
            res_data['total']   = round(res_data['foreign'] + res_data['trust'] + res_data['dealer'], 2)
        else:
            print(f"法人合計 - 數值不足 (僅 {len(all_vals)} 筆)")

    except Exception as e:
        print(f"Scrapling 爬取失敗: {e}")
        # 如果真的還是抓不到，強迫定錨在昨天，避免系統 404
        res_data["date"] = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        
    return res_data

@app.route('/api/init_progress')
def get_init_progress(): return jsonify(INIT_PROGRESS)

@app.route('/api/data')
def get_main_data():
    if not INIT_PROGRESS["is_done"]: return jsonify({"status": "loading"}), 202

    summary_board = get_precise_summary()
    
    # 🌟 優化後的日期解析邏輯 (增加錯誤防護)
    if summary_board.get("date"):
        try:
            start_date = datetime.strptime(summary_board["date"], "%Y%m%d")
        except ValueError:
            print(f"⚠️ 日期格式異常({summary_board['date']})，改用系統今日")
            start_date = datetime.now()
    else:
        start_date = datetime.now()

    for i in range(5):
        target = start_date - timedelta(days=i)
        d_twse = target.strftime("%Y%m%d")
        d_tpex = f"{target.year - 1911}/{target.strftime('%m/%d')}"
        print(f"排行資料 - {d_twse}", end="")

        try:
            tse_url = f"https://www.twse.com.tw/fund/T86?response=json&date={d_twse}&selectType=ALL"
            tse_res = requests.get(tse_url, headers=HEADERS, timeout=10).json()
            if tse_res.get('stat') != 'OK': 
                print(" [資料尚未更新]")
                continue
            
            print(" [資料對齊]")
            taiex = get_taiex_info(d_twse)
            summary_board["date"] = d_twse

            # 處理上市資料
            raw_tse = pd.DataFrame(tse_res['data'])
            df_tse = pd.DataFrame({
                'stock_id': raw_tse.iloc[:, 0].str.strip(),
                'stock_name': raw_tse.iloc[:, 1].str.strip(),
                'foreign': raw_tse.iloc[:, 4].apply(clean_num) / 1000,
                'trust': raw_tse.iloc[:, 10].apply(clean_num) / 1000,
                'dealer': raw_tse.iloc[:, 11].apply(clean_num) / 1000,
                'total': raw_tse.iloc[:, 18].apply(clean_num) / 1000,
                'market': 'tse'
            })

            # 處理上櫃資料
            otc_url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&d={d_tpex}"
            otc_res = requests.get(otc_url, headers=HEADERS, timeout=10).json()
            otc_rows = otc_res.get('tables', [{}])[0].get('data', []) or otc_res.get('aaData', []) or []
            df_otc = pd.DataFrame()
            if otc_rows:
                raw_otc = pd.DataFrame(otc_rows)
                df_otc = pd.DataFrame({
                    'stock_id': raw_otc.iloc[:, 0].str.strip(),
                    'stock_name': raw_otc.iloc[:, 1].str.strip(),
                    'foreign': raw_otc.iloc[:, 4].apply(clean_num) / 1000,
                    'trust': raw_otc.iloc[:, 13].apply(clean_num) / 1000,
                    'dealer': raw_otc.iloc[:, 22].apply(clean_num) / 1000,
                    'total': raw_otc.iloc[:, 23].apply(clean_num) / 1000,
                    'market': 'otc'
                })

            df = pd.concat([df_tse, df_otc], ignore_index=True).fillna(0)
            raw_sids = df['stock_id'].astype(str).str.strip()
            df['is_etf'] = raw_sids.apply(lambda x: len(x) != 4 or x.startswith('00'))
            df['stock_id'] = raw_sids.apply(lambda x: "".join(filter(str.isdigit, x)))

            def get_stock_profile(sid):
                tags = GLOBAL_STOCK_DB.get(sid, {"electronics": "", "concepts": "", "group": "", "basic": ""})
                clean_tags = {k: str(v).strip() for k, v in tags.items()}
                primary = (clean_tags.get('electronics') or clean_tags.get('concepts') or clean_tags.get('group') or clean_tags.get('basic') or "一般個股")
                return primary, clean_tags

            profiles = df['stock_id'].apply(get_stock_profile)
            df['category'] = [p[0] for p in profiles]
            df['all_tags'] = [p[1] for p in profiles]
            df.loc[df['is_etf'], 'category'] = 'ETF/指數標的'

            # 製作雷達小抄
            chip_map = {str(row['stock_id']): {
                "f": round(float(row['foreign']), 0),
                "t": round(float(row['trust']), 0),
                "d": round(float(row['dealer']), 0)
            } for _, row in df.iterrows()}

            # 族群統計與強勢族群提取
            sector_dict = {}
            
            # 只針對個股 (非 ETF) 進行遍歷
            for _, row in df[~df['is_etf']].iterrows():
                # 獲取這檔股票所有的標籤名稱 (electronics, concepts, group, basic)
                all_tags_set = set(val for val in row['all_tags'].values() if val and val != "一般個股")
                
                for tag_name in all_tags_set:
                    if tag_name not in sector_dict:
                        sector_dict[tag_name] = {"total": 0.0, "f": 0.0, "t": 0.0, "d": 0.0, "components": []}
                    
                    s = sector_dict[tag_name]
                    s["total"] += float(row['total'])
                    s["f"] += float(row['foreign'])
                    s["t"] += float(row['trust'])
                    s["d"] += float(row['dealer'])
                    s["components"].append({
                        "stock_id": row['stock_id'],
                        "stock_name": row['stock_name'],
                        "total": row['total']
                    })

            sector_list = []
            for name, s in sector_dict.items():
                if abs(s["total"]) < 1: continue 
                
                sector_list.append({
                    "name": name,
                    "total": round(s["total"], 0),
                    "foreign": round(s["f"], 0),
                    "trust": round(s["t"], 0),
                    "dealer": round(s["d"], 0),
                    "top_components": sorted(s["components"], key=lambda x: x['total'], reverse=True)[:5]
                })

            # 🌟 6. 提取強勢族群前 10 名 (邏輯維持不變)
            top_sectors_list = sorted([s for s in sector_list if s['total'] > 0], key=lambda x: x['total'], reverse=True)[:10]
            top_sectors_names = [s['name'] for s in top_sectors_list]
            # 啟動雷達
            threading.Thread(target=run_radar_background, args=(chip_map, top_sectors_names, GLOBAL_STOCK_DB), daemon=True).start()

            def get_ranks(col, source_df):
                return {
                    "tse_b": source_df[source_df['market']=='tse'].nlargest(500, col).to_dict('records'),
                    "tse_s": source_df[source_df['market']=='tse'].nsmallest(500, col).to_dict('records'),
                    "otc_b": source_df[source_df['market']=='otc'].nlargest(500, col).to_dict('records'),
                    "otc_s": source_df[source_df['market']=='otc'].nsmallest(500, col).to_dict('records')
                }

            print(f"全系統資料基準點：{d_twse}")
            print("-" * 40)
            return jsonify({
                "date": d_twse, "taiex": taiex, "summary": summary_board,
                "sectors": {
                    "buy": sorted([s for s in sector_list if s['total'] > 0], key=lambda x: x['total'], reverse=True)[:15],
                    "sell": sorted([s for s in sector_list if s['total'] < 0], key=lambda x: x['total'])[:15]
                },
                "rankings": {"total": get_ranks('total', df), "foreign": get_ranks('foreign', df), "trust": get_ranks('trust', df), "dealer": get_ranks('dealer', df)}
            })
        except Exception as e:
            print(f" [處理錯誤: {e}]")
            continue

    return jsonify({"error": "No data found"}), 404

@app.route('/api/radar')
def get_radar(): return jsonify(RADAR_RESULTS)

@app.route('/api/radar_progress')
def get_radar_progress(): return jsonify({"progress": getattr(radar_select, 'PROGRESS', 0)})

if __name__ == '__main__':
    threading.Thread(target=scrape_all_yahoo_classes, daemon=True).start()
    app.run(debug=True, port=5000, use_reloader=False)