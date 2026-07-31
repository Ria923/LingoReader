# LingoReader — Liquid Glass Design

這是可直接覆蓋到現有 GitHub／Vercel 專案的視覺改版。後端功能與原本英中字典、Gemini 句子解析完全保留，主要更新前端設計。

## 視覺改版

- 全螢幕循環影片背景，並套用灰階、暗化與顆粒效果。
- Poppins 作為主要字體，Source Serif 4 作為斜體標題點綴。
- 全站嚴格黑白灰色系，沒有彩色強調色。
- 兩種 Liquid Glass：一般薄玻璃與高模糊強玻璃。
- 桌面雙欄佈局：左側文章匯入／閱讀，右側句子解析／字典／單字本。
- 手機版自動改成上下排列，不會隱藏學習功能。
- 所有主要按鈕都有縮放互動效果。
- 系統設定「減少動態效果」時，會停用背景影片並使用靜態深色背景。

背景影片使用使用者提供的外部網址。若影片載入失敗，頁面仍會以內建灰階漸層背景正常顯示。

## 保留功能

- 貼網址擷取英文文章。
- 直接貼上文章文字。
- 點單字看繁體中文意思、英文定義與例句。
- 瀏覽器免費英文朗讀。
- 收藏、搜尋、移除與匯出單字。
- Gemini 整句翻譯、句型、文法與慣用語解析。
- `APP_ACCESS_CODE` 網站密碼保護。

## 覆蓋現有 GitHub 專案

1. 解壓縮 ZIP。
2. 進入 GitHub 的 `LingoReader` repository。
3. 按 `Add file` → `Upload files`。
4. 把本資料夾**裡面的全部檔案與資料夾**拖入上傳頁面。
5. 按 `Commit changes`。
6. 已連接 GitHub 的 Vercel 會自動重新部署。

不需要刪除原本的 Vercel 專案，也不用重新設定 Gemini Key。

## Vercel 環境變數

- `GEMINI_API_KEY`：啟用整句翻譯與文法解析。
- `GEMINI_MODEL`：預設 `gemini-2.5-flash-lite`。
- `APP_ACCESS_CODE`：選填，保護公開網站。

沒有 Gemini Key 時，文章閱讀、免費朗讀、英中字典與單字本仍可使用。

## 部署結構

HTML、CSS、JavaScript 同時保留在 `public` 資料夾，並內嵌於 `app.py`。這是為了避免 Vercel 打包 Python Function 時遺漏靜態檔案而造成 `FUNCTION_INVOCATION_FAILED`。
