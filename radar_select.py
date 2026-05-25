import pandas as pd
import yfinance as yf
import numpy as np
import requests
import re
from io import StringIO
import time
import warnings
import random 

warnings.filterwarnings("ignore")

PROGRESS = 0
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}
# --- 🌟 1. 處置股監控機制 ---
def get_disposition_list():
    """
    透過官方 OpenAPI 抓取上市、上櫃、興櫃之處置有價證券資訊。
    """
    dispo_stocks = set()
    
    # 🌟 1. 抓取上市處置股 (TWSE OpenAPI)
    try:
        # API 欄位包含: Code (證券代號), Name, DispositionPeriod...
        res_l = requests.get("https://openapi.twse.com.tw/v1/announcement/punish", timeout=10)
        if res_l.status_code == 200:
            data = res_l.json()
            for item in data:
                # 根據圖一，欄位名稱為 'Code'
                sid = str(item.get('Code', '')).strip()
                if sid: dispo_stocks.add(sid)
        print("上市處置同步成功")
    except Exception as e:
        print(f"上市處置同步異常: {e}")

    # 🌟 2. 抓取上櫃處置股 (TPEX OpenAPI)
    try:
        # API 欄位包含: SecuritiesCompanyCode (證券代號), CompanyName...
        res_o = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_disposal_information", timeout=10)
        if res_o.status_code == 200:
            data = res_o.json()
            for item in data:
                # 根據圖二，欄位名稱為 'SecuritiesCompanyCode'
                sid = str(item.get('SecuritiesCompanyCode', '')).strip()
                if sid: dispo_stocks.add(sid)
        print("上櫃處置同步成功")
    except Exception as e:
        print(f"上櫃處置同步異常: {e}")

    # 🌟 3. 抓取興櫃處置股 (TPEX OpenAPI)
    try:
        # API 欄位包含: 證券代號, 證券名稱, 處置內容...
        res_e = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_esb_disposal_information", timeout=10)
        if res_e.status_code == 200:
            data = res_e.json()
            for item in data:
                # 根據圖三，欄位名稱為 '證券代號'
                sid = str(item.get('證券代號', '')).strip()
                if sid: dispo_stocks.add(sid)
        print("興櫃處置同步成功")
    except Exception as e:
        print(f"興櫃處置同步異常: {e}")

    total_count = len(dispo_stocks)
    print(f"處置監控： {total_count} 檔處置股列入追蹤。")
    return dispo_stocks

class ScoringStrategyEngine:
    def __init__(self, ticker, name, data, chip_info=None, is_dispo=False, top_sectors=None, sector_name=""):
        self.ticker = ticker.split('.')[0]
        self.name = name
        self.df = data
        self.chip = chip_info or {"f": 0, "t": 0, "d": 0} 
        self.is_dispo = is_dispo
        self.top_sectors = top_sectors or []
        self.sector_name = sector_name

    def calculate_indicators(self):
        df = self.df.copy()
        # 均線系統
        df['sma5'] = df['Close'].rolling(window=5).mean()
        df['sma20'] = df['Close'].rolling(window=20).mean()
        df['sma60'] = df['Close'].rolling(window=60).mean()
        # RSI 與 MACD
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
        df['ema12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['macd_hist'] = (df['ema12'] - df['ema26']) - (df['ema12'] - df['ema26']).ewm(span=9, adjust=False).mean()
        return df

    def run_scoring(self):
        if len(self.df) < 65: return None
        df = self.calculate_indicators()
        today, yesterday = df.iloc[-1], df.iloc[-2]

        # 🌟 價格與漲幅變數 (修正偏差)
        current_p = round(float(today['Close']), 2)
        open_p = round(float(today['Open']), 2)
        high_p = float(today['High'])
        low_p = float(today['Low'])
        prev_close = float(yesterday['Close'])
        prev_open = float(yesterday['Open'])
        
        change_pct = (current_p - prev_close) / (prev_close + 1e-9)
        is_limit_up = bool(change_pct >= 0.098)

        # 1. 硬性過濾：均線多頭排列
        is_long = (current_p > today['sma5'] > today['sma20'] > today['sma60'])
        is_slope_up = (today['sma20'] > yesterday['sma20'] and today['sma60'] > yesterday['sma60'])
        if not (is_long and is_slope_up): return None

        # 2. 方案 B：箱體收斂判定
        lookback_20 = df.tail(20)
        box_h, box_l = float(lookback_20['High'].max()), float(lookback_20['Low'].min())
        base_width = (box_h - box_l) / (box_l + 1e-9)
        is_flat_base = bool(base_width < 0.12)

        # 3. 狀態判定 (60日高突破)
        hist_h_60 = float(df['High'].iloc[-61:-1].max())
        is_break = bool(current_p >= hist_h_60)
        
        # 突破天數
        break_count = 0
        
        # 準備好均線數據供迴圈讀取
        sma5_s = df['Close'].rolling(window=5).mean()
        sma20_s = df['Close'].rolling(window=20).mean()
        sma60_s = df['Close'].rolling(window=60).mean()

        for i in range(0, 60): # 最多追蹤 60 天
            if (i + 61) > len(df): break
            
            idx = -(i + 1)
            c = float(df['Close'].iloc[idx])
            m5 = float(sma5_s.iloc[idx])
            m20 = float(sma20_s.iloc[idx])
            m60 = float(sma60_s.iloc[idx])
            
            # 🌟 判定那一天是否符合「多頭跑道」標準
            # 條件：收盤 > 5MA > 20MA > 60MA
            if c > m5 > m20 > m60:
                break_count += 1
            else:
                break
        
        state_key = ""
        if is_break and prev_close < float(df['High'].iloc[-62:-2].max()):
            state_key = "first_break"
        elif is_break:
            state_key = "steady" if today['Volume'] < yesterday['Volume'] else "momentum"
        
        if not state_key: return None

        # 4. 七大物理條件與 K 線型態細節
        avg_vol_20d = df['Volume'].iloc[-21:-1].mean()
        vol_ratio_val = round((today['Volume'] / (avg_vol_20d + 1e-9)) * 100, 2)
        
        c1 = is_break
        c2 = (vol_ratio_val > 150 or is_limit_up)
        c3 = today['rsi'] > 50
        c4 = current_p > today['sma20']
        
        body = round(abs(current_p - open_p), 2)
        upper_s = round(high_p - max(open_p, current_p), 2)
        lower_s = round(min(open_p, current_p) - low_p, 2)
        
        is_hammer = (lower_s > body * 1.5) and (upper_s < body * 0.5)
        is_engulfing = (current_p > open_p and prev_close < prev_open and current_p > prev_open)
        c5 = is_hammer or is_engulfing or (low_p > float(yesterday['High']))
        c6 = today['macd_hist'] > 0
        c7 = current_p >= prev_close

        if sum([c1, c2, c3, c4, c5, c6, c7]) < 4: return None

        # 5. 籌碼 POC 與 實戰交易計畫 (還原圖二功能)
        lookback_120 = df.tail(120)
        bins = np.linspace(lookback_120['Low'].min(), lookback_120['High'].max(), 25)
        vol_profile = lookback_120.groupby(pd.cut(lookback_120['Close'], bins), observed=True)['Volume'].sum()
        poc_price = round((vol_profile.idxmax().left + vol_profile.idxmax().right) / 2, 2)
        high_120d = round(lookback_120['High'].max(), 2)
        recent_suppo = round(df['Low'].tail(20).min(), 2)

        stop_loss = round(max(recent_suppo, open_p * 0.98), 2)
        entry_1 = round(current_p * 0.99, 2)
        entry_2 = round((current_p + open_p) / 2, 2)
        risk_pct = round(((entry_1 - stop_loss) / (entry_1 + 1e-9)) * 100, 2)
        profit_pct = round(risk_pct * 4, 2)
        take_profit = round(entry_1 * (1 + profit_pct/100), 2)

        if current_p >= high_120d:
            break_dist = round(((current_p - high_120d) / (high_120d + 1e-9)) * 100, 2)
            resis_display = f"🚀 淨空(新高) 超越前高 +{break_dist}%"
        else:
            resis_dist = round(((high_120d - current_p) / (current_p + 1e-9)) * 100, 2)
            resis_display = f"🚩 壓力: {high_120d} [距離: +{resis_dist}%]"

        # 6. 視覺化文字構建 (完全還原)
        res_text = f"{'✅' if c1 else '  '} 突破60日高 | {'✅' if c2 else '  '} 量能放大 {vol_ratio_val}% | {'✅' if c3 else '  '} RSI: {round(float(today['rsi']),2)}\n"
        res_text += f"{'✅' if c4 else '  '} 站上月線    | {'✅' if c5 else '  '} K線型態符合    | {'✅' if c6 else '  '} MACD翻正\n"
        
        tags = []
        diag_msg = f"上影線({upper_s}) / 下影線({lower_s})，壓力待消化。"
        if upper_s > (body * 0.5) and not is_limit_up: tags.append("⚠️ 賣壓重")
        if lower_s > upper_s and lower_s > body: 
            tags.append("⚓ 支撐強")
            diag_msg = "下影線強力支撐，回測有守。"
        
        # 籌碼與族群共振標籤
        f, t = float(self.chip['f']), float(self.chip['t'])
        chip_line = f"🔴 土洋同買 (外:{int(f)} / 信:{int(t)})" if f > 0 and t > 0 else f"⚓ 投信重倉 ({int(t)}張)" if t > 500 else "今日無顯著法人買盤"
        
        status_tags = []
        if is_limit_up: status_tags.append("🔴 漲停")
        if self.is_dispo: status_tags.append("⏳ 處置監控")
        if self.sector_name in self.top_sectors: status_tags.append("🌊 資金主戰場")
        if is_flat_base: status_tags.append("💎 箱體突破")

        res_text += f"{'✅' if c7 else '  '} 今日收紅    | 標記: {' | '.join(tags) if tags else '正常'}\n"
        res_text += f"> 診斷：{diag_msg}\n"
        res_text += f"籌碼動向: {chip_line}\n"
        res_text += f"特殊標記: {' | '.join(status_tags) if status_tags else '正常'}\n"

        res_text += f"\n--- 📋 明日實戰交易計畫 (風報比 1:4) ---\n"
        res_text += f"🔹 進場區間: 第一批 {entry_1} (60%) / 第二批 {entry_2} (40%)\n"
        res_text += f"🚫 停損防線: {stop_loss} [預期風險: -{risk_pct}%]\n"
        res_text += f"🎯 停利目標: {take_profit} [預期報酬: +{profit_pct}%]\n"
        res_text += f"{resis_display} | ⚓ 支撐: {poc_price} [距離: -{round(((current_p-poc_price)/(current_p+1e-9)*100),2)}%]"
        
        # 7. 權重評分系統
        score = 5000 if state_key == "first_break" else 2000
        if 0.04 <= change_pct <= 0.08: score += 6000
        elif is_limit_up: score -= 8000 
        if is_flat_base: score += 5000
        if f > 0 and t > 0: score += 3500
        
        if state_key == "first_break":
            break_count = 1

        return {
            "stock_id": str(self.ticker), "name": str(self.name), "state_key": str(state_key),
            "price": float(current_p), "score": int(score), "break_count": int(break_count),
            "is_limit_up": is_limit_up, "is_disposition": bool(self.is_dispo),
            "chip_tag": str(status_tags[0]) if status_tags else "",
            "full_text": str(res_text)
        }

def get_ticker_name_map():
    """獲取完整的上市與上櫃名稱對應表"""
    name_map = {}
    try:
        # 上市
        r_l = requests.get("https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv")
        l_df = pd.read_csv(StringIO(r_l.content.decode('utf-8-sig')))
        for _, row in l_df.iterrows():
            name_map[f"{str(int(row['公司代號']))}.TW"] = row['公司簡稱']
        # 上櫃
        r_o = requests.get("https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv")
        o_df = pd.read_csv(StringIO(r_o.content.decode('utf-8-sig')))
        for _, row in o_df.iterrows():
            name_map[f"{str(int(row['公司代號']))}.TWO"] = row['公司簡稱']
    except: pass
    return name_map

def run_radar_scan(chip_map=None, top_sectors=None, industry_db=None):
    global PROGRESS
    PROGRESS = 0
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
                        sector_name=sec_name
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