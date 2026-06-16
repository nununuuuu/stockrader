import pandas as pd
import yfinance as yf
import numpy as np
import requests
import re
import io 
import time
import warnings
import random 
from playwright.sync_api import sync_playwright


warnings.filterwarnings("ignore")

PROGRESS = 0
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}
def get_goodinfo_limit_up_with_playwright():
    """
    使用 Playwright 抓取 Goodinfo 今日漲停股代號
    """
    url = "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E6%99%BA%E6%85%A7%E9%81%B8%E8%82%A1&INDUSTRY_CAT=%E6%BC%B2%E5%81%9C%E8%82%A1"
    limit_up_set = set()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            # 等待關鍵元素載入代表解鎖成功
            page.wait_for_selector("#txtStockCode", timeout=15000)
            time.sleep(2)
            html_content = page.content()
            browser.close()
            
            if "<table" in html_content.lower():
                dfs = pd.read_html(io.StringIO(html_content))
                for df in dfs:
                    if '代號' in df.columns and '名稱' in df.columns:
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = [col[-1] for col in df.columns]
                        ids = df['代號'].astype(str).tolist()
                        limit_up_set = set([str(x).strip() for x in ids if x.isdigit()])
                        break
        print(f"📡 Goodinfo 漲停對齊成功：共 {len(limit_up_set)} 檔")
    except Exception as e:
        print(f"Goodinfo 爬取失敗: {e}")
    return limit_up_set

# --- 🌟 1. 處置股監控機制 ---
def get_disposition_list():
    """
    透過官方 OpenAPI 抓取上市、上櫃、興櫃之處置有價證券資訊。
    """
    dispo_stocks = set()
    
    # 🌟 1. 抓取上市處置股 (TWSE OpenAPI)
    try:
        res_l = requests.get("https://openapi.twse.com.tw/v1/announcement/punish", timeout=10)
        if res_l.status_code == 200:
            data = res_l.json()
            for item in data:
                sid = str(item.get('Code', '')).strip()
                if sid: dispo_stocks.add(sid)
        print("上市處置同步成功")
    except Exception as e:
        print(f"上市處置同步異常: {e}")

    # 🌟 2. 抓取上櫃處置股 (TPEX OpenAPI)
    try:
        res_o = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_disposal_information", timeout=10)
        if res_o.status_code == 200:
            data = res_o.json()
            for item in data:
                sid = str(item.get('SecuritiesCompanyCode', '')).strip()
                if sid: dispo_stocks.add(sid)
        print("上櫃處置同步成功")
    except Exception as e:
        print(f"上櫃處置同步異常: {e}")

    # 🌟 3. 抓取興櫃處置股 (TPEX OpenAPI)
    try:
        res_e = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_esb_disposal_information", timeout=10)
        if res_e.status_code == 200:
            data = res_e.json()
            for item in data:
                sid = str(item.get('證券代號', '')).strip()
                if sid: dispo_stocks.add(sid)
        print("興櫃處置同步成功")
    except Exception as e:
        print(f"興櫃處置同步異常: {e}")

    total_count = len(dispo_stocks)
    print(f"處置監控： {total_count} 檔處置股列入追蹤。")
    return dispo_stocks

class ScoringStrategyEngine:
    def __init__(self, ticker, name, data, chip_info=None, is_dispo=False, top_sectors=None, sector_name="", limit_up_set=None):
        self.ticker = ticker.split('.')[0]
        self.name = name
        self.df = data
        self.chip = chip_info or {"f": 0, "t": 0, "d": 0} 
        self.is_dispo = is_dispo
        self.top_sectors = top_sectors or []
        self.sector_name = sector_name
        self.limit_up_set = limit_up_set or set() # 🌟 儲存名單


    def calculate_indicators(self):
        df = self.df.copy()
        df['sma20'] = df['Close'].rolling(window=20).mean()
        df['sma60'] = df['Close'].rolling(window=60).mean()
        df['sma200'] = df['Close'].rolling(window=200).mean()
        # 布林帶
        std = df['Close'].rolling(window=20).std()
        df['bb_up'] = df['sma20'] + (2 * std)
        df['bb_bw'] = (df['bb_up'] - (df['sma20'] - (2 * std))) / (df['sma20'] + 1e-9)
        # MACD & RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
        df['ema12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['macd_hist'] = (df['ema12'] - df['ema26']) - (df['ema12'] - df['ema26']).ewm(span=9, adjust=False).mean()
        return df

    def run_scoring(self):
        # --- [優化 1] 基礎數據長度 ---
        if len(self.df) < 120: return None 
        df = self.calculate_indicators()
        today, yesterday = df.iloc[-1], df.iloc[-2]

        current_p = round(float(today['Close']), 2)
        open_p = round(float(today['Open']), 2)
        prev_close = float(yesterday['Close'])
        
        # --- [優化 2] 稍微放寬硬性門檻 ---
        # 1. 均量降至 500 張 (1000張在台股太嚴，會漏掉很多爆發小飆股)
        if df['Volume'].tail(10).mean() < 500 * 1000: return None
        # 2. 趨勢過濾：保留年線之上
        if current_p < today['sma200']: return None
        is_limit_up = self.ticker in self.limit_up_set

        
        # 3. 上影線過濾 (只過濾極端誇張的壓制)
        body = abs(current_p - open_p)
        upper_shadow = today['High'] - max(current_p, open_p)
        if upper_shadow > body * 1.5 and current_p/prev_close < 1.09: return None

        avg_vol_20d = df['Volume'].iloc[-21:-1].mean()
        vol_ratio = (today['Volume'] / (avg_vol_20d + 1e-9)) * 100
        
        # --- 🚀 8 大模型偵測 ---
        triggered = []

        # 1. 物理實戰版 (要求量比更高 200%)
        hist_h_60 = float(df['High'].iloc[-61:-1].max())
        if current_p >= hist_h_60 and vol_ratio > 180: triggered.append("物理實戰")

        # 2. VCP 收斂突破 (收緊收縮比例 0.6 -> 0.5)
        recent_std = df['Close'].tail(10).std()
        prev_std = df['Close'].iloc[-40:-10].std()
        if recent_std < prev_std * 0.5: triggered.append("VCP收斂")

        # 3. 布林基礎版
        if current_p > today['bb_up']:
            triggered.append("布林基礎")

        # 4. 布林 SBA (收緊帶寬 0.12 -> 0.1)
        if current_p > today['bb_up'] and today['bb_bw'] < 0.10:
            triggered.append("布林SBA")

        # 5. 形態學標準版
        pivot_120 = float(df['High'].iloc[-121:-1].max())
        if current_p >= pivot_120:
            triggered.append("形態標準")

        # 6. 形態學進階版 (自帶年線過濾)
        if current_p >= pivot_120 and current_p > today['sma200']:
            triggered.append("形態進階")

        # 🌟 族群連動 (增加籌碼過濾：法人必須有買)
        is_in_hot_sector = self.sector_name in self.top_sectors
        # 如果籌碼有對齊就檢查，沒對齊就視為通過
        inst_buying = (self.chip['f'] > 50 or self.chip['t'] > 50) if self.chip['f'] != 0 else True
        
        # 7. 族群連動第一版
        if is_in_hot_sector and inst_buying and today['Volume'] < yesterday['Volume'] * 1.2:
            triggered.append("族群連動V1")

        # 8. 族群連動新版
        if is_in_hot_sector and inst_buying and (vol_ratio > 250 or current_p/prev_close > 1.05):
            triggered.append("族群連動New")

        # --- [優化 3] 關鍵：【多模型共振】門檻 ---
        if len(triggered) < 2 and not is_limit_up: return None

        # --- 狀態與計數 (對應原 V5.5.9 格式) ---
        state_key = "first_break" if current_p >= hist_h_60 and yesterday['Close'] < float(df['High'].iloc[-62:-2].max()) else "momentum"
        if state_key == "momentum" and today['Volume'] < yesterday['Volume']: state_key = "steady"
        
        break_count = 0
        for i in range(1, 21):
            if i > len(df)-61: break
            t = df.iloc[-(i)]
            if t['Close'] > t['sma20']: break_count += 1
            else: break

        stop_loss = round(max(df['Low'].tail(20).min(), open_p * 0.98), 2)
        entry_1 = round(current_p * 0.99, 2)
        risk_pct = round(((entry_1 - stop_loss) / (entry_1 + 1e-9)) * 100, 2)
        take_profit = round(entry_1 * (1 + (risk_pct * 4)/100), 2)

        # --- 視覺化輸出 ---
        is_resonance = len(triggered) >= 2
        res_text = f"核心觸發: {' + '.join(triggered)}\n"
        res_text += f"量能比: {round(vol_ratio)}% | RSI: {round(today['rsi'],2)}\n"
        
        tags = []
        if self.is_dispo: tags.append("⏳ 處置監控")
        
        money_tags = []
        if is_in_hot_sector: money_tags.append("🌊 資金主戰場")
        if self.chip['t'] > 500: money_tags.append("⚓ 投信重倉")

        res_text += f"籌碼: 外{int(self.chip['f'])}/信{int(self.chip['t'])}\n"
        res_text += f"\n--- 📋 明日實戰交易計畫 (風報比 1:4) ---\n"
        res_text += f"🔹 進場區間: 第一批 {entry_1} / 第二批 {round((current_p+open_p)/2,2)}\n"
        res_text += f"🚫 停損防線: {stop_loss} [-{risk_pct}%] | 🎯 停利: {take_profit}\n"
        res_text += f"⚓ 支撐(POC): {round((df['Close'].tail(120).min()+df['Close'].tail(120).max())/2,2)}"

        # 評分系統
        score = len(triggered) * 3000
        if inst_buying: score += 2000
        if is_limit_up: score += 1000

        return {
            "stock_id": self.ticker, "name": self.name, "state_key": state_key,
            "price": current_p, "score": score, "break_count": break_count,
            "is_disposition": self.is_dispo,
            "is_limit_up": is_limit_up,           
            "money_label": " | ".join(money_tags), 
            "chip_tag": " + ".join(triggered[:2]),
            "chip_tag": "多模型共振" if is_resonance else (triggered[0] if triggered else "動能突破"),
            "full_text": res_text
        }

def get_ticker_name_map():
    """獲取完整的上市與上櫃名稱對應表"""
    name_map = {}
    try:
        # 上市
        r_l = requests.get("https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv")
        l_df = pd.read_csv(io.StringIO(r_l.content.decode('utf-8-sig')))
        for _, row in l_df.iterrows():
            name_map[f"{str(int(row['公司代號']))}.TW"] = row['公司簡稱']
        # 上櫃
        r_o = requests.get("https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv")
        o_df = pd.read_csv(io.StringIO(r_o.content.decode('utf-8-sig')))
        for _, row in o_df.iterrows():
            name_map[f"{str(int(row['公司代號']))}.TWO"] = row['公司簡稱']
    except: pass
    return name_map

def run_radar_scan(chip_map=None, top_sectors=None, industry_db=None):
    global PROGRESS
    PROGRESS = 0
    limit_up_set = get_goodinfo_limit_up_with_playwright()
    dispo_list = get_disposition_list()
    name_map = get_ticker_name_map()
    tickers = list(name_map.keys())
    total_count = len(tickers)
    results = {"first_break": [], "steady": [], "momentum": []}
    
    batch_size = 30
    session = requests.Session()
    session.headers.update(HEADERS) # 使用我們原本定義的瀏覽器標頭

    for i in range(0, total_count, batch_size):
        PROGRESS = int((i / total_count) * 100)
        batch = tickers[i:i+batch_size]
        try:
            # 🌟 3. 下載時傳入 session，並關閉多線程 (threads=False 更不易被鎖)
            data = yf.download(
                batch, 
                period="1y", 
                group_by='ticker', 
                progress=False, 
                threads=True,  # 開啟多線程下載，yf 會處理並發
                auto_adjust=False
            )
            for ticker in batch:
                try:
                    # 檢查資料是否完整
                    if ticker not in data or data[ticker].empty:
                        continue
                        
                    df = data[ticker].dropna()
                    if len(df) < 65: continue
                    
                    # 流動性過濾 (成交量)
                    if df['Volume'].tail(10).mean() < 300 * 1000: continue
                    
                    sid = ticker.split('.')[0]
                    c_info = chip_map.get(sid) if chip_map else None
                    id_info = industry_db.get(sid, {}) if industry_db else {}
                    sec_name = id_info.get('electronics') or id_info.get('concepts') or id_info.get('group') or id_info.get('basic') or ""
                    
                    res = ScoringStrategyEngine(
                        ticker, name_map[ticker], df, 
                        chip_info=c_info, 
                        is_dispo=(sid in dispo_list), 
                        top_sectors=top_sectors, 
                        sector_name=sec_name,
                        limit_up_set=limit_up_set
                    ).run_scoring()
                    
                    if res: results[res['state_key']].append(res)
                except: continue
            print(f"已完成 {i}/{total_count}，進度: {PROGRESS}%")
            time.sleep(random.uniform(2.0, 4.0))             
        except Exception as e:
            print(f"⚠️ 下載批次 {i} 失敗: {e}")
            time.sleep(15) # 萬一出錯，休息久一點再繼續
            continue

    for k in results: results[k].sort(key=lambda x: x['score'], reverse=True)
    
    hit_count = sum(len(v) for v in results.values())
    hit_rate = round((hit_count / total_count) * 100, 2) if total_count > 0 else 0
    scan_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
    
    display_summary = f"今日篩選率: {hit_rate}% | 掃描時間: {scan_time_str}"
    print(f"\n✅ 掃描完成: {display_summary}")

    PROGRESS = 100
    return {
        "groups": results,
        "stats": {
            "hit_rate": f"{hit_rate}%",
            "scan_time": scan_time_str,
            "hit_count": hit_count,
            "total_count": total_count,
            "display_summary": display_summary
        }
    }