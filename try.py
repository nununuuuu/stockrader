import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 1. 完整產業代碼 ---
industries = {
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

base_url = "https://ic.tpex.org.tw/introduce.php?ic="

def get_session():
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    s.mount('https://', HTTPAdapter(max_retries=retries))
    return s

def parse_table_v22(table, main_cat, chain_label, sub_cat, segment, global_data, dedup):
    """
    V22 核心邏輯：標籤流解析
    不看 TR 行數，而是按順序尋找所有 B 標籤 (標題) 與 A 標籤 (公司)
    這能完美解決 Rowspan 導致的標題消失問題，並在標題出現時立即切換。
    """
    current_market = "未分類"
    
    # 尋找 table 內所有的子標籤，按順序處理
    # 我們只關心 <b> 和 <a>
    elements = table.find_all(['b', 'a'])
    
    for el in elements:
        text = el.get_text(strip=True)
        
        # 1. 偵測到 B 標籤：檢查是否為分類標題
        if el.name == 'b':
            # 市場別關鍵字判斷
            if any(k in text for k in ["本國上市", "本國上櫃", "本國興櫃", "外國上市", "外國上櫃", "外國興櫃", "創櫃"]):
                # 遇到新的標題，立即更新狀態
                current_market = re.sub(r'[\(（].*?[\)）]', '', text).strip()
        
        # 2. 偵測到 A 標籤：檢查是否為公司連結
        elif el.name == 'a':
            href = el.get('href', '')
            # 必須包含公司代碼連結，且排除「知名外國企業」
            if "company_basic.php" in href and "知名外國企業" not in current_market:
                comp_name = text
                stk_match = re.search(r'stk_code=(\w+)', href)
                stk_code = stk_match.group(1) if stk_match else ""
                
                # 去重 Key: 確保在同一個子產業/細目下不重複
                unique_key = (sub_cat, segment, stk_code)
                if unique_key not in dedup:
                    global_data.append({
                        "產業大類": main_cat,
                        "鏈位": chain_label,
                        "子產業": sub_cat,
                        "細分細目": segment,
                        "市場別": current_market,
                        "代號": stk_code,
                        "公司名稱": comp_name
                    })
                    dedup.add(unique_key)

def scrape_v22(session, ic_code, ic_name):
    print(f">>> 正在分析: {ic_name} ({ic_code})")
    all_rows = []
    dedup = set()
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        res = session.get(f"{base_url}{ic_code}", headers=headers, timeout=60)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 刪除備份區塊
        for ns in soup.find_all("noscript"):
            ns.decompose()

        # [A] 先鎖定鏈位容器 (確保鏈位正確)
        chain_containers = soup.find_all("div", class_="chain")
        for container in chain_containers:
            # 獲取 上/中/下游 標題
            title_div = container.find(class_=["chain-title-panel", "blockchain-title-panel"])
            if not title_div: title_div = container.find("h4")
            chain_text = title_div.get_text(strip=True) if title_div else "其他"
            
            # [B] 在容器內找子產業
            ic_links = container.find_all("div", id=re.compile(r"ic_link_"))
            for link in ic_links:
                sub_ic_id = link.get('id').replace("ic_link_", "")
                sub_ic_name = link.get_text(strip=True).replace("\n", " ").strip()
                
                list_div = soup.find(id=f"companyList_{sub_ic_id}")
                if not list_div: continue

                # [C] 判斷是否有「細目」 (如 LED驅動IC)
                sc_links = list_div.find_all(id=re.compile(r"sc_link_"))
                if sc_links:
                    for sc in sc_links:
                        sc_id = sc.get('id').replace("sc_link_", "")
                        sc_name = sc.get_text(strip=True).replace("►", "").replace("▶", "").strip()
                        sc_name = re.sub(r'\(.*\)', '', sc_name).strip()
                        
                        sc_table = list_div.find("table", id=f"sc_company_{sc_id}")
                        if sc_table:
                            parse_table_v22(sc_table, ic_name, chain_text, sub_ic_name, sc_name, all_rows, dedup)
                else:
                    # 無細目直接抓 Table
                    for tb in list_div.find_all("table"):
                        parse_table_v22(tb, ic_name, chain_text, sub_ic_name, "一般", all_rows, dedup)
        return all_rows
    except Exception as e:
        print(f"!!! 錯誤: {e}")
        return []

# --- 執行程序 ---
sess = get_session()
final_data = []

# 您可以一次跑全部 47 個產業
for code, name in industries.items():
    data = scrape_v22(sess, code, name)
    final_data.extend(data)
    time.sleep(3)

if final_data:
    df = pd.DataFrame(final_data)
    # 物理去重與格式化
    df['代號'] = df['代號'].astype(str)
    df.to_excel("台灣全產業價值鏈_終極精準版.xlsx", index=False)
    print(f"\n✅ 任務完成！共 {len(df)} 筆。分類、鏈位、重複問題已全部修復。")