from __future__ import annotations

import html
import hmac
import ipaddress
import json
import os
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from fastapi import FastAPI, Header, HTTPException, Request as FastAPIRequest
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

INDEX_HTML = '<!doctype html>\n<html lang="zh-Hant">\n<head>\n  <meta charset="utf-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1" />\n  <title>LingoReader｜互動式英文閱讀器</title>\n  <link rel="preconnect" href="https://fonts.googleapis.com">\n  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;600;700&display=swap" rel="stylesheet">\n  <link rel="stylesheet" href="/static/styles.css" />\n</head>\n<body>\n  <div class="app-shell">\n    <header class="topbar">\n      <div class="brand">\n        <div class="logo">L</div>\n        <div>\n          <strong>LingoReader</strong>\n          <span>把任何英文文章變成你的互動教材</span>\n        </div>\n      </div>\n      <div class="top-actions">\n        <span id="aiStatus" class="status-pill">檢查 AI…</span>\n        <button class="ghost-btn" id="openVocabBtn">單字本 <b id="vocabCount">0</b></button>\n      </div>\n    </header>\n\n    <section class="import-card">\n      <div class="import-heading">\n        <div>\n          <span class="eyebrow">READ · CLICK · LEARN</span>\n          <h1>貼上文章網址，開始拆解英文。</h1>\n        </div>\n        <div class="settings-row">\n          <label>程度\n            <select id="levelSelect">\n              <option>A1</option><option selected>A2</option><option>B1</option>\n              <option>B2</option><option>C1</option>\n            </select>\n          </label>\n          <label>翻譯\n            <select id="languageSelect">\n              <option selected>繁體中文</option><option>日文</option><option>英文</option>\n            </select>\n          </label>\n        </div>\n      </div>\n      <div class="url-row">\n        <span class="link-icon">↗</span>\n        <input id="urlInput" type="url" placeholder="https://example.com/an-english-article" />\n        <button id="loadBtn" class="primary-btn">生成互動文章</button>\n      </div>\n      <div class="import-footer">\n        <button id="pasteModeBtn" class="text-btn">網站抓不到？改成貼上文章文字</button>\n        <span>部分付費牆或登入網站無法自動讀取</span>\n      </div>\n      <div id="pastePanel" class="paste-panel hidden">\n        <input id="manualTitle" placeholder="文章標題（可不填）" />\n        <textarea id="manualText" rows="7" placeholder="把英文文章貼在這裡…"></textarea>\n        <button id="useTextBtn" class="secondary-btn">使用這篇文字</button>\n      </div>\n    </section>\n\n    <main class="workspace">\n      <section class="reader-panel">\n        <div id="emptyState" class="empty-state">\n          <div class="empty-illustration">\n            <span>word</span><span>phrase</span><span>grammar</span>\n            <div>Aa</div>\n          </div>\n          <h2>你的文章會出現在這裡</h2>\n          <p>點單字查字典，點句子看翻譯、慣用語與文法。</p>\n          <button id="demoBtn" class="secondary-btn">先看示範文章</button>\n        </div>\n        <article id="articleView" class="article-view hidden">\n          <div class="article-meta">\n            <span id="sourceHost"></span>\n            <span id="articleDate"></span>\n          </div>\n          <h2 id="articleTitle"></h2>\n          <p id="articleAuthor" class="author"></p>\n          <div class="reader-help">\n            <span><i class="dot word-dot"></i> 點單字查意思</span>\n            <span><i class="dot sentence-dot"></i> 點空白處選整句</span>\n          </div>\n          <div id="articleBody" class="article-body"></div>\n        </article>\n      </section>\n\n      <aside class="study-panel">\n        <div class="study-tabs">\n          <button class="tab active" data-tab="analysis">句子解析</button>\n          <button class="tab" data-tab="dictionary">字典</button>\n          <button class="tab" data-tab="vocabulary">單字本</button>\n        </div>\n\n        <div id="analysisTab" class="tab-content active">\n          <div id="analysisEmpty" class="panel-empty">\n            <div class="panel-icon">⌁</div>\n            <h3>選擇一個句子</h3>\n            <p>點文章中的句子，我會顯示翻譯、結構、文法與慣用語。</p>\n          </div>\n          <div id="analysisContent" class="hidden">\n            <div class="selected-card">\n              <div class="card-label">SELECTED SENTENCE</div>\n              <p id="selectedSentence"></p>\n              <button id="speakSentenceBtn" class="icon-btn" title="朗讀">▶</button>\n            </div>\n            <button id="analyzeBtn" class="primary-btn full">翻譯並解析這句</button>\n            <div id="analysisLoading" class="loading hidden"><span></span>正在拆解句子…</div>\n            <div id="analysisResult"></div>\n          </div>\n        </div>\n\n        <div id="dictionaryTab" class="tab-content">\n          <div id="dictionaryEmpty" class="panel-empty">\n            <div class="panel-icon">Aa</div>\n            <h3>點一個英文單字</h3>\n            <p>查看發音、詞性、英文解釋與例句。</p>\n          </div>\n          <div id="dictionaryContent" class="hidden"></div>\n        </div>\n\n        <div id="vocabularyTab" class="tab-content">\n          <div class="vocab-toolbar">\n            <input id="vocabSearch" placeholder="搜尋收藏的單字" />\n            <button id="exportBtn" class="ghost-btn small">匯出 CSV</button>\n          </div>\n          <div id="vocabList"></div>\n        </div>\n      </aside>\n    </main>\n  </div>\n\n  <div id="toast" class="toast"></div>\n  <script src="/static/app.js"></script>\n</body>\n</html>\n'
STYLES_CSS = ':root {\n  --ink: #1f2930;\n  --muted: #718079;\n  --paper: #fffdf8;\n  --cream: #f4f0e7;\n  --line: #ded8ca;\n  --green: #385f50;\n  --green-dark: #24483b;\n  --mint: #dceae3;\n  --orange: #e9904b;\n  --shadow: 0 18px 55px rgba(41, 56, 47, .10);\n}\n* { box-sizing: border-box; }\nbody {\n  margin: 0;\n  color: var(--ink);\n  background: radial-gradient(circle at 12% 0%, #f4ead7 0, transparent 32%), #eef1ec;\n  font-family: "DM Sans", "Noto Sans TC", sans-serif;\n}\nbutton, input, textarea, select { font: inherit; }\nbutton { cursor: pointer; }\n.hidden { display: none !important; }\n.app-shell { max-width: 1540px; margin: 0 auto; padding: 22px; }\n.topbar { display: flex; justify-content: space-between; align-items: center; padding: 4px 6px 22px; }\n.brand { display: flex; align-items: center; gap: 12px; }\n.logo { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 13px; background: var(--green); color: white; font-weight: 700; font-size: 22px; transform: rotate(-4deg); }\n.brand strong { display: block; font-size: 19px; }\n.brand span { display: block; color: var(--muted); font-size: 12px; margin-top: 2px; }\n.top-actions { display: flex; align-items: center; gap: 10px; }\n.status-pill { padding: 8px 11px; border-radius: 999px; background: rgba(255,255,255,.7); border: 1px solid var(--line); font-size: 12px; color: var(--muted); }\n.status-pill.ready { background: #dfefe5; color: #276045; border-color: #bad8c6; }\n.status-pill.off { background: #f4e9dc; color: #805532; border-color: #e7cdb2; }\n.ghost-btn, .secondary-btn, .text-btn, .icon-btn { border: 0; background: transparent; color: var(--green); }\n.ghost-btn { padding: 9px 13px; border: 1px solid var(--line); border-radius: 10px; background: rgba(255,255,255,.62); }\n.ghost-btn b { background: var(--green); color: white; border-radius: 999px; padding: 1px 6px; margin-left: 4px; font-size: 11px; }\n.import-card { background: var(--paper); border: 1px solid rgba(189,180,163,.65); border-radius: 24px; padding: 26px; box-shadow: var(--shadow); margin-bottom: 20px; }\n.import-heading { display: flex; justify-content: space-between; gap: 20px; align-items: end; }\n.eyebrow { color: var(--orange); font-size: 11px; font-weight: 700; letter-spacing: .17em; }\nh1 { margin: 7px 0 18px; font-size: clamp(25px, 3vw, 40px); letter-spacing: -.045em; }\n.settings-row { display: flex; gap: 10px; padding-bottom: 18px; }\n.settings-row label { color: var(--muted); font-size: 12px; }\nselect { display: block; margin-top: 5px; border: 1px solid var(--line); background: white; border-radius: 9px; padding: 8px 28px 8px 9px; color: var(--ink); }\n.url-row { display: grid; grid-template-columns: 28px 1fr auto; align-items: center; border: 1px solid var(--line); background: white; border-radius: 15px; padding: 7px; }\n.link-icon { text-align: center; color: var(--orange); font-weight: 700; }\n.url-row input { min-width: 0; border: 0; outline: 0; padding: 11px 8px; color: var(--ink); }\n.primary-btn { border: 0; border-radius: 11px; padding: 12px 17px; background: var(--green); color: white; font-weight: 700; box-shadow: 0 6px 15px rgba(56,95,80,.2); }\n.primary-btn:hover { background: var(--green-dark); }\n.primary-btn:disabled { opacity: .6; cursor: wait; }\n.primary-btn.full { width: 100%; margin-top: 10px; }\n.import-footer { display: flex; justify-content: space-between; gap: 15px; padding: 10px 3px 0; font-size: 12px; color: var(--muted); }\n.text-btn { padding: 0; text-decoration: underline; text-underline-offset: 3px; }\n.paste-panel { margin-top: 16px; padding-top: 16px; border-top: 1px dashed var(--line); }\n.paste-panel input, .paste-panel textarea, .vocab-toolbar input { width: 100%; border: 1px solid var(--line); border-radius: 10px; padding: 11px; outline: 0; margin-bottom: 9px; background: white; }\n.secondary-btn { border: 1px solid var(--green); border-radius: 10px; padding: 10px 15px; font-weight: 700; }\n.workspace { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(355px, .72fr); gap: 20px; align-items: start; }\n.reader-panel, .study-panel { background: var(--paper); border: 1px solid rgba(189,180,163,.65); border-radius: 24px; box-shadow: var(--shadow); min-height: 650px; }\n.reader-panel { padding: 38px clamp(24px, 5vw, 72px); }\n.study-panel { position: sticky; top: 18px; overflow: hidden; }\n.empty-state { min-height: 565px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; }\n.empty-state h2 { margin: 18px 0 7px; }\n.empty-state p { margin: 0 0 20px; color: var(--muted); }\n.empty-illustration { width: 210px; height: 170px; position: relative; border: 1px solid var(--line); background: #f7f2e9; border-radius: 22px; display: grid; place-items: center; transform: rotate(-1deg); }\n.empty-illustration div { width: 80px; height: 80px; display: grid; place-items: center; border-radius: 50%; background: var(--mint); color: var(--green); font-size: 32px; font-weight: 700; }\n.empty-illustration span { position: absolute; background: white; border: 1px solid var(--line); border-radius: 999px; padding: 5px 9px; font-size: 11px; color: var(--muted); }\n.empty-illustration span:nth-child(1) { top: 14px; left: 20px; transform: rotate(-8deg); }\n.empty-illustration span:nth-child(2) { top: 35px; right: 10px; transform: rotate(7deg); }\n.empty-illustration span:nth-child(3) { bottom: 14px; left: 27px; transform: rotate(4deg); }\n.article-meta { display: flex; gap: 12px; color: var(--orange); font-size: 11px; text-transform: uppercase; letter-spacing: .12em; font-weight: 700; }\n.article-view h2 { margin: 12px 0 8px; font-size: clamp(29px, 4vw, 48px); line-height: 1.08; letter-spacing: -.045em; font-family: Georgia, serif; }\n.author { color: var(--muted); margin: 0 0 24px; }\n.reader-help { display: flex; gap: 18px; padding: 12px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); color: var(--muted); font-size: 12px; }\n.dot { width: 7px; height: 7px; display: inline-block; border-radius: 50%; margin-right: 5px; }\n.word-dot { background: var(--orange); }.sentence-dot { background: var(--green); }\n.article-body { font-family: Georgia, "Noto Sans TC", serif; font-size: 20px; line-height: 1.92; color: #303a35; padding-top: 18px; }\n.article-body p { margin: 0 0 1.55em; }\n.sentence { border-radius: 5px; transition: background .15s ease; cursor: pointer; }\n.sentence:hover { background: #edf3ef; }\n.sentence.selected { background: #dfece5; box-shadow: 0 0 0 2px #dfece5; }\n.word { border-radius: 4px; cursor: pointer; transition: background .12s; }\n.word:hover { background: #f7d8ba; }\n.word.saved { background: #f8e7a8; border-bottom: 1px solid #c79e25; }\n.study-tabs { display: grid; grid-template-columns: repeat(3, 1fr); border-bottom: 1px solid var(--line); background: #f8f5ef; }\n.tab { border: 0; background: transparent; padding: 16px 8px; color: var(--muted); font-weight: 600; font-size: 13px; position: relative; }\n.tab.active { color: var(--green); }\n.tab.active::after { content: ""; position: absolute; left: 18px; right: 18px; bottom: -1px; height: 3px; background: var(--green); border-radius: 4px 4px 0 0; }\n.tab-content { display: none; padding: 22px; max-height: calc(100vh - 100px); overflow: auto; }\n.tab-content.active { display: block; }\n.panel-empty { min-height: 530px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }\n.panel-empty h3 { margin: 12px 0 7px; }\n.panel-empty p { max-width: 270px; margin: 0; color: var(--muted); font-size: 14px; line-height: 1.6; }\n.panel-icon { width: 54px; height: 54px; display: grid; place-items: center; border-radius: 16px; background: var(--mint); color: var(--green); font-size: 23px; font-weight: 700; }\n.selected-card { background: #f4f0e7; border: 1px solid var(--line); border-radius: 14px; padding: 14px 42px 14px 14px; position: relative; }\n.card-label, .section-label { color: var(--orange); font-size: 10px; letter-spacing: .13em; font-weight: 700; }\n.selected-card p { margin: 7px 0 0; line-height: 1.55; font-family: Georgia, serif; }\n.icon-btn { position: absolute; right: 10px; top: 11px; width: 30px; height: 30px; border-radius: 50%; background: white; border: 1px solid var(--line); }\n.loading { padding: 20px 4px; color: var(--muted); font-size: 13px; }\n.loading span { display: inline-block; width: 11px; height: 11px; border: 2px solid #b9c9c0; border-top-color: var(--green); border-radius: 50%; margin-right: 7px; animation: spin .7s linear infinite; }\n@keyframes spin { to { transform: rotate(360deg); } }\n.result-section { padding: 17px 2px; border-bottom: 1px solid var(--line); }\n.result-section h4 { margin: 5px 0 8px; font-size: 14px; }\n.result-section p { margin: 0; line-height: 1.65; font-size: 14px; }\n.translation { font-size: 18px !important; font-weight: 600; color: var(--green-dark); }\n.analysis-list { display: grid; gap: 9px; }\n.analysis-item { border-left: 3px solid var(--mint); padding-left: 10px; }\n.analysis-item strong { display: block; font-size: 13px; margin-bottom: 2px; }\n.analysis-item span { color: #59675f; font-size: 13px; line-height: 1.55; }\n.dict-head { display: flex; justify-content: space-between; gap: 12px; align-items: start; padding-bottom: 16px; border-bottom: 1px solid var(--line); }\n.dict-word { font-family: Georgia, serif; font-size: 34px; margin: 0; }\n.phonetic { color: var(--orange); margin-top: 3px; }\n.save-btn { border: 1px solid var(--green); background: white; color: var(--green); border-radius: 10px; padding: 9px 12px; font-weight: 700; }\n.save-btn.saved { background: var(--green); color: white; }\n.meaning-block { padding: 15px 0; border-bottom: 1px solid var(--line); }\n.part { color: var(--orange); font-size: 12px; font-weight: 700; font-style: italic; }\n.definition { margin: 8px 0; font-size: 14px; line-height: 1.55; }\n.example { color: var(--muted); font-size: 13px; font-style: italic; margin-top: 4px; }\n.vocab-toolbar { display: flex; gap: 8px; }\n.vocab-toolbar input { margin: 0; }\n.ghost-btn.small { white-space: nowrap; padding: 8px 10px; }\n.vocab-card { border-bottom: 1px solid var(--line); padding: 14px 2px; }\n.vocab-card-head { display: flex; justify-content: space-between; align-items: center; }\n.vocab-card h4 { margin: 0; font-size: 18px; font-family: Georgia, serif; }\n.vocab-card p { margin: 5px 0 0; color: var(--muted); font-size: 13px; line-height: 1.45; }\n.remove-btn { border: 0; background: transparent; color: #9b6c5d; }\n.toast { position: fixed; left: 50%; bottom: 25px; transform: translate(-50%, 20px); padding: 11px 16px; border-radius: 10px; background: #26352e; color: white; box-shadow: var(--shadow); opacity: 0; pointer-events: none; transition: .2s; z-index: 30; font-size: 13px; }\n.toast.show { opacity: 1; transform: translate(-50%, 0); }\n@media (max-width: 970px) {\n  .workspace { grid-template-columns: 1fr; }\n  .study-panel { position: static; min-height: 500px; }\n  .import-heading { align-items: start; flex-direction: column; }\n  .settings-row { padding: 0; }\n}\n@media (max-width: 620px) {\n  .app-shell { padding: 10px; }\n  .brand span, .status-pill { display: none; }\n  .import-card, .reader-panel, .study-panel { border-radius: 16px; }\n  .import-card { padding: 18px; }\n  .url-row { grid-template-columns: 24px 1fr; }\n  .url-row .primary-btn { grid-column: 1 / -1; }\n  .import-footer { flex-direction: column; }\n  .reader-panel { padding: 26px 19px; }\n  .article-body { font-size: 18px; }\n}\n'
APP_JS = 'const $ = (selector) => document.querySelector(selector);\nconst $$ = (selector) => [...document.querySelectorAll(selector)];\n\nconst state = {\n  article: null,\n  selectedSentence: "",\n  selectedElement: null,\n  dictionaryData: null,\n  vocabulary: JSON.parse(localStorage.getItem("lingoreader-vocabulary") || "[]"),\n};\n\nconst demoArticle = {\n  title: "Why Small Habits Matter More Than Big Plans",\n  author: "LingoReader Demo",\n  date: "",\n  url: "https://demo.local/small-habits",\n  paragraphs: [\n    "People often believe that meaningful change requires a dramatic plan. In reality, small actions repeated consistently can shape our lives more powerfully than a burst of motivation.",\n    "A habit may feel insignificant at first, but it reduces the number of decisions we need to make. Once an action becomes automatic, we can spend our attention on more difficult problems.",\n    "The key is not to aim for perfection. It is to create a system that is easy enough to continue, even on days when we feel tired or distracted."\n  ]\n};\n\nfunction toast(message) {\n  const node = $("#toast");\n  node.textContent = message;\n  node.classList.add("show");\n  clearTimeout(node.timer);\n  node.timer = setTimeout(() => node.classList.remove("show"), 2200);\n}\n\nfunction setLoading(button, loading, label) {\n  if (!button.dataset.original) button.dataset.original = button.textContent;\n  button.disabled = loading;\n  button.textContent = loading ? label : button.dataset.original;\n}\n\nfunction getAccessCode() {\n  return localStorage.getItem("lingoreader-access-code") || "";\n}\n\nasync function apiFetch(url, options = {}, allowRetry = true) {\n  const headers = new Headers(options.headers || {});\n  const code = getAccessCode();\n  if (code) headers.set("X-App-Code", code);\n\n  const response = await fetch(url, { ...options, headers });\n  if (response.status === 401 && allowRetry) {\n    const data = await response.clone().json().catch(() => ({}));\n    if (data.requiresAccessCode) {\n      const entered = window.prompt("請輸入你在 Vercel 設定的 APP_ACCESS_CODE：", code);\n      if (entered !== null && entered.trim()) {\n        localStorage.setItem("lingoreader-access-code", entered.trim());\n        return apiFetch(url, options, false);\n      }\n    }\n  }\n  return response;\n}\n\nfunction saveVocabulary() {\n  localStorage.setItem("lingoreader-vocabulary", JSON.stringify(state.vocabulary));\n  updateVocabCount();\n  renderVocabulary();\n  refreshSavedHighlights();\n}\n\nfunction updateVocabCount() {\n  $("#vocabCount").textContent = state.vocabulary.length;\n}\n\nfunction isSaved(word) {\n  return state.vocabulary.some(item => item.word.toLowerCase() === word.toLowerCase());\n}\n\nfunction refreshSavedHighlights() {\n  $$(".word").forEach(node => node.classList.toggle("saved", isSaved(node.dataset.word)));\n}\n\nfunction switchTab(name) {\n  $$(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.tab === name));\n  $$(".tab-content").forEach(content => content.classList.remove("active"));\n  $("#" + name + "Tab").classList.add("active");\n}\n\nfunction splitSentences(text) {\n  if (window.Intl?.Segmenter) {\n    const segmenter = new Intl.Segmenter("en", { granularity: "sentence" });\n    return [...segmenter.segment(text)].map(x => x.segment).filter(Boolean);\n  }\n  return text.match(/[^.!?]+[.!?]+[”’\\"]?|[^.!?]+$/g) || [text];\n}\n\nfunction tokenizeSentence(sentence) {\n  const fragment = document.createDocumentFragment();\n  const pieces = sentence.split(/([A-Za-z]+(?:[’\'][A-Za-z]+)*(?:-[A-Za-z]+)*)/g);\n  pieces.forEach(piece => {\n    if (/^[A-Za-z]+(?:[’\'][A-Za-z]+)*(?:-[A-Za-z]+)*$/.test(piece)) {\n      const word = document.createElement("span");\n      word.className = "word" + (isSaved(piece) ? " saved" : "");\n      word.dataset.word = piece;\n      word.textContent = piece;\n      word.addEventListener("click", event => {\n        event.stopPropagation();\n        lookupWord(piece);\n      });\n      fragment.appendChild(word);\n    } else {\n      fragment.appendChild(document.createTextNode(piece));\n    }\n  });\n  return fragment;\n}\n\nfunction renderArticle(article) {\n  state.article = article;\n  $("#emptyState").classList.add("hidden");\n  $("#articleView").classList.remove("hidden");\n  $("#articleTitle").textContent = article.title || "Untitled article";\n  $("#articleAuthor").textContent = article.author ? `By ${article.author}` : "";\n  $("#articleDate").textContent = article.date || "";\n  try { $("#sourceHost").textContent = new URL(article.url).hostname.replace(/^www\\./, ""); }\n  catch { $("#sourceHost").textContent = "PASTED ARTICLE"; }\n\n  const body = $("#articleBody");\n  body.innerHTML = "";\n  article.paragraphs.forEach(paragraphText => {\n    const p = document.createElement("p");\n    splitSentences(paragraphText).forEach(sentenceText => {\n      const sentence = document.createElement("span");\n      sentence.className = "sentence";\n      sentence.dataset.sentence = sentenceText.trim();\n      sentence.appendChild(tokenizeSentence(sentenceText));\n      sentence.addEventListener("click", () => selectSentence(sentence.dataset.sentence, sentence));\n      p.appendChild(sentence);\n    });\n    body.appendChild(p);\n  });\n  window.scrollTo({ top: document.querySelector(".workspace").offsetTop - 14, behavior: "smooth" });\n}\n\nfunction selectSentence(text, element) {\n  if (!text) return;\n  if (state.selectedElement) state.selectedElement.classList.remove("selected");\n  state.selectedElement = element;\n  element.classList.add("selected");\n  state.selectedSentence = text;\n  $("#selectedSentence").textContent = text;\n  $("#analysisEmpty").classList.add("hidden");\n  $("#analysisContent").classList.remove("hidden");\n  $("#analysisResult").innerHTML = "";\n  switchTab("analysis");\n}\n\nasync function loadArticleFromUrl() {\n  const url = $("#urlInput").value.trim();\n  if (!url) return toast("先貼上文章網址");\n  const button = $("#loadBtn");\n  setLoading(button, true, "正在抓取文章…");\n  try {\n    const response = await apiFetch("/api/article", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify({ url })\n    });\n    const data = await response.json();\n    if (!response.ok) throw new Error(data.error || "無法讀取文章");\n    renderArticle(data);\n    toast("互動文章已生成");\n  } catch (error) {\n    toast(error.message);\n    $("#pastePanel").classList.remove("hidden");\n  } finally {\n    setLoading(button, false);\n  }\n}\n\nasync function lookupWord(word) {\n  switchTab("dictionary");\n  $("#dictionaryEmpty").classList.add("hidden");\n  const panel = $("#dictionaryContent");\n  panel.classList.remove("hidden");\n  panel.innerHTML = `<div class="loading"><span></span>正在查 ${escapeHtml(word)}…</div>`;\n  try {\n    const response = await apiFetch("/api/dictionary", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify({ word })\n    });\n    const data = await response.json();\n    if (!response.ok) throw new Error(data.error || "查詢失敗");\n    state.dictionaryData = data;\n    renderDictionary(data);\n  } catch (error) {\n    panel.innerHTML = `<div class="panel-empty"><div class="panel-icon">!</div><h3>查不到</h3><p>${escapeHtml(error.message)}</p></div>`;\n  }\n}\n\nfunction renderDictionary(data) {\n  if (data.notFound) {\n    $("#dictionaryContent").innerHTML = `<div class="panel-empty"><div class="panel-icon">?</div><h3>${escapeHtml(data.word)}</h3><p>免費字典沒有找到這個詞，可能是專有名詞或變化形。</p></div>`;\n    return;\n  }\n  const saved = isSaved(data.word);\n  const meanings = (data.meanings || []).map(meaning => `\n    <div class="meaning-block">\n      <div class="part">${escapeHtml(meaning.partOfSpeech)}</div>\n      ${(meaning.definitions || []).map((d, i) => `\n        <div class="definition"><b>${i + 1}.</b> ${escapeHtml(d.definition)}\n          ${d.example ? `<div class="example">“${escapeHtml(d.example)}”</div>` : ""}\n        </div>`).join("")}\n    </div>`).join("");\n  $("#dictionaryContent").innerHTML = `\n    <div class="dict-head">\n      <div><h3 class="dict-word">${escapeHtml(data.word)}</h3><div class="phonetic">${escapeHtml(data.phonetic || "")}</div></div>\n      <div>\n        <button class="icon-btn" style="position:static" id="playWordBtn" title="免費朗讀單字">▶</button>\n        <button class="save-btn ${saved ? "saved" : ""}" id="saveWordBtn">${saved ? "已收藏" : "+ 加入單字本"}</button>\n      </div>\n    </div>\n    ${meanings || `<p class="panel-empty">沒有可顯示的定義。</p>`}`;\n  $("#saveWordBtn").addEventListener("click", () => toggleSaveWord(data));\n  $("#playWordBtn").addEventListener("click", () => {\n    if (data.audio) {\n      const audio = new Audio(data.audio);\n      audio.play().catch(() => speak(data.word));\n    } else {\n      speak(data.word);\n    }\n  });\n}\n\nfunction toggleSaveWord(data) {\n  const index = state.vocabulary.findIndex(item => item.word.toLowerCase() === data.word.toLowerCase());\n  if (index >= 0) {\n    state.vocabulary.splice(index, 1);\n    toast("已從單字本移除");\n  } else {\n    const firstMeaning = data.meanings?.[0];\n    const firstDefinition = firstMeaning?.definitions?.[0]?.definition || "";\n    state.vocabulary.unshift({\n      word: data.word,\n      phonetic: data.phonetic || "",\n      partOfSpeech: firstMeaning?.partOfSpeech || "",\n      definition: firstDefinition,\n      sentence: state.selectedSentence || "",\n      createdAt: new Date().toISOString()\n    });\n    toast("已加入單字本");\n  }\n  saveVocabulary();\n  renderDictionary(data);\n}\n\nasync function analyzeSentence() {\n  if (!state.selectedSentence) return toast("請先選擇句子");\n  const button = $("#analyzeBtn");\n  $("#analysisLoading").classList.remove("hidden");\n  $("#analysisResult").innerHTML = "";\n  setLoading(button, true, "解析中…");\n  try {\n    const response = await apiFetch("/api/analyze", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify({\n        sentence: state.selectedSentence,\n        level: $("#levelSelect").value,\n        targetLanguage: $("#languageSelect").value\n      })\n    });\n    const data = await response.json();\n    if (!response.ok) throw new Error(data.error || "解析失敗");\n    renderAnalysis(data);\n  } catch (error) {\n    $("#analysisResult").innerHTML = `<div class="result-section"><div class="section-label">無法解析</div><p>${escapeHtml(error.message)}</p></div>`;\n  } finally {\n    $("#analysisLoading").classList.add("hidden");\n    setLoading(button, false);\n  }\n}\n\nfunction renderItems(items, titleKey, bodyKey) {\n  if (!items?.length) return `<p>這句沒有特別需要補充的內容。</p>`;\n  return `<div class="analysis-list">${items.map(item => `\n    <div class="analysis-item"><strong>${escapeHtml(item[titleKey] || "")}</strong><span>${escapeHtml(item[bodyKey] || "")}${item.example ? `<br>例：${escapeHtml(item.example)}` : ""}</span></div>\n  `).join("")}</div>`;\n}\n\nfunction renderAnalysis(data) {\n  $("#analysisResult").innerHTML = `\n    <section class="result-section"><div class="section-label">自然翻譯</div><p class="translation">${escapeHtml(data.translation || "")}</p></section>\n    <section class="result-section"><div class="section-label">這句在說什麼</div><p>${escapeHtml(data.plainMeaning || "")}</p></section>\n    <section class="result-section"><div class="section-label">句子結構</div><p>${escapeHtml(data.structure || "")}</p></section>\n    <section class="result-section"><div class="section-label">文法與句型</div>${renderItems(data.grammar, "pattern", "explanation")}</section>\n    <section class="result-section"><div class="section-label">慣用語與搭配</div>${renderItems(data.phrases, "phrase", "meaning")}</section>\n    <section class="result-section"><div class="section-label">重點單字</div>${renderItems(data.keyWords, "word", "meaning")}</section>\n    ${data.note ? `<section class="result-section"><div class="section-label">注意</div><p>${escapeHtml(data.note)}</p></section>` : ""}\n  `;\n}\n\nfunction renderVocabulary() {\n  const query = $("#vocabSearch")?.value.toLowerCase().trim() || "";\n  const items = state.vocabulary.filter(item => !query || item.word.toLowerCase().includes(query) || item.definition.toLowerCase().includes(query));\n  const list = $("#vocabList");\n  if (!items.length) {\n    list.innerHTML = `<div class="panel-empty"><div class="panel-icon">☆</div><h3>${query ? "找不到單字" : "單字本還是空的"}</h3><p>閱讀時點一下單字，再按「加入單字本」。</p></div>`;\n    return;\n  }\n  list.innerHTML = items.map(item => `\n    <div class="vocab-card">\n      <div class="vocab-card-head"><h4>${escapeHtml(item.word)}</h4><button class="remove-btn" data-remove="${escapeHtml(item.word)}">移除</button></div>\n      <div class="phonetic">${escapeHtml(item.phonetic || "")} ${item.partOfSpeech ? `· ${escapeHtml(item.partOfSpeech)}` : ""}</div>\n      <p>${escapeHtml(item.definition || "")}</p>\n      ${item.sentence ? `<p><i>${escapeHtml(item.sentence)}</i></p>` : ""}\n    </div>`).join("");\n  $$(\'[data-remove]\').forEach(button => button.addEventListener("click", () => {\n    state.vocabulary = state.vocabulary.filter(item => item.word !== button.dataset.remove);\n    saveVocabulary();\n  }));\n}\n\nfunction exportCsv() {\n  if (!state.vocabulary.length) return toast("單字本還是空的");\n  const rows = [["word", "phonetic", "part_of_speech", "definition", "example_sentence"], ...state.vocabulary.map(i => [i.word, i.phonetic, i.partOfSpeech, i.definition, i.sentence])];\n  const csv = rows.map(row => row.map(cell => `"${String(cell || "").replaceAll(\'"\', \'""\')}"`).join(",")).join("\\n");\n  const blob = new Blob(["\\ufeff" + csv], { type: "text/csv;charset=utf-8" });\n  const link = document.createElement("a");\n  link.href = URL.createObjectURL(blob);\n  link.download = "lingoreader-vocabulary.csv";\n  link.click();\n  URL.revokeObjectURL(link.href);\n}\n\nfunction speak(text) {\n  speechSynthesis.cancel();\n  const utterance = new SpeechSynthesisUtterance(text);\n  utterance.lang = "en-US";\n  utterance.rate = .88;\n  speechSynthesis.speak(utterance);\n}\n\nfunction escapeHtml(value) {\n  return String(value ?? "").replace(/[&<>\'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\'":"&#39;",\'"\':"&quot;"}[char]));\n}\n\nasync function checkStatus() {\n  try {\n    const data = await fetch("/api/status").then(r => r.json());\n    const pill = $("#aiStatus");\n    const lockLabel = data.accessProtected ? " · 已鎖定" : "";\n    pill.textContent = (data.aiReady ? "Gemini 解析可用" : "免費朗讀／字典可用") + lockLabel;\n    pill.classList.add(data.aiReady ? "ready" : "off");\n    pill.title = data.aiReady ? "整句翻譯、文法與慣用語解析已啟用" : "朗讀與字典不需要 API Key；整句 AI 解析尚未啟用";\n  } catch {}\n}\n\n$("#loadBtn").addEventListener("click", loadArticleFromUrl);\n$("#urlInput").addEventListener("keydown", e => { if (e.key === "Enter") loadArticleFromUrl(); });\n$("#pasteModeBtn").addEventListener("click", () => $("#pastePanel").classList.toggle("hidden"));\n$("#useTextBtn").addEventListener("click", () => {\n  const text = $("#manualText").value.trim();\n  if (!text) return toast("請貼上文章文字");\n  renderArticle({ title: $("#manualTitle").value.trim() || "Pasted article", author: "", date: "", url: "pasted://article", paragraphs: text.split(/\\n\\s*\\n/).map(p => p.replace(/\\s+/g, " ").trim()).filter(Boolean) });\n});\n$("#demoBtn").addEventListener("click", () => renderArticle(demoArticle));\n$("#analyzeBtn").addEventListener("click", analyzeSentence);\n$("#speakSentenceBtn").addEventListener("click", () => speak(state.selectedSentence));\n$("#openVocabBtn").addEventListener("click", () => switchTab("vocabulary"));\n$("#vocabSearch").addEventListener("input", renderVocabulary);\n$("#exportBtn").addEventListener("click", exportCsv);\n$$(\'.tab\').forEach(tab => tab.addEventListener("click", () => switchTab(tab.dataset.tab)));\n\nupdateVocabCount();\nrenderVocabulary();\ncheckStatus();\n'

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
MAX_REMOTE_BYTES = 4_000_000

app = FastAPI(title="LingoReader", docs_url=None, redoc_url=None)


class ArticleRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class DictionaryRequest(BaseModel):
    word: str = Field(min_length=1, max_length=100)


class AnalyzeRequest(BaseModel):
    sentence: str = Field(min_length=1, max_length=1200)
    level: str = Field(default="A2", max_length=10)
    targetLanguage: str = Field(default="繁體中文", max_length=40)


class ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.og_title = ""
        self.author = ""
        self.published = ""
        self.paragraphs: list[str] = []
        self.context_paragraphs: list[str] = []
        self._in_title = False
        self._in_p = False
        self._p_parts: list[str] = []
        self._skip_depth = 0
        self._context_depth = 0

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {str(k).lower(): (v or "") for k, v in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        data = self._attrs(attrs)
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "form"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in {"article", "main"} or data.get("role", "").lower() == "main":
            self._context_depth += 1
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            prop = (data.get("property") or data.get("name") or "").lower()
            content = data.get("content", "").strip()
            if prop == "og:title" and content:
                self.og_title = content
            elif prop in {"author", "article:author", "byl"} and content and not self.author:
                self.author = content
            elif prop in {"article:published_time", "date", "datepublished", "pubdate"} and content and not self.published:
                self.published = content[:10]
        elif tag == "p":
            self._in_p = True
            self._p_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "form"}:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
        elif tag == "p" and self._in_p:
            text = " ".join("".join(self._p_parts).split())
            if len(text) >= 40 and not looks_like_junk(text):
                self.paragraphs.append(text)
                if self._context_depth:
                    self.context_paragraphs.append(text)
            self._in_p = False
            self._p_parts = []
        if tag in {"article", "main"} and self._context_depth:
            self._context_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        if self._in_p:
            self._p_parts.append(data)


def looks_like_junk(text: str) -> bool:
    lowered = text.lower()
    junk_phrases = (
        "cookie policy",
        "privacy policy",
        "terms of service",
        "all rights reserved",
        "sign up for",
        "subscribe to",
        "accept cookies",
        "advertisement",
    )
    if any(phrase in lowered for phrase in junk_phrases):
        return True
    return len(text.split()) < 7 or (text.count("|") + text.count("›") + text.count("»")) > 4


def clean_unique(paragraphs: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        text = " ".join(paragraph.split())
        key = text.lower()
        if key not in seen:
            seen.add(key)
            result.append(text)
    return result


def validate_public_url(raw_url: str) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        raise ValueError("請輸入文章網址")
    if not re.match(r"^https?://", raw_url, re.I):
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("網址格式不正確")
    if parsed.username or parsed.password:
        raise ValueError("網址不能包含帳號或密碼")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("只支援一般 HTTP／HTTPS 網址")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "0.0.0.0"} or hostname.endswith(".local"):
        raise ValueError("不支援本機或內部網路網址")

    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))}
    except socket.gaierror as exc:
        raise ValueError("找不到這個網站") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError("不支援本機或內部網路網址")
    return raw_url


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        safe_url = validate_public_url(urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, safe_url)


def fetch_article(url: str) -> dict[str, Any]:
    url = validate_public_url(url)
    opener = build_opener(SafeRedirectHandler())
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        },
    )
    with opener.open(req, timeout=22) as response:
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower() and "application/xhtml+xml" not in content_type.lower():
            raise ValueError("這個網址不是一般網頁文章")
        charset_match = re.search(r"charset=([^;]+)", content_type, re.I)
        charset = charset_match.group(1).strip() if charset_match else "utf-8"
        raw = response.read(MAX_REMOTE_BYTES + 1)
        if len(raw) > MAX_REMOTE_BYTES:
            raise ValueError("文章頁面太大，請改用貼上文章文字")
        try:
            page = raw.decode(charset, errors="replace")
        except LookupError:
            page = raw.decode("utf-8", errors="replace")

    parser = ArticleParser()
    parser.feed(page)
    paragraphs = clean_unique(parser.context_paragraphs)
    if len(paragraphs) < 2:
        paragraphs = clean_unique(parser.paragraphs)
    if not paragraphs:
        raise ValueError("抓不到正文。這個網站可能有付費牆或禁止擷取，請改用「貼上文章」功能。")

    title = parser.og_title or " ".join("".join(parser.title_parts).split()) or "Untitled article"
    title = re.split(r"\s+[|–—-]\s+", title)[0].strip() or title
    return {
        "url": url,
        "title": html.unescape(title),
        "author": html.unescape(parser.author),
        "date": parser.published,
        "paragraphs": [html.unescape(paragraph) for paragraph in paragraphs[:120]],
    }


def fetch_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> Any:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=request_headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_REMOTE_BYTES + 1)
        if len(raw) > MAX_REMOTE_BYTES:
            raise RuntimeError("外部服務回傳資料過大")
        return json.loads(raw.decode("utf-8"))


def gemini_output_text(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "translation": {"type": "string"},
        "plainMeaning": {"type": "string"},
        "structure": {"type": "string"},
        "grammar": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "explanation": {"type": "string"},
                    "example": {"type": "string"},
                },
                "required": ["pattern", "explanation", "example"],
            },
        },
        "phrases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phrase": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["phrase", "meaning"],
            },
        },
        "keyWords": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["word", "meaning"],
            },
        },
        "note": {"type": "string"},
    },
    "required": [
        "translation",
        "plainMeaning",
        "structure",
        "grammar",
        "phrases",
        "keyWords",
        "note",
    ],
}


def call_gemini(api_key: str, model: str, prompt: str) -> dict[str, Any]:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    base_payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2600,
            "responseFormat": {
                "text": {
                    "mimeType": "application/json",
                    "schema": ANALYSIS_SCHEMA,
                }
            },
        },
    }
    headers = {"x-goog-api-key": api_key}
    try:
        return fetch_json(endpoint, method="POST", payload=base_payload, headers=headers, timeout=55)
    except HTTPError as exc:
        # Older Gemini GenerateContent variants use the legacy JSON-mode field names.
        if exc.code != 400:
            raise
        legacy_payload = {
            "contents": base_payload["contents"],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2600,
                "responseMimeType": "application/json",
                "responseSchema": ANALYSIS_SCHEMA,
            },
        }
        return fetch_json(endpoint, method="POST", payload=legacy_payload, headers=headers, timeout=55)

def check_access(x_app_code: str | None) -> None:
    expected = os.getenv("APP_ACCESS_CODE", "").strip()
    if expected and not hmac.compare_digest(x_app_code or "", expected):
        raise HTTPException(
            status_code=401,
            detail={"message": "請輸入這個 App 的使用密碼", "requiresAccessCode": True},
        )


def http_error_message(exc: HTTPError) -> str:
    message = f"外部服務回傳 {exc.code}"
    try:
        body = json.loads(exc.read().decode("utf-8"))
        message = body.get("error", {}).get("message") or body.get("message") or message
    except Exception:
        pass
    return str(message)[:260]


@app.exception_handler(HTTPException)
async def http_exception_handler(_: FastAPIRequest, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail.get("message", "請求失敗"), **exc.detail})
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: FastAPIRequest, exc: Exception) -> JSONResponse:
    print("Unexpected error:", repr(exc))
    return JSONResponse(status_code=500, content={"error": "發生未預期錯誤"})


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@app.get("/static/styles.css")
def styles() -> Response:
    return Response(STYLES_CSS, media_type="text/css; charset=utf-8")


@app.get("/static/app.js")
def javascript() -> Response:
    return Response(APP_JS, media_type="application/javascript; charset=utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    return {
        "aiReady": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "aiProvider": "Gemini",
        "accessProtected": bool(os.getenv("APP_ACCESS_CODE", "").strip()),
    }


@app.post("/api/article")
def api_article(payload: ArticleRequest, x_app_code: str | None = Header(default=None)) -> dict[str, Any]:
    check_access(x_app_code)
    try:
        return fetch_article(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=http_error_message(exc)) from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise HTTPException(status_code=502, detail="連線失敗，請確認網址或稍後再試") from exc


@app.post("/api/dictionary")
def api_dictionary(payload: DictionaryRequest, x_app_code: str | None = Header(default=None)) -> dict[str, Any]:
    check_access(x_app_code)
    word = re.sub(r"[^A-Za-z'-]", "", payload.word).strip("'-")
    if not word:
        raise HTTPException(status_code=400, detail="無效的單字")
    try:
        entries = fetch_json(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=12)
    except HTTPError as exc:
        if exc.code == 404:
            return {"word": word, "notFound": True}
        raise HTTPException(status_code=502, detail=http_error_message(exc)) from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise HTTPException(status_code=502, detail="字典服務暫時無法連線") from exc

    entry = entries[0]
    phonetic = entry.get("phonetic") or ""
    audio = ""
    for item in entry.get("phonetics", []):
        phonetic = phonetic or item.get("text") or ""
        if item.get("audio"):
            audio = item["audio"]
            break
    meanings = []
    for meaning in entry.get("meanings", [])[:5]:
        definitions = []
        for definition in meaning.get("definitions", [])[:3]:
            definitions.append(
                {
                    "definition": definition.get("definition", ""),
                    "example": definition.get("example", ""),
                }
            )
        meanings.append({"partOfSpeech": meaning.get("partOfSpeech", ""), "definitions": definitions})
    return {"word": entry.get("word", word), "phonetic": phonetic, "audio": audio, "meanings": meanings}


@app.post("/api/analyze")
def api_analyze(payload: AnalyzeRequest, x_app_code: str | None = Header(default=None)) -> dict[str, Any]:
    check_access(x_app_code)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="尚未設定 GEMINI_API_KEY。朗讀、字典與單字本完全免費可用；設定 Gemini 金鑰後才會啟用整句翻譯與文法解析。",
        )

    level = payload.level if payload.level in {"A1", "A2", "B1", "B2", "C1"} else "A2"
    target_language = payload.targetLanguage if payload.targetLanguage in {"繁體中文", "日文", "英文"} else "繁體中文"
    prompt = f"""你是細心、簡單好懂的英文閱讀老師。學習者程度是 CEFR {level}，請使用{target_language}說明。
分析下列英文句子。翻譯要自然，文法說明要符合程度；只指出句中真的存在的片語、搭配與文法，不要硬湊。

英文句子：
{payload.sentence.strip()}

輸出要求：
- translation：完整自然翻譯
- plainMeaning：用白話解釋整句意思
- structure：清楚拆解主詞、動詞、受詞、子句與修飾語
- grammar：最多 4 個真正重要的文法或句型，每個含 pattern、explanation、example
- phrases：最多 4 個句中實際存在的慣用語、片語或搭配詞，每個含 phrase、meaning
- keyWords：最多 5 個值得學的單字，每個含 word、meaning
- note：容易誤解或值得注意處；沒有就回空字串
"""

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip() or "gemini-2.5-flash-lite"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        model = "gemini-2.5-flash-lite"
    try:
        response = call_gemini(api_key, model, prompt)
    except HTTPError as exc:
        message = http_error_message(exc)
        if exc.code == 429:
            message = "Gemini 免費額度暫時用完或請求太頻繁，稍後再試。朗讀與字典不受影響。"
        elif exc.code in {401, 403}:
            message = "Gemini API Key 無效、沒有權限，或此地區／專案未開放免費額度。請到 Google AI Studio 檢查金鑰。"
        raise HTTPException(status_code=502, detail=message) from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise HTTPException(status_code=502, detail="Gemini 暫時無法連線，請稍後再試") from exc

    output = gemini_output_text(response).strip()
    output = re.sub(r"^```(?:json)?\s*|\s*```$", "", output, flags=re.I | re.S)
    if not output:
        block_reason = response.get("promptFeedback", {}).get("blockReason")
        detail = f"（{block_reason}）" if block_reason else ""
        raise HTTPException(status_code=502, detail=f"Gemini 沒有回傳可用內容{detail}")
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Gemini 回傳格式不完整，請再試一次") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Gemini 回傳格式不正確，請再試一次")
    return parsed

