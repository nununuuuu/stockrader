# 專案換裝置安裝指南（Windows / PowerShell）

> 目標：在新電腦快速把後端（Flask/Python）與前端（Vite/React）裝起來並可執行。

## 0) 先決條件

- 安裝 Python 3.11+（建議）
- 安裝 Node.js 18+（建議 LTS）
- 安裝 Git

---

## 1) 取得專案

```powershell
git clone <你的repo-url>
cd warning
```

---

## 2) 後端（Python）環境

### 建立並啟用虛擬環境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> 若 PowerShell 啟用腳本被擋，可用：
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

### 安裝依賴

```powershell
pip install -r requirements.txt
```

### 啟動後端

```powershell
python app.py
```

預設 API：`http://localhost:5000`

---

## 3) 前端（Vite/React）環境

開新一個 PowerShell 視窗（或保持後端在跑），在專案根目錄執行：

```powershell
cd frontend
npm install
npm run dev
```

預設前端：`http://localhost:5173`

---

## 4) 常見問題

### A) `.venv`、`__pycache__`、`.history` 出現在 Git

請在專案根目錄 `.gitignore` 忽略這些資料夾（不建議提交）。

### B) 版本要完全一致（可重現）

若你希望在不同裝置得到完全相同版本，可以在舊機器啟用 `.venv` 後輸出鎖版清單：

```powershell
pip freeze > requirements-lock.txt
```

然後新機器改用：

```powershell
pip install -r requirements-lock.txt
```
