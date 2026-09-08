import requests
import json
import re
import csv
import io
import codecs

# 🌟 步驟 0：強制註冊編碼別名 (解決 MS950 報錯)
try:
    codecs.lookup('ms950')
except LookupError:
    codecs.register(lambda name: codecs.lookup('cp950') if name.lower() == 'ms950' else None)

# 模擬真實瀏覽器標頭
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/json,text/plain,*/*',
    'Referer': 'https://www.tpex.org.tw/zh-tw/mainboard/trading/margin/margin.html',
    'X-Requested-With': 'XMLHttpRequest'
}

def clean_num(val):
    if not val: return 0.0
    try:
        s = str(val).replace('"', '').replace(',', '').replace('=', '').strip()
        return float(s)
    except:
        return 0.0

def test_otc_margin_binary():
    print("🚀 啟動櫃買中心 (TPEX) 二進制穿透測試...")
    target_date = "115/05/22" # 民國年格式
    
    # 使用妳截圖中證實可用的路徑 (透過 www 網域)
    # 我們優先測試 OpenAPI，因為它的資料結構最完整
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance"
    
    session = requests.Session()
    
    try:
        # 🌟 步驟 1：先造訪官網首頁獲取 Cookie (關鍵！)
        print("1. 正在獲取官網通行證 (Cookie)...")
        session.get("https://www.tpex.org.tw/zh-tw/index.html", headers=HEADERS, timeout=10)
        
        # 🌟 步驟 2：請求數據 (使用二進制模式避免編碼報錯)
        print(f"2. 正在請求數據: {url}")
        resp = session.get(url, headers=HEADERS, timeout=10)
        
        # 🌟 步驟 3：手動解碼 (不直接用 resp.text)
        # 即使伺服器噴 MS950，我們也強迫用 cp950 讀取
        try:
            raw_data = resp.content.decode('cp950')
        except:
            raw_data = resp.content.decode('utf-8', errors='ignore')

        print(f"3. 連線狀態: {resp.status_code}, 內容長度: {len(raw_data)} 字元")

        # 檢查是否抓到的是 JSON (OpenAPI 格式)
        if raw_data.strip().startswith('['):
            data = json.loads(raw_data)
            print(f"✅ 成功！透過 OpenAPI 抓取到 {len(data)} 檔個股")
            sample = data[0]
            # 對齊妳截圖中的 Key
            sid = sample.get('SecuritiesCompanyCode')
            print(f"💡 數據驗證 {sample.get('CompanyName')}({sid})")
            return True
        
        # 檢查是否抓到的是 404 網頁
        elif "page-not-found" in raw_data or "<!DOCTYPE html>" in raw_data:
            print("❌ 失敗：雖然連線成功，但被伺服器導向了 404 頁面。")
            print("💡 備案：嘗試切換至 CSV 原始路徑...")
            
            # --- 備案：切換回 CSV 接口 ---
            csv_url = f"https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=csv&d={target_date}"
            csv_resp = session.get(csv_url, headers=HEADERS, timeout=10)
            csv_text = csv_resp.content.decode('cp950', errors='ignore')
            
            if "代號" in csv_text:
                reader = csv.reader(io.StringIO(csv_text))
                stocks = [row for row in reader if len(row) > 10 and re.match(r'^\d', row[0])]
                print(f"✅ 備案成功！透過 CSV 抓取到 {len(stocks)} 檔個股")
                return True
            else:
                print("❌ 備案也失敗，可能 IP 被暫時限制。")

    except Exception as e:
        print(f"🚨 異常報錯: {e}")
    
    return False

if __name__ == "__main__":
    test_otc_margin_binary()