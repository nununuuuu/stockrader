import requests
import pandas as pd
import io
import re
import json
import os
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class HotIndustryManager:
    def __init__(self, industry_db, cache_file="industry_value_chain.json"):
        """ 
        industry_db: 傳入主程式的 GLOBAL_STOCK_DB (Yahoo 標籤)
        cache_file: 儲存櫃買中心詳細價值鏈地圖的本地檔案
        """
        self.industry_db = industry_db
        self.cache_file = cache_file
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        self.value_chain_map = {} # 存放櫃買中心的詳細地圖
        self.last_update_date = ""

        # 47 個產業代碼配置
        self.ic_config = {
            'D000': '半導體', 'C100': '製藥', 'C200': '醫療器材', 'C300': '食品生技', 'C400': '再生醫療',
            'A300': '電動車輛', 'A200': 'LED照明', 'A100': '太陽能', 'AB10': '汽電共生', 'AB20': '風力發電',
            'E000': '能源元件', 'AD10': '智慧電網', '5100': '區塊鏈', '5200': '金融科技', '5300': '人工智慧',
            '5400': '雲端運算', '5500': '資通訊安全', '5600': '大數據', '5700': '體驗科技', '5800': '運動科技',
            '4100': '太空衛星', '6000': '自動化', 'B000': '休閒娛樂', 'L000': '印刷電路板', 'R300': '電子商務',
            'J000': '被動元件', 'I000': '通信網路', 'K000': '連接器', 'F000': '電腦及週邊設備', 'G000': '平面顯示器',
            'H000': '觸控面板', '1000': '水泥', 'M000': '食品', 'N000': '石化及塑橡膠', 'O000': '紡織',
            'P000': '電機機械', '2000': '造紙', 'Q000': '鋼鐵', '3000': '汽車', 'R000': '軟體服務',
            'S000': '建材營造', 'T000': '交通運輸及航運', 'U000': '金融', 'V000': '貿易百貨', 'W000': '油電燃氣',
            'Y000': '文化創意', 'X000': '其他'
        }
        
        # 初始化載入
        self._load_cache_or_check_update()

    # --- 內部輔助工具 ---

    def _clean_num(self, val):
        if val is None: return 0.0
        try: return float(str(val).replace(',', '').replace('"', '').strip())
        except: return 0.0

    def _get_session(self):
        s = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        s.mount('https://', HTTPAdapter(max_retries=retries))
        return s

    # --- 核心快取邏輯 ---

    def _load_cache_or_check_update(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.last_update_date = cache_data.get("update_date", "2000-01-01")
                    
                    last_dt = datetime.strptime(self.last_update_date, "%Y-%m-%d")
                    if datetime.now() - last_dt < timedelta(days=90):
                        self.value_chain_map = cache_data.get("map", {})
                        print(f"[HotMap] 載入本地產業地圖 (上次更新: {self.last_update_date})")
                        return
                    else:
                        print(f"[HotMap] 地圖資料已過期 (上次更新: {self.last_update_date})，啟動背景更新...")
                        import threading
                        threading.Thread(target=self.run_full_update, daemon=True).start()
            except:
                print("❌ [HotMap] 讀取快取失敗")
        
        # 若沒檔案或過期，不主動啟動以免阻塞 Flask 啟動，改由 get_hot_industry_data 觸發或手動按鈕
        print("[HotMap] 需手動或自動啟動價值鏈爬蟲更新數據")

    def run_full_update(self, progress_cb=None):
        """ 執行完整爬蟲 (V22 標籤流解析法) 並存檔 """
        print("🚀 [HotMap] 啟動全台股價值鏈地圖同步 (預計 2-3 分鐘)...")
        session = self._get_session()
        new_map = {}
        dedup = set()
        total_ics = len(self.ic_config)


        for idx, (ic_code, ic_name) in enumerate(self.ic_config.items()):
            try:
                url = f"https://ic.tpex.org.tw/introduce.php?ic={ic_code}"
                res = session.get(url, headers=self.headers, timeout=30)
                soup = BeautifulSoup(res.content, 'html.parser')
                for ns in soup.find_all("noscript"): ns.decompose()
                if progress_cb:
                    current_p = int(((idx + 1) / total_ics) * 100)
                    progress_cb(current_p)

                # 定位容器
                chain_containers = soup.find_all("div", class_="chain")
                for container in chain_containers:
                    title_div = container.find(class_=["chain-title-panel", "blockchain-title-panel"]) or container.find("h4")
                    chain_text = title_div.get_text(strip=True) if title_div else "其他"
                    
                    for link in container.find_all("div", id=re.compile(r"ic_link_")):
                        sub_ic_id = link.get('id').replace("ic_link_", "")
                        sub_ic_name = link.get_text(strip=True).replace("\n", " ").strip()
                        list_div = soup.find(id=f"companyList_{sub_ic_id}")
                        if not list_div: continue

                        # 判斷細目
                        sc_links = list_div.find_all(id=re.compile(r"sc_link_"))
                        if sc_links:
                            for sc in sc_links:
                                sc_id = sc.get('id').replace("sc_link_", "")
                                sc_name = re.sub(r'[\(（].*?[\)）]', '', sc.get_text(strip=True)).replace("►", "").replace("▶", "").strip()
                                table = list_div.find("table", id=f"sc_company_{sc_id}")
                                if table: self._process_v22_table(table, ic_name, chain_text, sub_ic_name, sc_name, new_map, dedup)
                        else:
                            for tb in list_div.find_all("table"):
                                self._process_v22_table(tb, ic_name, chain_text, sub_ic_name, "一般", new_map, dedup)
                time.sleep(0.5) # 稍微延遲避免被鎖
            except Exception as e:
                print(f"Error at {ic_name}: {e}")
                continue
        # 存檔
        self.value_chain_map = new_map
        self.last_update_date = datetime.now().strftime("%Y-%m-%d")
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump({"update_date": self.last_update_date, "map": self.value_chain_map}, f, ensure_ascii=False, indent=4)
        print(f"✅ [HotMap] 地圖同步完成，共收錄 {len(new_map)} 筆個股產業路徑")

    def _process_v22_table(self, table, main_cat, chain, sub, detail, target_map, dedup):
        """ V22 標籤流解析實作 """
        current_market = "未分類"
        for el in table.find_all(['b', 'a']):
            text = el.get_text(strip=True)
            if el.name == 'b':
                if any(k in text for k in ["本國上市", "本國上櫃", "本國興櫃", "外國上市", "外國上櫃", "外國興櫃", "創櫃"]):
                    current_market = re.sub(r'[\(（].*?[\)）]', '', text).strip()
            elif el.name == 'a':
                href = el.get('href', '')
                if "company_basic.php" in href and "知名外國企業" not in current_market:
                    stk_match = re.search(r'stk_code=(\w+)', href)
                    if stk_match:
                        sid = stk_match.group(1)
                        unique_key = f"{sid}_{sub}_{detail}"
                        if unique_key not in dedup:
                            target_map[sid] = target_map.get(sid, [])
                            target_map[sid].append({"main": main_cat, "path": f"{chain} > {sub} > {detail}"})
                            dedup.add(unique_key)

    # --- 數據計算邏輯 (與主程式對接) ---

    def fetch_market_prices(self, date_str):
        """ 使用快速 OpenAPI 獲取個股行情 (修正上櫃邏輯錯誤) """
        stock_data = {}
        total_amt = 0
        tse_count = 0  
        otc_count = 0
        try:
            # 1. 上市 OpenAPI (MI_INDEX)
            r_tse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=self.headers, timeout=15)
            if r_tse.status_code == 200:
                data_tse = r_tse.json()
                if isinstance(data_tse, list):
                    for r in data_tse:
                        sid = r.get('Code', '').strip()
                        if len(sid) == 4:
                            raw_amt = r.get('TradeValue') or 0
                            amt = self._clean_num(raw_amt) / 100000000 
                            close = self._clean_num(r.get('ClosingPrice') or 0)
                            change = self._clean_num(r.get('Change') or 0)
                        
                            prev_close = close - change
                            pct = round((change / prev_close) * 100, 2) if prev_close > 0 else 0.0
                        
                            stock_data[sid] = {"name": r.get('Name', '').strip(), "amount": amt, "change_pct": pct}
                            total_amt += amt
                            tse_count += 1

            # 2. 上櫃 OpenAPI (tpex_mainboard_quotes)
            r_otc = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", headers=self.headers, timeout=15)

            if r_otc.status_code == 200:
                data_otc = r_otc.json()
                if isinstance(data_otc, list):
                    for r in data_otc:
                        sid = r.get('SecuritiesCompanyCode', '').strip()
                        if len(sid) == 4:
                            raw_amt = r.get('TransactionAmount') or 0
                            amt = self._clean_num(raw_amt) / 100000000 
                            close = self._clean_num(r.get('Close') or 0)
                            change = self._clean_num(r.get('Change') or 0)
                        
                            prev_close = close - change
                            pct = round((change / prev_close) * 100, 2) if prev_close > 0 else 0.0
                        
                            stock_data[sid] = {"name": r.get('CompanyName', '').strip(), "amount": amt, "change_pct": pct}
                            total_amt += amt
                            otc_count += 1
                    
            print(f"[HotMap] OpenAPI 數據同步成功，共 {len(stock_data)} 檔，總金額: {total_amt:.2f} 億")
        except Exception as e:
            print(f"[HotMap] OpenAPI 抓取失敗: {e}")
            
        return stock_data, total_amt

    def get_hot_industry_data(self, date_str, current_db, chip_map, margin_map):
        """
        chip_map: 來自 app.py 的法人買賣超 (單位: 張)
        margin_map: 來自 app.py 的融資增減 (單位: 張)
        """
        if not self.value_chain_map:
            self._load_cache_or_check_update()
            if not self.value_chain_map: return {"resonance": [], "top5": [], "others": []}

        stock_prices, total_mkt_amount = self.fetch_market_prices(date_str)
        if total_mkt_amount == 0: return {"resonance": [], "top5": [], "others": []}

        industry_agg = {}
        for sid, info in stock_prices.items():
            paths = self.value_chain_map.get(sid, [])
            if not paths: continue
            
            # 💡 確保這裡抓得到的資料與 app.py 傳入的一致
            inst_net = chip_map.get(sid, {}).get('total', 0)
            retail_net = margin_map.get(sid, {}).get('f_change', 0) 
            combined_force = inst_net + retail_net

            for p in paths:
                name = p['main']
                if name not in industry_agg:
                    industry_agg[name] = {
                        "amount": 0.0, "changes": [], "sub_paths": {}, "net_force": 0.0 
                    }
            
                # 💡 修正：這幾行必須在 if 外面，才能累加該產業所有股票的數據
                industry_agg[name]["amount"] += info["amount"]
                industry_agg[name]["changes"].append(info["change_pct"])
                industry_agg[name]["net_force"] += combined_force
                industry_agg[name]["sub_paths"][p['path']] = industry_agg[name]["sub_paths"].get(p['path'], 0) + info["amount"]

        # 取得吸金產業清單 (用於後面篩選與標籤排序)
        all_industries_list = []
        for name, data in industry_agg.items():
            if not data["changes"]: continue
            all_industries_list.append({
                "name": name,
                "flow_val": data["amount"]
            })

        # 取得成交量前 10 名的產業名稱
        top_10_names = [x['name'] for x in sorted(all_industries_list, key=lambda x: x['flow_val'], reverse=True)[:10]]

        # --- 步驟 2：篩選共振個股 (標籤按熱度排序) ---
        sorted_stocks = sorted(stock_prices.items(), key=lambda x: x[1]['amount'], reverse=True)[:15]
        resonance_list = []

        for sid, info in sorted_stocks:
            paths = self.value_chain_map.get(sid, [])
            if not paths: continue

            # 篩選出屬於 Top 10 的產業路徑
            matched_hot_sectors = list(set([p['main'] for p in paths if p['main'] in top_10_names]))

            # 💡 關鍵修正：標籤根據「產業總金流」熱度進行排序
            # 讓這檔股票身上最吸金的標籤排在最前面
            matched_hot_sectors.sort(key=lambda s: industry_agg.get(s, {}).get("amount", 0), reverse=True)

            if len(matched_hot_sectors) >= 2:
                s_inst = chip_map.get(sid, {}).get('total', 0)
                s_retail = margin_map.get(sid, {}).get('f_change', 0)
        
                resonance_list.append({
                    "id": sid,
                    "name": info["name"],
                    "change": info["change_pct"],
                    "total_flow": round((info["amount"] / total_mkt_amount) * 100, 2),
                    "sectors": matched_hot_sectors,
                    "is_net_in": (s_inst + s_retail) > 0
                })

        # --- 步驟 3：格式化產業大類 (Leaders 篩選邏輯修正) ---
        results = []
        for name, data in industry_agg.items():
            if not data["changes"]: continue
            best_path = max(data["sub_paths"], key=data["sub_paths"].get)
            results.append({
                "name": name,
                "flow": round((data["amount"] / total_mkt_amount) * 100, 2),
                "change": round(sum(data["changes"]) / len(data["changes"]), 2),
                "path": best_path,
                "is_net_in": data["net_force"] > 0,
                "net_force": data["net_force"]
            })

        # 分類與排序
        leaders_pool = [r for r in results if r['is_net_in'] and r['change'] > 0]
        top5 = sorted(leaders_pool, key=lambda x: x['flow'], reverse=True)[:5]
        top5_names = [x['name'] for x in top5]
        
        others = sorted(
            [r for r in results if r['name'] not in top5_names], 
            key=lambda x: x['net_force'], 
            reverse=True
        )

        return {
            "resonance": sorted(resonance_list, key=lambda x: x['total_flow'], reverse=True)[:5],
            "top5": top5,
            "others": others,
            "last_update": self.last_update_date
        }
