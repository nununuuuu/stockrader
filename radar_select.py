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
    except Exception as e:
        print(f"興櫃處置同步異常: {e}")

    total_count = len(dispo_stocks)
    print(f"處置監控： {total_count} 檔處置股列入追蹤。")
    return dispo_stocks

class ScoringStrategyEngine:
    def __init__(self, ticker, name, data, chip_info=None, is_dispo=False, 
                 top_vc_keys=None, vc_paths=None, limit_up_set=None, vc_mgr=None):
        """
        top_vc_keys: 傳入當日 Valuechain 資金力道最強的前幾名 Key (例如: "半導體::IC/晶圓製造")
        vc_paths: 該個股在 Valuechain 中的所有分類路徑列表
        vc_mgr: valuechainManager 實例，用來把 vc_paths 轉換成分組 Key (_valuechain_group_key)
        """
        self.ticker = ticker.split('.')[0]
        self.name = name
        self.df = data
        self.chip = chip_info or {"f": 0, "t": 0, "d": 0} 
        self.is_dispo = is_dispo
        self.top_vc_keys = top_vc_keys or []
        self.vc_paths = vc_paths or [] #
        self.limit_up_set = limit_up_set or set()
        # 🌟 修正：run_radar_scan() 呼叫時有傳入 vc_mgr=vc_mgr，但先前這裡沒有宣告/儲存此參數，
        # 會導致 TypeError（未知的關鍵字參數）；即使加了參數，run_scoring() 內用到 self.vc_mgr
        # 也一定會 AttributeError。這裡一併補上。
        self.vc_mgr = vc_mgr


    def calculate_indicators(self):
        df = self.df.copy()
        # 1. 均線系統
        df['sma20'] = df['Close'].rolling(window=20).mean()
        df['sma200'] = df['Close'].rolling(window=200).mean()
        
        # 2. 布林帶 (20, 2)
        std = df['Close'].rolling(window=20).std()
        df['bb_up'] = df['sma20'] + (2 * std)
        df['bb_bw'] = (df['bb_up'] - (df['sma20'] - (2 * std))) / (df['sma20'] + 1e-9)
        
        # 3. RSI 6 (短線爆發力)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
        df['rsi6'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
        
        # 4. KDJ (9, 3, 3)
        low_min = df['Low'].rolling(window=9).min()
        high_max = df['High'].rolling(window=9).max()
        df['rsv'] = (df['Close'] - low_min) / (high_max - low_min + 1e-9) * 100
        df['k'] = df['rsv'].ewm(com=2, adjust=False).mean()
        df['d'] = df['k'].ewm(com=2, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']
        
        return df

    def run_scoring(self):
        if len(self.df) < 120: return None 
        df = self.calculate_indicators()
        today, yesterday = df.iloc[-1], df.iloc[-2]

        current_p = round(float(today['Close']), 2)
        open_p = round(float(today['Open']), 2)
        prev_close = float(yesterday['Close'])
        
        # --- [1] 硬性過濾 ---
        if df['Volume'].tail(10).mean() < 500 * 1000: return None
        if current_p < today['sma200']: return None
        
        # 上影線過濾 (確保收盤紮實度)
        body = abs(current_p - open_p)
        upper_shadow = today['High'] - max(current_p, open_p)
        if upper_shadow > body * 0.8 and current_p/prev_close < 1.09: return None

        avg_vol_20d = df['Volume'].iloc[-21:-1].mean()
        vol_ratio = (today['Volume'] / (avg_vol_20d + 1e-9)) * 100
        is_limit_up = self.ticker in self.limit_up_set

        # --- [2] 取得個股 Valuechain 群組 ---
        my_vc_keys = []
        if self.vc_mgr:
            for p in self.vc_paths:
                k = self.vc_mgr._valuechain_group_key(p)
                my_vc_keys.append(k)

        # 🌟 族群連動背景 (檢查所屬任一分類是否屬當日熱門)
        # 修正：app.py 在 valuechain 尚未算好時，會用 top_sectors 的「純子分類名稱」組出
        # 暫用的 top_vc_keys（而非 valuechain.py 產生的 "主分類::子分類" 完整 Key），
        # 兩邊格式對不上會導致這裡永遠比對不到。這裡同時比對完整 Key 與「::」後半段的子分類名稱。
        is_in_hot_sector = any(
            k in self.top_vc_keys or k.split("::")[-1] in self.top_vc_keys
            for k in my_vc_keys
        )
        # 法人條件 (買超 > 80 張)
        inst_buying = (self.chip['f'] > 80 or self.chip['t'] > 80) if self.chip['f'] != 0 else True
        
        # --- [3] 8 大模型偵測 ---
        triggered = []
        recent_h_5 = float(df['High'].iloc[-6:-1].max())  # 過去 5 天最高點
        avg_vol_5d = df['Volume'].iloc[-6:-1].mean()

        # 1. 物理實戰版 (要求量比更高)
        hist_h_60 = float(df['High'].iloc[-61:-1].max())
        if current_p >= hist_h_60 and vol_ratio > 180: triggered.append("物理實戰")

        # 2. VCP 收斂突破
        if df['Close'].tail(10).std() < df['Close'].iloc[-40:-10].std() * 0.5: triggered.append("VCP收斂")

        # 3. 布林基礎版
        if current_p > today['bb_up']: triggered.append("布林基礎")

        # 4. 布林 SBA 
        if current_p > today['bb_up'] and today['bb_bw'] < 0.10: triggered.append("布林SBA")

        # 5. 形態學標準版
        pivot_120 = float(df['High'].iloc[-121:-1].max())
        if current_p >= pivot_120: triggered.append("形態標準")

        # 6. 形態學進階版
        if current_p >= pivot_120 and current_p > today['sma200']: triggered.append("形態進階")

        # 7. 族群連動V1 (潛伏)
        if is_in_hot_sector and inst_buying and today['Volume'] < yesterday['Volume'] * 1.2:
            triggered.append("族群連動V1")

        # 8. 🌟 族群連動新版 (優化：突破 5 日高 + 量能)
        if is_in_hot_sector and inst_buying and current_p > recent_h_5 and vol_ratio > 220:
            triggered.append("族群連動New")

        # --- [4] RSI/KDJ 提示 (不需取消選入) ---
        hints = []
        if today['rsi6'] > 85: hints.append("⚠️RSI過熱")
        elif today['rsi6'] > 70: hints.append("🔥動能強勁")
        
        if today['j'] > 100: hints.append("⚡J值乖離")
        if yesterday['k'] < yesterday['d'] and today['k'] > today['d']: hints.append("✅KDJ金叉")

        # --- [5] 共振門檻 (移除漲停免死金牌) ---
        # 任何股票(含漲停)都必須符合至少 2 個模型
        if len(triggered) < 2: return None

        # --- [6] 狀態與計畫計算 ---
        state_key = "first_break" if current_p > recent_h_5 and yesterday['Close'] <= recent_h_5 else "momentum"
        stop_loss = round(max(df['Low'].tail(20).min(), open_p * 0.98), 2)
        risk_pct = round(((current_p - stop_loss) / (current_p + 1e-9)) * 100, 2)
        take_profit = round(current_p * (1 + (risk_pct * 4)/100), 2)

        # 分數權重
        score = len(triggered) * 1000 + (2000 if inst_buying else 0) + (1000 if is_limit_up else 0)

        return {
            "stock_id": self.ticker, "name": self.name, "state_key": state_key,
            "price": current_p, "score": score, "my_vc_keys": my_vc_keys,
            "is_disposition": self.is_dispo, "is_limit_up": is_limit_up,           
            "hints": hints, "models": triggered,
            "full_text": f"觸發: {' + '.join(triggered)}\n提示: {' | '.join(hints)}\n量比: {int(vol_ratio)}% | RSI6: {int(today['rsi6'])}\n明日計畫: 進場 {current_p} / 停損 {stop_loss} / 停利 {take_profit}"
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

def run_radar_scan(chip_map=None, valuechain_result=None, vc_mgr=None, industry_db=None):
    global PROGRESS
    PROGRESS = 0
    limit_up_set = get_goodinfo_limit_up_with_playwright()
    dispo_list = get_disposition_list()
    name_map = get_ticker_name_map()
    tickers = list(name_map.keys())
    
    # 提取 Valuechain 熱門產業 Key
    # 修正：app.py 的 run_radar_background() 在 valuechain 尚未算好時，會用純子分類名稱
    # 組出格式不同的暫用 Key（例如 "類別::IC設計" 而非正式的 "半導體::IC設計"）。
    # 這裡把完整 Key 與「::」後半段的子分類名稱都放進集合，讓兩種格式都能互相比對成功。
    top_vc_keys = set()
    if valuechain_result:
        raw_keys = [x['key'] for x in (valuechain_result.get('top5', []) + valuechain_result.get('others', [])[:10])]
        for k in raw_keys:
            top_vc_keys.add(k)
            top_vc_keys.add(k.split("::")[-1])

    raw_hits = []
    batch_size = 35

    # --- 第一階段：模型篩選 ---
    for i in range(0, len(tickers), batch_size):
        PROGRESS = int((i / len(tickers)) * 80)
        batch = tickers[i:i+batch_size]
        try:
            data = yf.download(batch, period="1y", group_by='ticker', progress=False, threads=True)
            for ticker in batch:
                if ticker not in data or data[ticker].empty: continue
                sid = ticker.split('.')[0]
                my_paths = vc_mgr.valuechain_map.get(sid, []) if vc_mgr else []
                
                res = ScoringStrategyEngine(
                    ticker, name_map[ticker], data[ticker].dropna(), 
                    chip_info=chip_map.get(sid) if chip_map else None, 
                    is_dispo=(sid in dispo_list), 
                    top_vc_keys=top_vc_keys,
                    vc_paths=my_paths,
                    limit_up_set=limit_up_set,
                    vc_mgr=vc_mgr
                ).run_scoring()
                
                if res: raw_hits.append(res)
            time.sleep(random.uniform(2, 4))
        except: continue

    # --- 第二階段：Valuechain 族群共振統計 ---
    PROGRESS = 90
    vc_group_counts = {}
    for hit in raw_hits:
        for k in hit['my_vc_keys']:
            vc_group_counts[k] = vc_group_counts.get(k, 0) + 1

    # --- 第三階段：標籤注入與格式化 ---
    results = {"first_break": [], "steady": [], "momentum": []}
    for hit in raw_hits:
        # 尋找最強共振路徑
        best_sub_name = ""
        max_n = 0
        for k in hit['my_vc_keys']:
            n = vc_group_counts.get(k, 0)
            if n > max_n:
                max_n = n
                best_sub_name = k.split('::')[-1] # 取 "半導體::IC製造" 的 "IC製造"

        # 🌟 組合名稱旁的小標籤 (chip_tag)
        display_tags = []
        # a. 顯示第一個模型
        if hit['models']: display_tags.append(hit['models'][0])
        # b. 顯示第一個動能提示
        if hit['hints']: display_tags.append(hit['hints'][0])
        # c. 顯示 Valuechain 共振標籤
        if max_n >= 3:
            display_tags.append(f"🌊{best_sub_name}({max_n})")
            hit['score'] += 500 # 共振加分

        hit['chip_tag'] = " + ".join(display_tags)
        results[hit['state_key']].append(hit)

    for k in results: results[k].sort(key=lambda x: x['score'], reverse=True)
    PROGRESS = 100
    return {"groups": results, "stats": {"hit_count": len(raw_hits)}}