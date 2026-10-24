# Supabase 資料串接

目標專案：`pxglzzlihfhdjulegxag`。

## 首次設定

1. 在 Supabase SQL Editor 執行 `supabase/migrations/202610240001_kootree.sql`。
   此 SQL 新增三個 `kootree_` 資料表及切換快照函式，不修改既有資料表。
2. 在專案目錄執行：

   ```powershell
   Copy-Item .env.example .env
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. 在 `.env` 填入專案 Settings → API Keys 的後端 Secret key：

   ```dotenv
   KOOTREE_DATA_SOURCE=local
   SUPABASE_URL=https://pxglzzlihfhdjulegxag.supabase.co
   SUPABASE_SECRET_KEY=填入後端金鑰
   ```

   也支援舊版 `SUPABASE_SERVICE_ROLE_KEY`。金鑰只由 Python 伺服器讀取；
   不可放入 assets、前端、GitHub 或聊天。`.env` 已被 Git 忽略。
   anon/publishable key 無法讀取這些資料表。
4. 匯入資料：

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.supabase_store
   ```

5. 將 `.env` 的 `KOOTREE_DATA_SOURCE` 改成 `supabase`，重新啟動網站：

   ```powershell
   .\.venv\Scripts\python.exe -c "from app import app; app.run(host='127.0.0.1', port=8050, debug=False)"
   ```

   畫面資料來源會加註 Supabase。設定錯誤或資料不完整時啟動失敗，
   不會悄悄改用示範資料。恢復本機 CSV：改回 `local` 並重新啟動。

## 資料範圍與更新

- `trees`：優先使用 `data/trees_clean.csv`，不存在才使用明確標記的示範 CSV。
- `official_cases`：官方移除／移植 GeoJSON，保留來源、授權、座標與缺失值。
- 通報、風險、巡檢及工單仍由原程式產生並標記為模擬；未冒充真實業務紀錄。
- 原始 CSV、地圖樣式、圖片、簡報及尚未接入主站的社群觀察檔不匯入。
- 儲存採 JSONB 快照，保留原欄位與順序；不是可編修的業務關聯模型。
- 每次匯入建立新版本，分批完成並核對筆數後才切換該資料集。
  行道樹與官方說明各自切換；失敗資料集保留上一版，已完成資料集不回滾。
  舊版保留，不自動刪除；重複匯入會增加儲存量。
- 網站按伺服器程序快取，更新匯入後須重新啟動；不提供即時訂閱。
- RLS 啟用且不提供匿名或登入使用者的直接讀寫權限，由後端金鑰讀取。
  現有網站公開呈現的欄位與 CSV 匯出仍可供網站訪客讀取。

目前專案以全量 Pandas 分析運作；約九萬筆行道樹首次啟動需要分頁下載，
速度依網路與 Supabase 配額而定。
