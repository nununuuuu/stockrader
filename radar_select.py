import pandas as pd
import yfinance as yf
import numpy as np
import requests
import re
from io import StringIO
import time
import warnings

warnings.filterwarnings("ignore")

PROGRESS = 0

# --- 🌟 1. 處置股監控機制 ---
def get_disposition_list():
    """抓取證交所與櫃買中心當日的處置股代碼"""
    dispo_stocks = set()
    try:
        # A. 上市處置公告
        r1 = requests.get("https://www.twse.com.tw/announcement/disposition.html", timeout=10)
        dispo_stocks.update(re.findall(r'(\d{4})', r1.text))
        # B. 上櫃處置公告 API
        r2 = requests.get("https://www.tpex.org.tw/web/stock/announcement/disposition/dispo_result.php?l=zh-tw", timeout=10)
        if r2.status_code == 200:
            for item in r2.json().get('aaData', []):
                m = re.search(r'(\d{4})', str(item))
                if m: dispo_stocks.add(m.group(1))
    except: pass
    return dispo_stocks

class ScoringStrategyEngine:
    def __init__(self, ticker, name, data, chip_info=None, is_dispo=False):
        self.ticker = ticker.split('.')[0]
        self.name = name
        self.df = data
        self.chip = chip_info or {"f": 0, "t": 0, "d": 0} 
        self.is_dispo = is_dispo

    def calculate_indicators(self):
        df = self.df.copy()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['rsi'] = round(100 - (100 / (1 + rs)), 2)
        df['sma20'] = df['Close'].rolling(window=20).mean()
        df['ema12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['signal']
        return df

    def run_scoring(self):
        if len(self.df) < 65: return None
        df = self.calculate_indicators()
        today = df.iloc[-1]
        yesterday = df.iloc[-2]

        # --- 1. 漲停偵測 ---
        change_pct = (today['Close'] - yesterday['Close']) / (yesterday['Close'] + 1e-9)
        is_limit_up = bool(change_pct >= 0.098)

        # --- 2. 狀態判定 ---
        break_count = 0
        for i in range(1, 21):
            if i > len(df) - 61: break
            target_day = df.iloc[-i]
            hist_high = df['High'].iloc[-(60+i):-i].max()
            if target_day['Close'] >= hist_high: break_count += 1
            else: break

        is_break_today = today['Close'] >= df['High'].iloc[-61:-1].max()
        is_break_yesterday = yesterday['Close'] >= df['High'].iloc[-62:-2].max()
        
        state_key = ""
        if is_break_today and not is_break_yesterday:
            state_key = "first_break"
        elif is_break_today and is_break_yesterday:
            state_key = "steady" if today['Volume'] < yesterday['Volume'] else "momentum"
        
        if not state_key: return None

        # --- 3. 七大物理條件判定 ---
        avg_vol_20d = df['Volume'].iloc[-21:-1].mean()
        vol_ratio_val = round((today['Volume'] / (avg_vol_20d + 1e-9)) * 100, 2)
        
        c1 = is_break_today
        c2 = (vol_ratio_val > 180 or is_limit_up)
        c3 = today['rsi'] > 50
        c4 = today['Close'] > today['sma20']
        
        body = round(abs(today['Close'] - today['Open']), 2)
        upper_s = round(today['High'] - max(today['Open'], today['Close']), 2)
        lower_s = round(min(today['Open'], today['Close']) - today['Low'], 2)
        
        is_hammer = (lower_s > body * 1.5) and (upper_s < body * 0.5)
        is_engulfing = (today['Close'] > today['Open'] and yesterday['Close'] < yesterday['Open'] and today['Close'] > yesterday['Open'])
        c5 = is_hammer or is_engulfing or (today['Low'] > yesterday['High'])
        c6 = today['macd_hist'] > 0
        c7 = today['Close'] >= yesterday['Close']

        if sum([c1, c2, c3, c4, c5, c6, c7]) < 4: return None

        # --- 4. 交易計畫計算 ---
        lookback_120 = df.tail(120)
        bins = np.linspace(lookback_120['Low'].min(), lookback_120['High'].max(), 25)
        vol_profile = lookback_120.groupby(pd.cut(lookback_120['Close'], bins), observed=True)['Volume'].sum()
        poc_price = round((vol_profile.idxmax().left + vol_profile.idxmax().right) / 2, 2)

        current_p = round(today['Close'], 2)
        open_p = round(today['Open'], 2)
        high_120d = round(lookback_120['High'].max(), 2)
        recent_suppo = round(df['Low'].tail(20).min(), 2)

        stop_loss = round(max(recent_suppo, open_p * 0.98), 2)
        entry_1 = round(current_p * 0.99, 2)
        entry_2 = round((current_p + open_p) / 2, 2)

        risk_pct = round(((entry_1 - stop_loss) / (entry_1 + 1e-9)) * 100, 2)
        profit_pct = round(risk_pct * 4, 2)
        take_profit = round(entry_1 * (1 + profit_pct/100), 2)

        if current_p >= high_120d:
            resis_display = f"🚀 淨空(新高) 超越前高 +{round(((current_p-high_120d)/(high_120d+1e-9)*100),2)}%"
        else:
            resis_display = f"🚩 壓力: {high_120d} [距離: +{round(((high_120d-current_p)/(current_p+1e-9)*100),2)}%]"

        # --- 5. 視覺化文字構建 (🌟 修復 initialization bug) ---
        res_text = f"{'✅' if c1 else '  '} 突破60日高 | {'✅' if c2 else '  '} 量能放大 {vol_ratio_val}% | {'✅' if c3 else '  '} RSI: {today['rsi']}\n"
        res_text += f"{'✅' if c4 else '  '} 站上月線    | {'✅' if c5 else '  '} K線型態符合    | {'✅' if c6 else '  '} MACD翻正\n"
        
        tags = []
        if upper_s > (body * 0.5) and not is_limit_up: tags.append("⚠️ 賣壓重")
        if lower_s > upper_s and lower_s > body: tags.append("⚓ 支撐強")
        
        res_text += f"{'✅' if c7 else '  '} 今日收紅    | 標記: {' | '.join(tags) if tags else '正常'}\n"
        res_text += f"> 診斷：上影線({upper_s}) / 下影線({lower_s})，壓力待消化。\n"

        f, t = self.chip['f'], self.chip['t']
        chip_line = f"🔴 土洋同買 (外:{f} / 信:{t})" if f > 0 and t > 0 else f"⚓ 投信重倉 ({t}張)" if t > 500 else "今日無顯著法人買盤"
        res_text += f"籌碼動向: {chip_line}\n"
        
        status_tags = []
        if is_limit_up: status_tags.append("🔴 漲停鎖死")
        if self.is_dispo: status_tags.append("⏳ 處置監控")
        res_text += f"特殊標記: {' | '.join(status_tags) if status_tags else '正常'}\n"

        res_text += f"\n--- 📋 交易計畫 (風報比 1:4) ---\n"
        res_text += f"🔹 進場區間: 第一批 {entry_1} (60%) / 第二批 {entry_2} (40%)\n"
        res_text += f"🚫 停損防線: {stop_loss} [預期風險: -{risk_pct}%]\n"
        res_text += f"🎯 停利目標: {take_profit} [預期報酬: +{profit_pct}%]\n"
        res_text += f"{resis_display} | ⚓ 支撐: {poc_price} [距離: -{round(((current_p-poc_price)/(current_p+1e-9)*100),2)}%]"
        
        # 權重評分
        score = 10000 if state_key == "steady" else 5000 if state_key == "momentum" else 1000
        if f > 0 and t > 0: score += 3500
        if is_limit_up: score += 2000
        if self.is_dispo: score -= 2500

        return {
            "stock_id": self.ticker, "name": self.name, "state_key": state_key,
            "price": current_p, "score": score, "break_count": break_count,
            "is_limit_up": is_limit_up, "is_disposition": self.is_dispo,
            "chip_tag": chip_line if "今日無" not in chip_line else "",
            "full_text": res_text
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

def run_radar_scan(chip_map=None):
    global PROGRESS
    PROGRESS = 0
    dispo_list = get_disposition_list()
    name_map = get_ticker_name_map()
    tickers = list(name_map.keys())
    total_count = len(tickers)
    results = {"first_break": [], "steady": [], "momentum": []}
    
    batch_size = 50
    for i in range(0, total_count, batch_size):
        PROGRESS = int((i / total_count) * 100)
        batch = tickers[i:i+batch_size]
        try:
            # 下載 1y 確保長度充足
            data = yf.download(batch, period="1y", group_by='ticker', progress=False, threads=True, auto_adjust=True)
            for ticker in batch:
                try:
                    df = data[ticker].dropna()
                    # 流動性與長度過濾
                    if len(df) < 65 or df['Volume'].tail(10).mean() < 300 * 1000: continue
                    
                    sid = ticker.split('.')[0]
                    c_info = chip_map.get(sid, {"f": 0, "t": 0, "d": 0}) if chip_map else {"f": 0, "t": 0, "d": 0}
                    
                    res = ScoringStrategyEngine(ticker, name_map[ticker], df, chip_info=c_info, is_dispo=(sid in dispo_list)).run_scoring()
                    if res: 
                        results[res['state_key']].append(res)
                except: continue
        except: continue

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