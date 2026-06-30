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

class valuechainManager:
    def __init__(self, industry_db, cache_file="valuechain.json"):
        """ 
        industry_db: 傳入主程式的 GLOBAL_STOCK_DB (Yahoo 標籤)
        cache_file: 儲存櫃買中心詳細價值鏈地圖的本地檔案
        """
        self.industry_db = industry_db
        self.cache_file = cache_file
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        self.valuechain_map = {} # 存放櫃買中心的詳細地圖
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
        
        self._load_cache_or_check_update()

    def _clean_num(self, val):
        if val is None: return 0.0
        try: return float(str(val).replace(',', '').replace('"', '').strip())
        except: return 0.0

    def _valuechain_level2_name(self, path_item):
        parts = [part.strip() for part in str(path_item.get("path", "")).split(">") if part.strip()]
        if len(parts) >= 2:
            return parts[1]
        return path_item.get("main", "其他")

    def _valuechain_group_key(self, path_item):
        return f"{path_item.get('main', '其他')}::{self._valuechain_level2_name(path_item)}"

    def _valuechain_display_path(self, path):
        parts = [part.strip() for part in str(path).split(">") if part.strip()]
        if len(parts) >= 3 and parts[2] == "一般":
            parts = parts[:2]
        return " > ".join(parts) if parts else str(path)

    def _valuechain_detail_name(self, path):
        parts = [part.strip() for part in str(path).split(">") if part.strip()]
        if len(parts) >= 3 and parts[2] != "一般":
            return parts[2]
        if len(parts) >= 2:
            return parts[1]
        return str(path)

    def _get_session(self):
        s = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        s.mount('https://', HTTPAdapter(max_retries=retries))
        return s

    def _load_cache_or_check_update(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.last_update_date = cache_data.get("update_date", "2000-01-01")
                    last_dt = datetime.strptime(self.last_update_date, "%Y-%m-%d")
                    if datetime.now() - last_dt < timedelta(days=90):
                        self.valuechain_map = cache_data.get("map", {})
                        print(f"[ValueChain] 載入本地產業地圖 (上次更新: {self.last_update_date})")
                        return
            except: pass
        print("[ValueChain] 快取過期或不存在，需執行價值鏈爬蟲更新數據")

    def run_full_update(self, progress_cb=None):
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
                if progress_cb: progress_cb(int(((idx + 1) / total_ics) * 100))

                chain_containers = soup.find_all("div", class_="chain")
                for container in chain_containers:
                    title_div = container.find(class_=["chain-title-panel", "blockchain-title-panel"]) or container.find("h4")
                    chain_text = title_div.get_text(strip=True) if title_div else "其他"
                    
                    for link in container.find_all("div", id=re.compile(r"ic_link_")):
                        sub_ic_id = link.get('id').replace("ic_link_", "")
                        sub_ic_name = link.get_text(strip=True).replace("\n", " ").strip()
                        list_div = soup.find(id=f"companyList_{sub_ic_id}")
                        if not list_div: continue

                        sc_links = list_div.find_all(id=re.compile(r"sc_link_"))
                        if sc_links:
                            for sc in sc_links:
                                sc_id = sc.get('id').replace("sc_link_", "")
                                sc_name = re.sub(r'[\(（].*?[\)內]', '', sc.get_text(strip=True)).replace("►", "").replace("▶", "").strip()
                                table = list_div.find("table", id=f"sc_company_{sc_id}")
                                if table: self._process_v22_table(table, ic_name, chain_text, sub_ic_name, sc_name, new_map, dedup)
                        else:
                            for tb in list_div.find_all("table"):
                                self._process_v22_table(tb, ic_name, chain_text, sub_ic_name, "一般", new_map, dedup)
                time.sleep(0.1)
            except: continue

        self.valuechain_map = new_map
        self.last_update_date = datetime.now().strftime("%Y-%m-%d")
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump({"update_date": self.last_update_date, "map": self.valuechain_map}, f, ensure_ascii=False, indent=4)

    def _strip_parens(self, text):
        """移除字串中的括號內容，例如「網路設備(如數據機...)」→「網路設備」"""
        if not text:
            return text
        return re.sub(r'[\(（][^)）]*[\)）]', '', text).strip()

    def _process_v22_table(self, table, main_cat, chain, sub, detail, target_map, dedup):
        current_market = "未分類"
        # 🌟 先清理掉括號內容，避免顯示時出現冗長補充說明
        chain = self._strip_parens(chain)
        sub = self._strip_parens(sub)
        detail = self._strip_parens(detail)
        
        for el in table.find_all(['b', 'a']):
            text = el.get_text(strip=True)
            if el.name == 'b':
                if any(k in text for k in ["本國上市", "本國上櫃", "本國興櫃", "外國上市", "外國上櫃", "外國興櫃"]):
                    current_market = re.sub(r'[\(（].*?[\)內]', '', text).strip()
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

    def fetch_market_prices(self, date_str):
        """ 🌟 單位校正：官方 OpenAPI 原始單位即為元，除以 1 億換算成實體新台幣億元 """
        stock_data = {}
        total_amt = 0
        try:
            # 1. 上市行情同步
            r_tse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=self.headers, timeout=15)
            if r_tse.status_code == 200:
                for r in r_tse.json():
                    sid = r.get('Code', '').strip()
                    if len(sid) == 4 and sid.isdigit():
                        amt = self._clean_num(r.get('TradeValue')) / 100000000 
                        close = self._clean_num(r.get('ClosingPrice'))
                        change = self._clean_num(r.get('Change'))
                        prev_close = close - change
                        pct = round((change / prev_close) * 100, 2) if prev_close > 0 else 0.0
                        stock_data[sid] = {"name": r.get('Name', '').strip(), "amount": amt, "change_pct": pct, "price": close}
                        total_amt += amt

            # 2. 上櫃行情同步
            r_otc = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", headers=self.headers, timeout=15)
            if r_otc.status_code == 200:
                for r in r_otc.json():
                    sid = r.get('SecuritiesCompanyCode', '').strip()
                    if len(sid) == 4 and sid.isdigit():
                        amt = self._clean_num(r.get('TransactionAmount')) / 100000000 
                        close = self._clean_num(r.get('Close'))
                        change = self._clean_num(r.get('Change'))
                        prev_close = close - change
                        pct = round((change / prev_close) * 100, 2) if prev_close > 0 else 0.0
                        stock_data[sid] = {"name": r.get('CompanyName', '').strip(), "amount": amt, "change_pct": pct, "price": close}
                        total_amt += amt
                        
            print(f"[ValueChain] OpenAPI 行情校正完畢，全市場總金額: {total_amt:.2f} 億元")
        except Exception as e:
            print(f"[ValueChain] OpenAPI 同步異常: {e}")
        return stock_data, total_amt

    def get_valuechain_industry_data(self, date_str, current_db, chip_map, margin_map, radar_data=None):
        """
        全域核心大腦計算
        chip_map: 來自 app.py 傳入的各股法人買賣超 (單位為仟元，需在此處校正為億元)
        margin_map: 來自 app.py 傳入的融資增減明細 (單位為張)
        radar_data: 傳入雷達數據快取，用以直接抓取最新的 5日均量與當日量比
        """
        if not self.valuechain_map:
            self._load_cache_or_check_update()
            if not self.valuechain_map: return {"resonance": [], "top5": [], "others": []}

        stock_prices, total_mkt_amount = self.fetch_market_prices(date_str)
        if total_mkt_amount == 0: return {"resonance": [], "top5": [], "others": []}

        # --- 步驟 1：統計 47 大產業大類金流與多空趨勢 ---
        industry_agg = {}
        for sid, info in stock_prices.items():
            paths = self.valuechain_map.get(sid, [])
            if not paths: continue
            
            # 🌟 法人籌碼仟元 → 億元校正 + 融資張數金額化校正
            inst_net = chip_map.get(sid, {}).get('total', 0) / 100000   # 仟元 → 億元
            retail_shares = margin_map.get(sid, {}).get('f_change', 0) 
            retail_estimated_billion = (retail_shares * info["price"] * 1000) / 100000000
            
            # 個股的實體真實多空聚集金額 (億元)
            combined_force_billion = inst_net + retail_estimated_billion

            # 防止一檔股票在櫃買價值鏈中，被貼了多個一模一樣的大類標籤，進行去重
            unique_group_keys = list(set([self._valuechain_group_key(p) for p in paths]))
            weight_divider = len(unique_group_keys) if unique_group_keys else 1

            seen_groups = set()
            for p in paths:
                name = self._valuechain_group_key(p)
                if name not in industry_agg:
                    industry_agg[name] = {
                        "name": self._valuechain_level2_name(p),
                        "main": p.get("main", "其他"),
                        "amount": 0.0,
                        "changes": [],
                        "sub_paths": {},
                        "net_force": 0.0,
                        "components": {}
                    }
            
                if name not in seen_groups:
                    # 均分灌入，防止產業成交量自我繁衍假膨脹
                    industry_agg[name]["amount"] += (info["amount"] / weight_divider)
                    industry_agg[name]["changes"].append(info["change_pct"])
                    industry_agg[name]["net_force"] += (combined_force_billion / weight_divider)
                    industry_agg[name]["components"][sid] = {
                        "id": sid,
                        "name": info["name"],
                        "amount": round(info["amount"], 2),
                        "change": info["change_pct"],
                        "net_force": round(combined_force_billion, 2),
                        "price": info["price"]
                    }
                    seen_groups.add(name)
                
                # 詳細細分路徑成交量追蹤
                industry_agg[name]["sub_paths"][p['path']] = industry_agg[name]["sub_paths"].get(p['path'], 0) + info["amount"]

        # 整理全市場大類金流基礎占比
        all_industries_list = [{"key": key, "flow_val": data["amount"]} for key, data in industry_agg.items() if data["changes"]]
        top_12_keys = [x['key'] for x in sorted(all_industries_list, key=lambda x: x['flow_val'], reverse=True)[:12]]

        # --- 步驟 2：多產業共振核心個股篩選（方案二：金額 × 量比加權加強版） ---
        # 1. 基礎門檻過濾：當日必須是聚集最多資金上漲（漲幅 >= 2.0% 且成交金額 > 0.4億）
        rising_pool = [(sid, info) for sid, info in stock_prices.items() if info["change_pct"] >= 2.0 and info["amount"] >= 0.4]
        
        resonance_candidates = []
        for sid, info in rising_pool:
            paths = self.valuechain_map.get(sid, [])
            if not paths: continue

            # 取出個股的所有大產業標籤，並篩選出當日最吸金的前 12 名熱門流入產業 (net_force > 0)
            matched_sector_keys = list(set([
                self._valuechain_group_key(p)
                for p in paths
                if self._valuechain_group_key(p) in top_12_keys
                and industry_agg.get(self._valuechain_group_key(p), {}).get("net_force", 0) > 0
            ]))
            
            if len(matched_sector_keys) >= 2:
                # 🌟 方案二加權核心：引入當日量比
                vol_ratio = 1.0
                if radar_data and "groups" in radar_data:
                    # 從雷達數據緩存中嘗試精準撈出這檔股票的量比欄位
                    for gk, gv in radar_data["groups"].items():
                        for radar_item in gv:
                            if str(radar_item.get("stock_id")).strip() == str(sid).strip():
                                vol_ratio = radar_item.get("vol_ratio", 1.0)
                                break

                # 計算這檔股票當日真實的『多空聚集總量』(億元)
                inst_net = chip_map.get(sid, {}).get('total', 0) / 100000   # 仟元 → 億元
                retail_shares = margin_map.get(sid, {}).get('f_change', 0)
                actual_net_gather = inst_net + ((retail_shares * info["price"] * 1000) / 100000000)
                
                # 🌟 排行綜合評分 = 聚集量絕對值 * 當日量比 (量能爆發加權)
                ranking_score = abs(actual_net_gather) * vol_ratio

                # 按熱度降序排列股票身上的產業標籤
                matched_sector_keys.sort(key=lambda s: industry_agg.get(s, {}).get("amount", 0), reverse=True)
                best_detail_path = " | ".join(list(set([self._valuechain_detail_name(p['path']) for p in paths if self._valuechain_group_key(p) in matched_sector_keys])))
                matched_sectors = [industry_agg[k]["name"] for k in matched_sector_keys[:3]]

                resonance_candidates.append({
                    "id": sid,
                    "name": info["name"],
                    "change": info["change_pct"],
                    "flow_display": round(actual_net_gather, 2),
                    "total_flow": round((info["amount"] / total_mkt_amount) * 100, 2),
                    "sectors": matched_sectors,
                    "path_detail": best_detail_path,
                    "ranking_score": ranking_score,
                    "is_net_in": actual_net_gather >= 0
                })

        # 共振核心依據 綜合量能加權評分（Score）進行由大到小降序，完美淘汰死氣沉沉的高價高基數股
        final_resonance = sorted(resonance_candidates, key=lambda x: x['ranking_score'], reverse=True)[:5]

        # --- 步驟 3：今日價量領頭羊 & 全市場金流矩陣（同源切分、完美降序） ---
        all_industry_results = []
        for name, data in industry_agg.items():
            if not data["changes"]: continue
            best_path = max(data["sub_paths"], key=data["sub_paths"].get)
            
            all_industry_results.append({
                "key": name,
                "name": data["name"],
                "main": data["main"],
                "flow": round((data["amount"] / total_mkt_amount) * 100, 2), # 🌟 水波紋高度與全局排序唯一依據：金流占比
                "change": round(sum(data["changes"]) / len(data["changes"]), 2), # 右上角平均漲跌幅
                "flow_display": round(data["net_force"], 2), # 卡片中央顯示實體資金聚集/逃出量 (億元)
                "path": self._valuechain_display_path(best_path),
                "is_net_in": data["net_force"] >= 0, # 正數為紅，負數為綠
                "net_force": data["net_force"],
                "components": sorted(data["components"].values(), key=lambda x: x["amount"], reverse=True)[:30]
            })

        # 全市場 47 個產業，嚴格遵循「當日金流占比 (flow %)」由大到小降序大排列
        global_sorted_industries = sorted(all_industry_results, key=lambda x: x['flow'], reverse=True)

        # 頂部價量領頭羊條件：必須是金流占比前列、且主力資金呈聚集狀態 (net_force > 0) 且平均在上漲的產業
        leaders_pool = [r for r in global_sorted_industries if r['is_net_in'] and r['change'] > 0]
        top5 = leaders_pool[:5]
        top5_keys = [x['key'] for x in top5]
        
        # 全市場金流矩陣：完美切分，裝載除了那 5 個領頭羊之外的「其餘所有產業」，並維持一貫的降序階梯排列
        others = [r for r in global_sorted_industries if r['key'] not in top5_keys]

        return {
            "resonance": final_resonance,
            "top5": top5,
            "others": others,
            "last_update": self.last_update_date
        }
