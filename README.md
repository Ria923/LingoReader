# LingoReader — Vercel 修正版

這個版本修正了 Vercel `FUNCTION_INVOCATION_FAILED` 問題。

## 修正內容

- FastAPI 啟動時不再依賴 `public/static` 資料夾存在。
- HTML、CSS、JavaScript 內建於 Python Function，避免 Vercel 打包時漏掉靜態檔案而崩潰。
- 移除不必要的 `functions/includeFiles` 設定，改用 Vercel 對 FastAPI 的零設定偵測。
- 新增 `/health` 健康檢查網址。
- `public` 資料夾仍保留，方便 Vercel 或其他平台直接提供靜態頁面。

## 更新現有 GitHub 專案

1. 解壓縮 ZIP。
2. 打開 GitHub 的 `LingoReader` repository。
3. 按 `Add file` → `Upload files`。
4. 把本資料夾內的全部檔案與 `public` 資料夾拖進去。
5. 按 `Commit changes`。
6. Vercel 會自動重新部署。

## Vercel 環境變數

可選：

- `GEMINI_API_KEY`：啟用句子翻譯、文法與慣用語解析。
- `GEMINI_MODEL`：預設 `gemini-2.5-flash-lite`。
- `APP_ACCESS_CODE`：保護網站，避免陌生人消耗 Gemini 額度。

沒有 Gemini Key 時，示範文章、瀏覽器朗讀、免費字典與單字本仍可使用。
