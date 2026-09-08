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
import concurrent.futures 
import random


HISTORY_SCHEMA_VERSION = 3
MAX_HISTORY_GAP_DAYS = 7

class valuechainManager:
    def __init__(self, industry_db, cache_file="valuechain.json", history_file="industry_history.json"):
        self.industry_db = industry_db
        self.cache_file = cache_file
        self.history_file = history_file
        self.history_data = self._load_history()
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'}
        self.valuechain_map = {} 
        self.last_update_date = ""

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
        
    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
                if (
                    isinstance(payload, dict)
                    and payload.get("_schema_version") == HISTORY_SCHEMA_VERSION
                    and isinstance(payload.get("dates"), dict)
                ):
                    return payload["dates"]
                if payload:
                    print("[ValueChain] 舊版歷史資料口徑不一致，將重新回填。")
                return {}
            except: return {}
        return {}

    def _save_history(self):
        sorted_dates = sorted(self.history_data.keys(), reverse=True)[:40]
        self.history_data = {d: self.history_data[d] for d in sorted_dates}
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump({
                "_schema_version": HISTORY_SCHEMA_VERSION,
                "dates": self.history_data,
            }, f, ensure_ascii=False, indent=4)

    def sync_historical_data(self, anchor_date, progress_cb=None):
        needed_dates = []
        check_dt = datetime.strptime(anchor_date, "%Y%m%d")
        REQUIRED_KEYS = {"net_force", "inst_net", "change"}
        for i in range(1, 30):
            d_str = (check_dt - timedelta(days=i)).strftime("%Y%m%d")
            if datetime.strptime(d_str, "%Y%m%d").weekday() < 5:
                should_refetch = False
                if d_str not in self.history_data: should_refetch = True
                else:
                    day_content = self.history_data[d_str]
                    if not day_content: should_refetch = True
                    else:
                        sample = next(iter(day_content.values()))
                        if not REQUIRED_KEYS.issubset(sample.keys()): should_refetch = True
                if should_refetch: needed_dates.append(d_str)
            if len(needed_dates) >= 20: break 

        if not needed_dates: return
        print(f"[ValueChain] 自動補齊啟動: {needed_dates}")
        session = self._get_session()
        for d in needed_dates:
            if self._fetch_and_store_historical_day(session, d):
                self._save_history()
            time.sleep(random.randint(10, 15))

    def _fetch_and_store_historical_day(self, session, d_str):
        """ 修正：修復 Key 缺失導致的崩潰與邏輯錯誤 """
        try:
            t_i = session.get(f"https://www.twse.com.tw/fund/T86?response=json&date={d_str}&selectType=ALL", timeout=20).json()
            if t_i.get('stat') != 'OK': return False
            time.sleep(2)
            t_p = session.get(f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={d_str}&type=ALLBUT0999", timeout=20).json()
            
            d_otc = f"{int(d_str[:4])-1911}/{d_str[4:6]}/{d_str[6:]}"
            o_i = session.get(f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&d={d_otc}", timeout=20).json()
            o_p = session.get(f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&d={d_otc}&o=json", timeout=20).json()

            full_inst, full_price = {}, {}
            for r in t_i.get('data', []):
                if len(r) > 18: full_inst[str(r[0]).strip()] = float(str(r[18]).replace(',', ''))
            
            for k in ['data9', 'data8', 'data10']:
                if k in t_p:
                    for r in t_p[k]:
                        if len(r) > 10:
                            sid, close, chg_v = str(r[0]).strip(), self._clean_num(r[8]), self._clean_num(r[10])
                            sign = -1 if 'green' in str(r[9]) or '-' in str(r[9]) else 1
                            full_price[sid] = {"p": close, "c": chg_v * sign}
                    break

            o_i_data = o_i['tables'][0].get('data', []) if o_i and 'tables' in o_i else []
            for r in o_i_data:
                if len(r) > 23: full_inst[str(r[0]).strip()] = float(str(r[23]).replace(',', ''))
            
            o_p_data = o_p['tables'][0].get('data', []) if o_p and 'tables' in o_p else []
            for r in o_p_data:
                if len(r) > 3: full_price[str(r[0]).strip()] = {"p": self._clean_num(r[2]), "c": self._clean_num(r[3])}

            daily_snapshot = {}
            for sid, info in full_price.items():
                paths = self.valuechain_map.get(sid) or self.valuechain_map.get(sid.zfill(6))
                if not paths or sid not in full_inst: continue
                nf = (full_inst[sid] * info['p']) / 100000000
                pc = (info['c'] / (info['p'] - info['c']) * 100) if (info['p'] - info['c']) != 0 else 0
                unique_groups = {self._valuechain_group_key(p) for p in paths}
                for g in unique_groups:
                    if g not in daily_snapshot: daily_snapshot[g] = {"nf": 0.0, "inst": 0.0, "cs": []}
                    daily_snapshot[g]["nf"] += nf
                    daily_snapshot[g]["inst"] += nf
                    daily_snapshot[g]["cs"].append(pc)

            if daily_snapshot:
                self.history_data[d_str] = {
                    k: { "net_force": round(v["nf"], 2), "inst_net": round(v["inst"], 2), "change": round(sum(v["cs"])/len(v["cs"]), 2) } 
                    for k, v in daily_snapshot.items()
                }
                return True
        except Exception as e: print(f"背景同步失敗 ({d_str}): {e}")
        return False

    def get_valuechain_industry_data(self, date_str, current_db, chip_map, margin_map, radar_data=None):
        """ 修正：變數對齊與異常標籤邏輯優化 """
        if not self.valuechain_map:
            self._load_cache_or_check_update()
            if not self.valuechain_map: return {"resonance": [], "top5": [], "others": []}

        stock_prices, total_mkt_amount = self.fetch_market_prices(date_str)
        if total_mkt_amount == 0: return {"resonance": [], "top5": [], "others": []}

        industry_agg = {}
        for sid, info in stock_prices.items():
            paths = self.valuechain_map.get(sid, [])
            if not paths: continue
            
            # 修正：法人金額換算
            raw_inst_lots = chip_map.get(sid, {}).get('total', 0)
            inst_net_billion = (raw_inst_lots * info["price"]) / 100000   
            
            margin_lot_change = margin_map.get(sid, {}).get('f_change', 0)
            margin_net_billion = (margin_lot_change * info["price"] * 1000) / 100000000

            seen_groups = set()
            for p in paths:
                name = self._valuechain_group_key(p)
                if name not in industry_agg:
                    industry_agg[name] = {
                        "name": self._valuechain_level2_name(p),
                        "main": p.get("main", "其他"),
                        "amount": 0.0, "changes": [], "sub_paths": {}, 
                        "net_inst": 0.0, "margin_net": 0.0, "components": {}
                    }
            
                if name not in seen_groups:
                    # 🌟 修正：個股異常判斷 (基於純法人)
                    is_abnormal_buy = inst_net_billion > 5.0 or (inst_net_billion > 1.0 and (inst_net_billion / (info["amount"] or 1)) > 0.15)
                    is_abnormal_sell = inst_net_billion < -5.0 or (inst_net_billion < -1.0 and (abs(inst_net_billion) / (info["amount"] or 1)) > 0.15)
                    
                    industry_agg[name]["amount"] += info["amount"]
                    industry_agg[name]["changes"].append(info["change_pct"])
                    industry_agg[name]["net_inst"] += inst_net_billion
                    industry_agg[name]["margin_net"] += margin_net_billion
                    
                    industry_agg[name]["components"][sid] = {
                        "id": sid, "name": info["name"], "amount": round(info["amount"], 2),
                        "change": info["change_pct"], 
                        "net_force": round(inst_net_billion, 2),
                        "inst_net": round(inst_net_billion, 2), 
                        "margin_net": round(margin_net_billion, 2),
                        "price": info["price"],
                        "is_abnormal": is_abnormal_buy or is_abnormal_sell,
                        "abnormal_type": "buy" if is_abnormal_buy else "sell" if is_abnormal_sell else None
                    }
                    seen_groups.add(name)
                industry_agg[name]["sub_paths"][p['path']] = industry_agg[name]["sub_paths"].get(p['path'], 0) + info["amount"]

        history_dates = self._recent_history_dates(date_str)
        
        all_industry_results = []
        for name, data in industry_agg.items():
            if not data["changes"]: continue
            
            inst_series = [data["net_inst"]]
            change_series = [sum(data["changes"]) / len(data["changes"])]
            
            for d in history_dates:
                h_item = self.history_data[d].get(name)
                if not h_item:
                    break
                inst_series.append(h_item.get("inst_net", h_item.get("net_force", 0)))
                change_series.append(h_item.get("change", 0))

            observations = len(inst_series)
            ins_5d = sum(inst_series[:5]) if observations >= 5 else None
            ins_20d = sum(inst_series[:20]) if observations >= 20 else None
            chg_5d = None
            if len(change_series) >= 5:
                compound = 1.0
                for daily_change in change_series[:5]:
                    compound *= 1 + (daily_change / 100)
                chg_5d = (compound - 1) * 100
            
            streak = 0
            current_inst = data["net_inst"]
            if current_inst != 0:
                is_inflow = current_inst > 0
                for institutional_flow in inst_series:
                    if institutional_flow == 0 or (institutional_flow > 0) != is_inflow:
                        break
                    streak += 1
            final_streak = streak if current_inst >= 0 else -streak

            previous_inst = inst_series[1:6]
            accel = round(current_inst - (sum(previous_inst) / len(previous_inst)), 2) if previous_inst else None

            best_path = max(data["sub_paths"], key=data["sub_paths"].get)
            all_industry_results.append({
                "key": name, "name": data["name"], "main": data["main"],
                "flow": round((data["amount"] / total_mkt_amount) * 100, 2),
                "change": round(change_series[0], 2),
                # 保留 net_force 欄位供既有卡片使用，但口徑統一為純法人淨買超。
                "net_force": round(data["net_inst"], 2),
                "net_inst_1d": round(data["net_inst"], 2),
                "margin_net_1d": round(data["margin_net"], 2),
                "inst_net_5d": round(ins_5d, 2) if ins_5d is not None else None,
                "inst_net_20d": round(ins_20d, 2) if ins_20d is not None else None,
                "change_5d": round(chg_5d, 2) if chg_5d is not None else None,
                "inflow_streak": final_streak,
                "accel": accel,
                "history_days": observations,
                "path": self._valuechain_display_path(best_path),
                "is_net_in": data["net_inst"] >= 0,
                "components": sorted(data["components"].values(), key=lambda x: x["amount"], reverse=True)[:30]
            })

        self.history_data[date_str] = { 
            r['key']: {"net_force": r['net_force'], "inst_net": r['net_inst_1d'], "change": r['change']} 
            for r in all_industry_results 
        }
        self._save_history()

        global_sorted = sorted(all_industry_results, key=lambda x: x['flow'], reverse=True)
        leaders_pool = [r for r in global_sorted if r['is_net_in'] and r['change'] > 0]
        top5 = leaders_pool[:5]
        top5_keys = [x['key'] for x in top5]
        others = [r for r in global_sorted if r['key'] not in top5_keys]

        return {"resonance": [], "top5": top5, "others": others, "last_update": self.last_update_date}

    def run_full_update(self, progress_cb=None):
        """重新載入獨立產業鏈快取，不使用 Yahoo 分類覆寫它。"""
        if progress_cb:
            progress_cb(10)
        if not self._load_cache_or_check_update():
            raise RuntimeError(f"無法讀取有效的獨立產業鏈檔案: {self.cache_file}")
        if progress_cb:
            progress_cb(100)
        print(f"[ValueChain] 已重新載入獨立產業鏈，共 {len(self.valuechain_map)} 檔個股。")
        return True

    # --- 4. 輔助工具方法 (去重整理) ---

    def _clean_num(self, val):
        if val is None: return 0.0
        try: return float(str(val).replace(',', '').replace('"', '').replace('=', '').strip())
        except: return 0.0

    def _strip_parens(self, text):
        if not text: return text
        return re.sub(r'[\(（][^)）]*[\)內舉]', '', text).strip()

    def _valuechain_level2_name(self, path_item):
        parts = [part.strip() for part in str(path_item.get("path", "")).split(">") if part.strip()]
        return parts[1] if len(parts) >= 2 else path_item.get("main", "其他")

    def _valuechain_group_key(self, path_item):
        return f"{path_item.get('main', '其他')}::{self._valuechain_level2_name(path_item)}"

    def _valuechain_display_path(self, path):
        parts = [part.strip() for part in str(path).split(">") if part.strip()]
        if len(parts) >= 3 and parts[2] == "一般": parts = parts[:2]
        return " > ".join(parts) if parts else str(path)

    def _recent_history_dates(self, date_str):
        """只接受日期連續的近期資料，避免用過舊資料冒充近 5／20 日。"""
        try:
            cursor = datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            return []

        result = []
        for history_date in sorted((d for d in self.history_data if d < date_str), reverse=True):
            try:
                history_dt = datetime.strptime(history_date, "%Y%m%d")
            except ValueError:
                continue
            if (cursor - history_dt).days > MAX_HISTORY_GAP_DAYS:
                break
            result.append(history_date)
            cursor = history_dt
        return result

    def fetch_market_prices(self, date_str):
        stock_data, total_amt = {}, 0
        try:
            r_tse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=self.headers, timeout=15).json()
            for r in r_tse:
                sid = r.get('Code', '').strip()
                if len(sid) == 4 and sid.isdigit():
                    amt, close, chg = self._clean_num(r.get('TradeValue')) / 100000000, self._clean_num(r.get('ClosingPrice')), self._clean_num(r.get('Change'))
                    stock_data[sid] = {"name": r.get('Name', '').strip(), "amount": amt, "price": close, "change_pct": round(chg/(close-chg)*100, 2) if close!=chg else 0}
                    total_amt += amt
            r_otc = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", headers=self.headers, timeout=15).json()
            for r in r_otc:
                sid = r.get('SecuritiesCompanyCode', '').strip()
                if len(sid) == 4 and sid.isdigit():
                    amt, close, chg = self._clean_num(r.get('TransactionAmount')) / 100000000, self._clean_num(r.get('Close')), self._clean_num(r.get('Change'))
                    stock_data[sid] = {"name": r.get('CompanyName', '').strip(), "amount": amt, "price": close, "change_pct": round(chg/(close-chg)*100, 2) if close!=chg else 0}
                    total_amt += amt
        except: pass
        return stock_data, total_amt

    def _load_cache_or_check_update(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                valuechain_map = cache_data.get("map", {})
                if not isinstance(valuechain_map, dict) or not valuechain_map:
                    return False
                self.last_update_date = cache_data.get("update_date", "2000-01-01")
                self.valuechain_map = valuechain_map
                print(f"[ValueChain] 載入獨立產業鏈 ({self.last_update_date})")
                return True
            except Exception as e:
                print(f"[ValueChain] 產業鏈快取讀取失敗: {e}")
        return False

    def _get_session(self):
        s = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        s.mount('https://', HTTPAdapter(max_retries=retries))
        return s
