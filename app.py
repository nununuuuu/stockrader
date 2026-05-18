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

# --- 1. 產業地圖掃描邏輯 ---

MAP_FILE = "industry_map.json"

def scrape_all_yahoo_classes():
    global GLOBAL_STOCK_DB, INIT_PROGRESS
    
    # 1. 嘗試讀取本地檔案
    if os.path.exists(MAP_FILE):
        print(f"發現本地產業地圖 ({MAP_FILE})，正在直接載入...")
        try:
            with open(MAP_FILE, 'r', encoding='utf-8') as f:
                GLOBAL_STOCK_DB = json.load(f)
            INIT_PROGRESS["percentage"] = 100
            INIT_PROGRESS["is_done"] = True
            print(f"✅ 地圖載入完成（共 {len(GLOBAL_STOCK_DB)} 檔個股資料）。啟動初始雷達掃描...")
            threading.Thread(target=run_radar_background, daemon=True).start()
            return
        except Exception as e:
            print(f"讀取本地檔案失敗，重新啟動線上掃描: {e}")

    INIT_PROGRESS["status"] = "SCANNING"
    targets = [
        {"title": "電子產業", "weight_key": "electronics"},
        {"title": "概念股", "weight_key": "concepts"},
        {"title": "上市類股", "weight_key": "basic"},
        {"title": "上櫃類股", "weight_key": "basic"},
        {"title": "集團股", "weight_key": "group"}
    ]
    try:
        res = requests.get("https://tw.stock.yahoo.com/class/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        all_h2 = soup.find_all('h2')
        category_links = []
        for t in targets:
            target_h2 = next((h2 for h2 in all_h2 if t['title'] in h2.get_text()), None)
            if not target_h2: continue
            parent_div = target_h2.find_parent('div').find_parent('div')
            links = parent_div.select('ul a[href*="class-quote?"]') if parent_div else []
            for l in links: category_links.append({"link": l, "weight_key": t['weight_key']})
        
        total = len(category_links)
        INIT_PROGRESS["total_tasks"] = total
        for idx, item in enumerate(category_links):
            cat_name = item["link"].get_text(strip=True)
            INIT_PROGRESS["current_item"] = cat_name
            INIT_PROGRESS["percentage"] = int((idx / total) * 100)
            try:
                url = "https://tw.stock.yahoo.com" + item["link"]['href']
                cat_res = requests.get(url, headers=HEADERS, timeout=10)
                ids = re.findall(r'/quote/(\d{4})', cat_res.text)
                for sid in set(ids):
                    if sid not in GLOBAL_STOCK_DB: GLOBAL_STOCK_DB[sid] = {"electronics": "", "concepts": "", "group": "", "basic": ""}
                    GLOBAL_STOCK_DB[sid][item["weight_key"]] = cat_name
            except: continue
        
        print(f"正在將產業地圖存檔至 {MAP_FILE}...")
        with open(MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(GLOBAL_STOCK_DB, f, ensure_ascii=False, indent=4)

        INIT_PROGRESS["is_done"] = True
        print("✅ 產業地圖收錄完成。啟動初始雷達掃描...")
        threading.Thread(target=run_radar_background, daemon=True).start()
    except Exception as e:
        print(f"地圖掃描異常: {e}")

def run_radar_background(chip_map=None):
    """
    修改雷達啟動邏輯，現在會接收 chip_map 進行掃描
    """
    global RADAR_RESULTS
    RADAR_RESULTS = radar_select.run_radar_scan(chip_map)

# --- 2. 核心運算邏輯 ---

def clean_num(val):
    try: return float(str(val).replace(',', '').strip())
    except: return 0.0

def get_taiex_info(target_date_str=None):
    """
    從證交所 API 拿當天最新價格，從 yfinance 拿歷史均線與量比。
    """
    try:
        query_date = target_date_str or datetime.now().strftime("%Y%m%d")
        print(f"加權指數資料 - {query_date}...", end="")

        twse_url = f"https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={query_date}"
        twse_res = requests.get(twse_url, headers=HEADERS, timeout=10).json()
        
        if twse_res.get('stat') != 'OK': 
            print(" [官方未更新]") 
            return None
        

        latest_market_data = twse_res['data'][-1]
        official_price = float(latest_market_data[4].replace(',', ''))
        official_diff = float(latest_market_data[5].replace(',', ''))
        
        # 算量比 (金額為基準)
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

        return {
            "price": round(official_price, 2),
            "diff": round(official_diff, 2),
            "pct": round((official_diff / prev_close) * 100, 2),
            "ma20": round(c_ma20, 2),
            "ma60": round(c_ma60, 2),
            "vol_ratio": round(float(vol_ratio), 2),
            "is_above_ma20": bool(official_price > c_ma20),
            "is_above_ma60": bool(official_price > c_ma60),
            "date": query_date
        }
    except Exception as e:
        print(f"抓取指數異常: {e}")
        return None

def get_precise_summary():
    res_data = {"foreign": 0.0, "trust": 0.0, "dealer": 0.0, "total": 0.0, "date": ""}
    url = "https://tw.stock.yahoo.com/institutional-trading/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        tai_section = soup.find('div', id='TAI')
        if tai_section:
            time_tag = tai_section.find('time')
            if time_tag:
                raw_date = time_tag.get('datetime') or time_tag.get_text(strip=True)
                match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', raw_date)
                if match: res_data["date"] = "".join(match.groups())

        spans = soup.find_all('span', class_=re.compile(r'C\(\$c-trend-(up|down)\)'))
        all_vals = []
        for s in spans:
            text = s.get_text(strip=True).replace(',', '')
            if re.match(r'^-?\d+\.?\d*$', text): all_vals.append(float(text))

        if len(all_vals) >= 7:
            res_data['foreign'] = round(all_vals[0] + all_vals[4], 2)
            res_data['trust']   = round(all_vals[1] + all_vals[5], 2)
            res_data['dealer']  = round(all_vals[2] + all_vals[6], 2)
            res_data['total']   = round(res_data['foreign'] + res_data['trust'] + res_data['dealer'], 2)
            print(f"法人合計 - {res_data['date']}")

    except Exception as e:
        print(f"Yahoo 爬蟲失敗: {e}")
    return res_data

@app.route('/api/init_progress')
def get_init_progress(): return jsonify(INIT_PROGRESS)

@app.route('/api/data')
def get_main_data():
    if not INIT_PROGRESS["is_done"]: return jsonify({"status": "loading"}), 202

    # 1. 爬蟲定錨日期
    summary_board = get_precise_summary()
    start_date = datetime.strptime(summary_board["date"], "%Y%m%d") if summary_board.get("date") else datetime.now()

    # 2. 進入日期對齊迴圈
    for i in range(5):
        target = start_date - timedelta(days=i)
        d_twse = target.strftime("%Y%m%d")
        d_tpex = f"{target.year - 1911}/{target.strftime('%m/%d')}"
        print(f"排行資料對齊日期 - {d_twse}", end="")

        try:
            # 檢查排行資料是否更新
            tse_url = f"https://www.twse.com.tw/fund/T86?response=json&date={d_twse}&selectType=ALL"
            tse_res = requests.get(tse_url, headers=HEADERS, timeout=10).json()
            if tse_res.get('stat') != 'OK': 
                print(" [資料尚未更新]")
                continue
            print(" [資料對齊]") # 🌟 補回狀態

            taiex = get_taiex_info(d_twse)
            summary_board["date"] = d_twse

            # 抓取並處理排行資料
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

            # 3. 🌟 精準個股判定
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

            # 🌟 4. 製作雷達籌碼小抄
            chip_map = {}
            for _, row in df.iterrows():
                chip_map[str(row['stock_id'])] = {
                    "f": round(float(row['foreign']), 0),
                    "t": round(float(row['trust']), 0),
                    "d": round(float(row['dealer']), 0)
                }
            threading.Thread(target=run_radar_background, args=(chip_map,), daemon=True).start()

            # 5. 族群統計修復
            sector_list = []
            for cat, sub in df[~df['is_etf']].groupby('category'):
                if not cat or cat == "一般個股": continue
                val = float(sub['total'].sum())
                if abs(val) < 1: continue
                sector_list.append({
                    "name": str(cat), 
                    "total": round(val, 0), 
                    "foreign": round(float(sub['foreign'].sum()), 0), 
                    "trust": round(float(sub['trust'].sum()), 0),
                    "dealer": round(float(sub['dealer'].sum()), 0),
                    "top_components": sub.nlargest(5, 'total')[['stock_id', 'stock_name', 'total']].to_dict('records')
                })

            def get_ranks(col):
                # 🌟 增加到 500 筆解決個股變少的問題
                return {
                    "tse_b": df[df['market']=='tse'].nlargest(500, col).to_dict('records'),
                    "tse_s": df[df['market']=='tse'].nsmallest(500, col).to_dict('records'),
                    "otc_b": df[df['market']=='otc'].nlargest(500, col).to_dict('records'),
                    "otc_s": df[df['market']=='otc'].nsmallest(500, col).to_dict('records')
                }

            print(f"全系統資料基準點：{d_twse}")
            print("-" * 40)

            return jsonify({
                "date": d_twse, "taiex": taiex, "summary": summary_board,
                "sectors": {
                    "buy": sorted([s for s in sector_list if s['total'] > 0], key=lambda x: x['total'], reverse=True)[:15],
                    "sell": sorted([s for s in sector_list if s['total'] < 0], key=lambda x: x['total'])[:15]
                },
                "rankings": {"total": get_ranks('total'), "foreign": get_ranks('foreign'), "trust": get_ranks('trust'), "dealer": get_ranks('dealer')}
            })
        except Exception as e:
            print(f"處理錯誤: {e}")
            continue
    

    return jsonify({"error": "No data found"}), 404

@app.route('/api/radar')
def get_radar(): return jsonify(RADAR_RESULTS)

@app.route('/api/radar_progress')
def get_radar_progress(): return jsonify({"progress": getattr(radar_select, 'PROGRESS', 0)})

if __name__ == '__main__':
    threading.Thread(target=scrape_all_yahoo_classes, daemon=True).start()
    app.run(debug=True, port=5000, use_reloader=False)