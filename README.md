# LingoReader — Vercel 免費工具版

這是純網頁／伺服器程式碼，沒有 `.bat`、`.exe`、`.cmd` 或 `.dll`，不需要在 Windows 執行任何程式。

## 哪些功能完全免費、不需要 API Key？

- 英文句子與單字朗讀：瀏覽器內建 Web Speech API
- 單字音標、詞性、英英解釋、例句：DictionaryAPI.dev
- 單字收藏、搜尋與 CSV 匯出：瀏覽器 Local Storage
- 貼英文文章網址並擷取正文：LingoReader 自己的 Vercel 後端

## 哪個功能需要免費 Gemini API Key？

只有按下「翻譯並解析這句」時，才會使用 Gemini：

- 自然整句翻譯
- 白話句意
- 句子結構
- 文法與句型
- 慣用語、片語與搭配詞
- 重點單字

程式已完全移除 OpenAI API。預設模型為 `gemini-2.5-flash-lite`。

## 部署到 Vercel

1. 在 GitHub 網頁建立新的空白 repository。
2. 解壓縮 ZIP，把 `LingoReader_Vercel` 資料夾**裡面的檔案**全部拖進 repository 並 Commit。
3. 到 Vercel 選 **Add New → Project**，匯入該 repository，按 **Deploy**。
4. 先不用設定任何 Key，也能測試文章、朗讀、字典和單字本。
5. 要啟用整句 AI 解析，再到 Google AI Studio 建立 Gemini API Key。
6. 到 Vercel 專案的 **Settings → Environment Variables** 新增：
   - `GEMINI_API_KEY`：Google AI Studio 建立的金鑰
   - `GEMINI_MODEL`：`gemini-2.5-flash-lite`（可省略，已有預設值）
   - `APP_ACCESS_CODE`：你自訂的網站使用密碼（選填但建議）
7. 新增環境變數後，在 Vercel 重新 Deploy。

> Gemini 免費層的模型與額度可能由 Google 調整。即使免費額度暫時用完，朗讀、免費字典、文章閱讀和單字本仍可繼續使用。

## 安全設計

- Gemini Key 只由 `app.py` 在 Vercel 後端讀取，不會傳到瀏覽器。
- 真實 Key 不應寫進 `.env.example`、GitHub 或前端 JavaScript。
- `APP_ACCESS_CODE` 可避免公開網址被陌生人消耗 Gemini 額度。
- 文章網址會阻擋 localhost、私人 IP 和內部網路位址，降低 SSRF 風險。

## 主要檔案

- `app.py`：FastAPI、文章擷取、免費字典代理、Gemini 句子解析
- `public/index.html`：網站畫面
- `public/static/app.js`：互動、朗讀、單字本
- `public/static/styles.css`：版面樣式
- `vercel.json`：Vercel 路由與安全標頭
- `.env.example`：環境變數名稱範例，不含真實金鑰
