import pandas as pd
import io
import time
from playwright.sync_api import sync_playwright

def get_goodinfo_limit_up_with_playwright():
    """
    優化等待機制的 Playwright 版本，避免因背景廣告或流量導致的超時錯誤
    """
    url = "https://goodinfo.tw/tw/StockList.asp?MARKET_CAT=%E6%99%BA%E6%85%A7%E9%81%B8%E8%82%A1&INDUSTRY_CAT=%E6%BC%B2%E5%81%9C%E8%82%A1"
    
    with sync_playwright() as p:
        print("正在啟動背景瀏覽器 (Chromium)...")
        browser = p.chromium.launch(headless=True)
        
        # 建立瀏覽器上下文，並加入更多真實瀏覽器的特徵偽裝
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        try:
            print("正在導向 Goodinfo 網頁並等待基礎結構載入...")
            # 💡 修正一：只等待基礎 DOM 結構載入即可 (避免被背景持續的網路流量拖入超時)
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            
            print("正在等待 Goodinfo 內部 JavaScript 驗證與關鍵元素...")
            # 💡 修正二：精準等待 Goodinfo 頁面上的股票代號查詢輸入框載入完成（代表頁面已解鎖並成功跳轉）
            # 這個輸入框的 id 是 'txtStockCode'
            page.wait_for_selector("#txtStockCode", timeout=15000)
            
            # 給表格渲染留一秒鐘的溫柔餘裕
            time.sleep(2)
            
            # 取得經由瀏覽器渲染跳轉後的真實完整 HTML
            html_content = page.content()
            browser.close()
            
            if not html_content or "<table" not in html_content.lower():
                print("⚠️ 網頁載入成功，但內容尚未包含表格結構。")
                return set()
            
            # 使用 pandas 解析 HTML 表格
            dfs = pd.read_html(io.StringIO(html_content))
            
            target_df = None
            for df in dfs:
                if '代號' in df.columns and '名稱' in df.columns:
                    target_df = df
                    break
                    
            if target_df is not None:
                if isinstance(target_df.columns, pd.MultiIndex):
                    target_df.columns = [col[-1] for col in target_df.columns]
                    
                limit_up_list = target_df['代號'].astype(str).tolist()
                return set([str(x).strip() for x in limit_up_list if x.isdigit()])
            else:
                print("⚠️ 成功載入網頁表格，但未找到包含『代號』與『名稱』的目標表格。")
                return set()
                
        except Exception as e:
            print(f"❌ Playwright 爬取或解析失敗: {e}")
            try:
                browser.close()
            except:
                pass
            return set()

# 測試執行
if __name__ == "__main__":
    result = get_goodinfo_limit_up_with_playwright()
    print("\n當前漲停股代號清單：")
    print(result)