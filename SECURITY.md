# 安全說明

本專案是可閱讀的網站原始碼，不包含 Windows 可執行程式。

## 不包含

- `.exe`
- `.bat`
- `.cmd`
- `.dll`
- PowerShell 腳本
- 安裝程式
- 背景常駐程式

## 外部連線

網站只在需要時連線到：

- 使用者輸入的公開 HTTP／HTTPS 英文文章網址
- `api.dictionaryapi.dev`：免費英英字典
- `generativelanguage.googleapis.com`：只有按下句子 AI 解析時才呼叫 Gemini

## 金鑰

`GEMINI_API_KEY` 只能設定在 Vercel 的 Environment Variables。後端不會把金鑰回傳到前端，也不要將真實金鑰提交到 GitHub。

## 本機資料

收藏單字存在使用者自己的瀏覽器 Local Storage。網站不會上傳整本單字本。
