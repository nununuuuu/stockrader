import requests
import json

def test_yahoo_limit_up_api():
    print("🚀 [測試開始] 正在請求 Yahoo 實時數據中心 (漲停名單)...")
    
    limit_up_set = set()
    
    # 💡 這是 Yahoo 的實時分類 API
    # category=%E6%BC%B2%E5%81%9C 代表「漲停」
    url = "https://tw.stock.yahoo.com/_td-stock/api/resource/StockServices.getClassQuotes;category=%E6%BC%B2%E5%81%9C;limit=100;offset=0"
    
    # 💡 Yahoo API 非常看重 Referer，沒加會 404
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://tw.stock.yahoo.com/class-quote?category=%E6%BC%B2%E5%81%9C',
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            # Yahoo 的資料結構在 'list' 欄位中
            items = data.get('list', [])
            
            if not items:
                print("💡 請求成功，但目前名單為空 (可能是非交易時段或今日無漲停)")
            else:
                print(f"✅ 成功抓取今日漲停股，共 {len(items)} 檔：")
                for item in items:
                    # symbol 格式為 "2330.TW"
                    full_code = item.get('symbol', '')
                    code = full_code.split('.')[0]
                    name = item.get('stockName', '未知')
                    # 這是 Yahoo 標記的漲幅
                    change_pct = item.get('changePercent', '0')
                    
                    if code.isdigit():
                        limit_up_set.add(code)
                        print(f"   - {code} {name} (漲幅: {change_pct}%)")
        else:
            print(f"❌ 請求失敗，狀態碼: {res.status_code}")
            
    except Exception as e:
        print(f"❌ 發生異常: {e}")

    print("\n" + "="*40)
    print(f"🏁 測試完成！總計抓到 {len(limit_up_set)} 檔漲停。")
    print(f"代號清單: {sorted(list(limit_up_set))}")
    print("="*40)

if __name__ == "__main__":
    test_yahoo_limit_up_api()