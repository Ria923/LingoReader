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
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from fastapi import FastAPI, Header, HTTPException, Request as FastAPIRequest
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

INDEX_HTML = '<!doctype html>\n<html lang="zh-Hant">\n<head>\n  <meta charset="utf-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1" />\n  <meta name="theme-color" content="#090909" />\n  <title>LingoReader｜Liquid Glass English Reader</title>\n  <link rel="preconnect" href="https://fonts.googleapis.com">\n  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600&family=Poppins:ital,wght@0,400;0,500;0,600;1,400&family=Source+Serif+4:ital,wght@1,400;1,500&display=swap" rel="stylesheet">\n  <link rel="stylesheet" href="/static/styles.css" />\n</head>\n<body>\n  <div class="background-stage" aria-hidden="true">\n    <video class="background-video" autoplay muted loop playsinline preload="metadata">\n      <source src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260315_073750_51473149-4350-4920-ae24-c8214286f323.mp4" type="video/mp4" />\n    </video>\n    <div class="background-shade"></div>\n    <div class="background-grain"></div>\n  </div>\n\n  <div class="app-shell">\n    <main class="workspace">\n      <section class="left-panel liquid-glass-strong">\n        <header class="topbar">\n          <div class="brand">\n            <div class="logo-mark" aria-hidden="true">\n              <svg viewBox="0 0 24 24"><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4"/></svg>\n            </div>\n            <div class="brand-copy">\n              <strong>LingoReader</strong>\n              <span>Interactive English Reading</span>\n            </div>\n          </div>\n          <button class="menu-pill liquid-glass" type="button" aria-label="閱讀模式">\n            <svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>\n            <span>Reader</span>\n          </button>\n        </header>\n\n        <section class="import-card">\n          <div class="hero-copy">\n            <span class="eyebrow">READ · CLICK · UNDERSTAND</span>\n            <h1>Turn any article into <em>your English lesson.</em></h1>\n            <p class="hero-description">貼上英文文章網址，直接點單字看繁中意思；選整句查看翻譯、文法與慣用語。</p>\n          </div>\n\n          <div class="url-row liquid-glass-strong">\n            <span class="link-icon" aria-hidden="true">\n              <svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/></svg>\n            </span>\n            <input id="urlInput" type="url" inputmode="url" autocomplete="url" placeholder="Paste an English article URL" aria-label="英文文章網址" />\n            <button id="loadBtn" class="primary-btn">生成互動文章</button>\n          </div>\n\n          <div class="import-footer">\n            <button id="pasteModeBtn" class="text-btn">網站抓不到？直接貼文章文字</button>\n            <span>部分付費牆或登入網站無法自動擷取</span>\n          </div>\n\n          <div id="pastePanel" class="paste-panel liquid-glass hidden">\n            <input id="manualTitle" placeholder="文章標題（可不填）" />\n            <textarea id="manualText" rows="7" placeholder="把英文文章貼在這裡…"></textarea>\n            <button id="useTextBtn" class="secondary-btn">使用這篇文字</button>\n          </div>\n\n          <div class="hero-bottom">\n            <div class="feature-pills" aria-label="功能">\n              <span class="liquid-glass">Instant Dictionary</span>\n              <span class="liquid-glass">Sentence Analysis</span>\n              <span class="liquid-glass">Vocabulary Archive</span>\n            </div>\n            <div class="settings-row">\n              <label>LEVEL\n                <select id="levelSelect">\n                  <option>A1</option><option selected>A2</option><option>B1</option>\n                  <option>B2</option><option>C1</option>\n                </select>\n              </label>\n              <label>TRANSLATION\n                <select id="languageSelect">\n                  <option selected>繁體中文</option><option>日文</option><option>英文</option>\n                </select>\n              </label>\n            </div>\n          </div>\n        </section>\n\n        <section class="reader-panel liquid-glass">\n          <div id="emptyState" class="empty-state">\n            <div class="empty-orbit" aria-hidden="true">\n              <span class="orbit-ring ring-one"></span>\n              <span class="orbit-ring ring-two"></span>\n              <div class="orbit-core">Aa</div>\n              <span class="orbit-word word-one">word</span>\n              <span class="orbit-word word-two">phrase</span>\n              <span class="orbit-word word-three">grammar</span>\n            </div>\n            <div class="empty-copy">\n              <span class="section-kicker">YOUR READING SPACE</span>\n              <h2>文章會出現在這裡。</h2>\n              <p>點單字查字典，點句子看翻譯、句型、慣用語與文法。</p>\n              <button id="demoBtn" class="secondary-btn demo-button">先看示範文章 <span aria-hidden="true">↗</span></button>\n            </div>\n          </div>\n\n          <article id="articleView" class="article-view hidden">\n            <div class="article-meta">\n              <span id="sourceHost"></span>\n              <span id="articleDate"></span>\n            </div>\n            <h2 id="articleTitle"></h2>\n            <p id="articleAuthor" class="author"></p>\n            <div class="reader-help">\n              <span><i class="dot word-dot"></i>點單字查繁中意思</span>\n              <span><i class="dot sentence-dot"></i>點句子進行解析</span>\n            </div>\n            <div id="articleBody" class="article-body"></div>\n          </article>\n        </section>\n\n        <footer class="bottom-quote">\n          <span>READING, REIMAGINED</span>\n          <p>“The limits of my language mean the limits of <em>my world.</em>”</p>\n          <div><i></i><b>LUDWIG WITTGENSTEIN</b><i></i></div>\n        </footer>\n      </section>\n\n      <aside class="right-rail">\n        <div class="rail-topbar">\n          <div class="status-cluster liquid-glass">\n            <span class="status-dot" aria-hidden="true"></span>\n            <span id="aiStatus" class="status-pill">檢查 AI…</span>\n          </div>\n          <button class="vocab-button liquid-glass" id="openVocabBtn">\n            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/></svg>\n            <span>單字本</span>\n            <b id="vocabCount">0</b>\n          </button>\n        </div>\n\n        <section class="ecosystem-card liquid-glass">\n          <div class="ecosystem-icon">\n            <svg viewBox="0 0 24 24"><path d="m12 3-1.7 4.3L6 9l4.3 1.7L12 15l1.7-4.3L18 9l-4.3-1.7L12 3ZM5 16l-.8 2.2L2 19l2.2.8L5 22l.8-2.2L8 19l-2.2-.8L5 16Zm14-2-1.1 2.9L15 18l2.9 1.1L19 22l1.1-2.9L23 18l-2.9-1.1L19 14Z"/></svg>\n          </div>\n          <div>\n            <span>INTERACTIVE READING</span>\n            <h2>讀懂，而不只是讀完。</h2>\n            <p>右側會隨著你的點選，即時切換句子解析、英中字典與收藏單字。</p>\n          </div>\n        </section>\n\n        <section class="study-panel liquid-glass-strong">\n          <div class="study-tabs">\n            <button class="tab active" data-tab="analysis">句子解析</button>\n            <button class="tab" data-tab="dictionary">字典</button>\n            <button class="tab" data-tab="vocabulary">單字本</button>\n          </div>\n\n          <div id="analysisTab" class="tab-content active">\n            <div id="analysisEmpty" class="panel-empty">\n              <div class="panel-icon">\n                <svg viewBox="0 0 24 24"><path d="m12 3-1.7 4.3L6 9l4.3 1.7L12 15l1.7-4.3L18 9l-4.3-1.7L12 3ZM5 16l-.8 2.2L2 19l2.2.8L5 22l.8-2.2L8 19l-2.2-.8L5 16Z"/></svg>\n              </div>\n              <span class="section-kicker">SENTENCE LAB</span>\n              <h3>選擇一個句子</h3>\n              <p>點文章中的句子，我會顯示翻譯、結構、文法與慣用語。</p>\n            </div>\n            <div id="analysisContent" class="hidden">\n              <div class="selected-card liquid-glass">\n                <div class="card-label">SELECTED SENTENCE</div>\n                <p id="selectedSentence"></p>\n                <button id="speakSentenceBtn" class="icon-btn" title="朗讀句子" aria-label="朗讀句子">\n                  <svg viewBox="0 0 24 24"><path d="m6 9-3 3 3 3V9Zm4-3-4 3v6l4 3V6Zm4.5 3.5a4 4 0 0 1 0 5m2.5-7.5a7 7 0 0 1 0 10"/></svg>\n                </button>\n              </div>\n              <button id="analyzeBtn" class="primary-btn full">翻譯並解析這句</button>\n              <div id="analysisLoading" class="loading hidden"><span></span>正在拆解句子…</div>\n              <div id="analysisResult"></div>\n            </div>\n          </div>\n\n          <div id="dictionaryTab" class="tab-content">\n            <div id="dictionaryEmpty" class="panel-empty">\n              <div class="panel-icon serif-icon">Aa</div>\n              <span class="section-kicker">DICTIONARY</span>\n              <h3>點一個英文單字</h3>\n              <p>先顯示繁體中文意思，再補充詞性、英文定義與例句。</p>\n            </div>\n            <div id="dictionaryContent" class="hidden"></div>\n          </div>\n\n          <div id="vocabularyTab" class="tab-content">\n            <div class="vocab-toolbar">\n              <input id="vocabSearch" placeholder="搜尋收藏的單字" />\n              <button id="exportBtn" class="ghost-btn small">匯出 CSV</button>\n            </div>\n            <div id="vocabList"></div>\n          </div>\n        </section>\n\n      </aside>\n    </main>\n  </div>\n\n  <div id="toast" class="toast liquid-glass-strong"></div>\n  <script src="/static/app.js"></script>\n</body>\n</html>\n'
STYLES_CSS = ':root {\n  --radius: 1rem;\n  --black: hsl(0 0% 0%);\n  --gray-5: hsl(0 0% 5%);\n  --gray-9: hsl(0 0% 9%);\n  --gray-14: hsl(0 0% 14%);\n  --gray-25: hsl(0 0% 25%);\n  --gray-45: hsl(0 0% 45%);\n  --gray-65: hsl(0 0% 65%);\n  --gray-80: hsl(0 0% 80%);\n  --gray-92: hsl(0 0% 92%);\n  --white: hsl(0 0% 100%);\n  --text: hsl(0 0% 100%);\n  --text-80: hsl(0 0% 100% / .8);\n  --text-65: hsl(0 0% 100% / .65);\n  --text-50: hsl(0 0% 100% / .5);\n  --text-35: hsl(0 0% 100% / .35);\n  --glass-fill: rgba(255, 255, 255, .01);\n  --glass-soft: rgba(255, 255, 255, .055);\n  --glass-hover: rgba(255, 255, 255, .11);\n  --shadow: 0 24px 80px rgba(0, 0, 0, .28);\n}\n\n* { box-sizing: border-box; }\nhtml { scroll-behavior: smooth; }\nbody {\n  margin: 0;\n  min-width: 320px;\n  min-height: 100vh;\n  color: var(--text);\n  background: var(--gray-5);\n  font-family: "Poppins", "Noto Sans TC", sans-serif;\n  font-weight: 400;\n  -webkit-font-smoothing: antialiased;\n  text-rendering: optimizeLegibility;\n}\n\nbutton, input, textarea, select { font: inherit; }\nbutton { cursor: pointer; }\nbutton, input, textarea, select { border: 0; }\nbutton:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {\n  outline: 2px solid rgba(255,255,255,.75);\n  outline-offset: 3px;\n}\nsvg {\n  width: 1em;\n  height: 1em;\n  fill: none;\n  stroke: currentColor;\n  stroke-width: 1.7;\n  stroke-linecap: round;\n  stroke-linejoin: round;\n}\na { color: inherit; }\n.hidden { display: none !important; }\n\n.background-stage {\n  position: fixed;\n  inset: 0;\n  z-index: 0;\n  overflow: hidden;\n  background:\n    radial-gradient(circle at 24% 20%, hsl(0 0% 35%) 0, transparent 36%),\n    linear-gradient(145deg, hsl(0 0% 16%), hsl(0 0% 3%));\n}\n.background-video {\n  width: 100%;\n  height: 100%;\n  object-fit: cover;\n  filter: grayscale(1) contrast(1.08) brightness(.58);\n  transform: scale(1.015);\n}\n.background-shade {\n  position: absolute;\n  inset: 0;\n  background:\n    linear-gradient(90deg, rgba(0,0,0,.28) 0%, rgba(0,0,0,.08) 48%, rgba(0,0,0,.26) 100%),\n    linear-gradient(180deg, rgba(0,0,0,.08), rgba(0,0,0,.38));\n}\n.background-grain {\n  position: absolute;\n  inset: 0;\n  opacity: .08;\n  pointer-events: none;\n  background-image: url("data:image/svg+xml,%3Csvg viewBox=\'0 0 160 160\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'.92\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\' opacity=\'.9\'/%3E%3C/svg%3E");\n  mix-blend-mode: soft-light;\n}\n\n.liquid-glass,\n.liquid-glass-strong {\n  position: relative;\n  overflow: hidden;\n  isolation: isolate;\n  background: var(--glass-fill);\n  background-blend-mode: luminosity;\n}\n.liquid-glass {\n  -webkit-backdrop-filter: blur(4px);\n  backdrop-filter: blur(4px);\n  box-shadow: inset 0 1px 1px rgba(255,255,255,.1);\n}\n.liquid-glass-strong {\n  -webkit-backdrop-filter: blur(50px) saturate(.7);\n  backdrop-filter: blur(50px) saturate(.7);\n  box-shadow: 4px 4px 4px rgba(0,0,0,.05), inset 0 1px 1px rgba(255,255,255,.15), var(--shadow);\n}\n.liquid-glass::before,\n.liquid-glass-strong::before {\n  content: "";\n  position: absolute;\n  inset: 0;\n  border-radius: inherit;\n  padding: 1.4px;\n  pointer-events: none;\n  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);\n  -webkit-mask-composite: xor;\n  mask-composite: exclude;\n  z-index: 4;\n}\n.liquid-glass::before {\n  background: linear-gradient(180deg,\n    rgba(255,255,255,.45) 0%,\n    rgba(255,255,255,.15) 20%,\n    transparent 40%,\n    transparent 60%,\n    rgba(255,255,255,.15) 80%,\n    rgba(255,255,255,.45) 100%);\n}\n.liquid-glass-strong::before {\n  background: linear-gradient(180deg,\n    rgba(255,255,255,.5) 0%,\n    rgba(255,255,255,.2) 20%,\n    transparent 40%,\n    transparent 60%,\n    rgba(255,255,255,.2) 80%,\n    rgba(255,255,255,.5) 100%);\n}\n\n.app-shell {\n  position: relative;\n  z-index: 10;\n  width: 100%;\n  max-width: 1800px;\n  margin: 0 auto;\n  padding: 24px;\n}\n.workspace {\n  display: grid;\n  grid-template-columns: minmax(0, 52fr) minmax(390px, 48fr);\n  gap: 18px;\n  align-items: start;\n  min-height: calc(100vh - 48px);\n}\n.left-panel {\n  min-height: calc(100vh - 48px);\n  border-radius: 30px;\n  padding: clamp(18px, 2vw, 30px);\n  display: flex;\n  flex-direction: column;\n  background: rgba(0,0,0,.14);\n}\n.right-rail {\n  position: sticky;\n  top: 24px;\n  display: flex;\n  flex-direction: column;\n  gap: 14px;\n  min-width: 0;\n}\n\n.topbar,\n.rail-topbar,\n.brand,\n.menu-pill,\n.status-cluster,\n.vocab-button,\n.hero-bottom,\n.settings-row,\n.feature-pills,\n.import-footer,\n.reader-help,\n.article-meta,\n.dict-head,\n.vocab-card-head,\n.bottom-quote > div {\n  display: flex;\n  align-items: center;\n}\n.topbar { justify-content: space-between; gap: 16px; }\n.brand { gap: 11px; min-width: 0; }\n.logo-mark {\n  width: 38px;\n  height: 38px;\n  border-radius: 50%;\n  display: grid;\n  place-items: center;\n  background: rgba(255,255,255,.12);\n  color: var(--text-80);\n  box-shadow: inset 0 1px 1px rgba(255,255,255,.25);\n}\n.logo-mark svg { width: 19px; height: 19px; }\n.brand-copy strong {\n  display: block;\n  font-size: 20px;\n  line-height: 1;\n  font-weight: 600;\n  letter-spacing: -.055em;\n}\n.brand-copy span {\n  display: block;\n  margin-top: 5px;\n  color: var(--text-50);\n  font-size: 9px;\n  letter-spacing: .14em;\n  text-transform: uppercase;\n}\n.menu-pill,\n.status-cluster,\n.vocab-button,\n.feature-pills > span {\n  border-radius: 999px;\n}\n.menu-pill,\n.vocab-button {\n  color: var(--text-80);\n  background: rgba(255,255,255,.03);\n  transition: transform .22s ease, background .22s ease;\n}\n.menu-pill:hover,\n.vocab-button:hover,\n.primary-btn:hover,\n.secondary-btn:hover,\n.ghost-btn:hover,\n.icon-btn:hover,\n.feature-card:hover {\n  transform: scale(1.035);\n}\n.menu-pill:active,\n.vocab-button:active,\n.primary-btn:active,\n.secondary-btn:active,\n.ghost-btn:active,\n.icon-btn:active,\n.feature-card:active { transform: scale(.975); }\n.menu-pill { gap: 8px; padding: 10px 14px; }\n.menu-pill svg { width: 17px; height: 17px; }\n.menu-pill span { font-size: 12px; }\n\n.import-card {\n  padding: clamp(54px, 8vh, 112px) clamp(0px, 2vw, 22px) 34px;\n}\n.hero-copy { max-width: 800px; }\n.eyebrow,\n.section-kicker,\n.card-label,\n.section-label,\n.ecosystem-card > div > span,\n.feature-card > span,\n.bottom-quote > span {\n  color: var(--text-50);\n  font-size: 10px;\n  font-weight: 500;\n  letter-spacing: .22em;\n  text-transform: uppercase;\n}\nh1, h2, h3, h4, p { overflow-wrap: anywhere; }\nh1 {\n  max-width: 860px;\n  margin: 12px 0 18px;\n  font-size: clamp(44px, 5.7vw, 82px);\n  line-height: .99;\n  font-weight: 500;\n  letter-spacing: -.065em;\n}\nh1 em,\n.bottom-quote em {\n  color: var(--text-80);\n  font-family: "Source Serif 4", serif;\n  font-weight: 400;\n}\n.hero-description {\n  max-width: 680px;\n  margin: 0;\n  color: var(--text-65);\n  font-size: 14px;\n  line-height: 1.75;\n}\n.url-row {\n  display: grid;\n  grid-template-columns: 38px minmax(0, 1fr) auto;\n  gap: 7px;\n  align-items: center;\n  max-width: 900px;\n  margin-top: 30px;\n  padding: 8px;\n  border-radius: 999px;\n  background: rgba(0,0,0,.08);\n}\n.link-icon {\n  width: 34px;\n  height: 34px;\n  display: grid;\n  place-items: center;\n  border-radius: 50%;\n  color: var(--text-65);\n  background: rgba(255,255,255,.09);\n}\n.link-icon svg { width: 17px; height: 17px; }\n.url-row input,\n.paste-panel input,\n.paste-panel textarea,\n.vocab-toolbar input,\nselect {\n  width: 100%;\n  color: var(--text);\n  background: rgba(0,0,0,.16);\n  box-shadow: inset 0 1px 1px rgba(255,255,255,.11);\n}\n.url-row input {\n  min-width: 0;\n  padding: 13px 9px;\n  background: transparent;\n  box-shadow: none;\n  outline: 0;\n}\ninput::placeholder,\ntextarea::placeholder { color: var(--text-35); }\n.primary-btn,\n.secondary-btn,\n.ghost-btn,\n.icon-btn,\n.text-btn,\n.remove-btn,\n.save-btn {\n  color: var(--text);\n  transition: transform .22s ease, background .22s ease, opacity .22s ease;\n}\n.primary-btn {\n  min-height: 44px;\n  padding: 12px 18px;\n  border-radius: 999px;\n  color: var(--gray-9);\n  background: rgba(255,255,255,.92);\n  box-shadow: 0 8px 28px rgba(0,0,0,.18), inset 0 1px 1px rgba(255,255,255,.7);\n  font-weight: 600;\n  white-space: nowrap;\n}\n.primary-btn:disabled { opacity: .5; cursor: wait; transform: none; }\n.primary-btn.full { width: 100%; margin-top: 10px; }\n.import-footer {\n  justify-content: space-between;\n  gap: 18px;\n  max-width: 900px;\n  padding: 12px 5px 0;\n  color: var(--text-35);\n  font-size: 10px;\n}\n.text-btn {\n  padding: 0;\n  color: var(--text-65);\n  background: transparent;\n  text-decoration: underline;\n  text-decoration-color: rgba(255,255,255,.25);\n  text-underline-offset: 4px;\n}\n.text-btn:hover { color: var(--text); }\n.paste-panel {\n  max-width: 900px;\n  margin-top: 17px;\n  padding: 15px;\n  border-radius: 24px;\n  background: rgba(0,0,0,.12);\n}\n.paste-panel input,\n.paste-panel textarea,\n.vocab-toolbar input {\n  padding: 12px 14px;\n  border-radius: 14px;\n  outline: 0;\n}\n.paste-panel textarea { display: block; resize: vertical; margin: 9px 0; min-height: 150px; }\n.secondary-btn,\n.ghost-btn,\n.save-btn {\n  padding: 11px 15px;\n  border-radius: 999px;\n  background: rgba(255,255,255,.08);\n  box-shadow: inset 0 1px 1px rgba(255,255,255,.16);\n  font-weight: 500;\n}\n.hero-bottom {\n  justify-content: space-between;\n  gap: 18px;\n  margin-top: 28px;\n}\n.feature-pills { gap: 7px; flex-wrap: wrap; }\n.feature-pills > span {\n  padding: 9px 14px;\n  color: var(--text-80);\n  font-size: 11px;\n  letter-spacing: .02em;\n  background: rgba(255,255,255,.05);\n}\n.settings-row { gap: 9px; }\n.settings-row label {\n  min-width: 96px;\n  color: var(--text-65);\n  font-size: 10px;\n  letter-spacing: .14em;\n}\nselect {\n  appearance: none;\n  margin-top: 5px;\n  padding: 9px 30px 9px 11px;\n  border-radius: 999px;\n  color-scheme: dark;\n  background-image:\n    linear-gradient(45deg, transparent 50%, rgba(255,255,255,.65) 50%),\n    linear-gradient(135deg, rgba(255,255,255,.65) 50%, transparent 50%);\n  background-position: calc(100% - 15px) 50%, calc(100% - 11px) 50%;\n  background-size: 4px 4px, 4px 4px;\n  background-repeat: no-repeat;\n}\n\n.reader-panel {\n  min-height: 560px;\n  margin-top: 6px;\n  padding: clamp(24px, 4vw, 58px);\n  border-radius: 28px;\n  background: rgba(0,0,0,.12);\n}\n.empty-state {\n  min-height: 450px;\n  display: grid;\n  grid-template-columns: minmax(210px, .8fr) minmax(260px, 1.2fr);\n  gap: clamp(20px, 5vw, 70px);\n  align-items: center;\n}\n.empty-orbit {\n  width: min(290px, 80vw);\n  aspect-ratio: 1;\n  position: relative;\n  display: grid;\n  place-items: center;\n  margin: auto;\n}\n.orbit-ring {\n  position: absolute;\n  inset: 15%;\n  border-radius: 50%;\n  box-shadow: inset 0 0 0 1px rgba(255,255,255,.18);\n}\n.ring-one { transform: rotate(22deg) scaleX(.68); }\n.ring-two { transform: rotate(-45deg) scaleX(.74); }\n.orbit-core {\n  width: 102px;\n  height: 102px;\n  display: grid;\n  place-items: center;\n  border-radius: 50%;\n  color: var(--text);\n  background: rgba(255,255,255,.12);\n  box-shadow: inset 0 1px 2px rgba(255,255,255,.22), 0 18px 42px rgba(0,0,0,.2);\n  font-family: "Source Serif 4", serif;\n  font-size: 35px;\n  font-style: italic;\n}\n.orbit-word {\n  position: absolute;\n  padding: 7px 12px;\n  border-radius: 999px;\n  color: var(--text-65);\n  background: rgba(255,255,255,.07);\n  box-shadow: inset 0 1px 1px rgba(255,255,255,.18);\n  font-size: 10px;\n}\n.word-one { top: 15%; left: 4%; transform: rotate(-8deg); }\n.word-two { top: 28%; right: 2%; transform: rotate(7deg); }\n.word-three { bottom: 17%; left: 12%; transform: rotate(4deg); }\n.empty-copy h2 {\n  margin: 10px 0 10px;\n  font-size: clamp(28px, 3vw, 46px);\n  line-height: 1.08;\n  font-weight: 500;\n  letter-spacing: -.055em;\n}\n.empty-copy p {\n  max-width: 520px;\n  margin: 0 0 22px;\n  color: var(--text-50);\n  font-size: 13px;\n  line-height: 1.75;\n}\n.demo-button { display: inline-flex; gap: 12px; align-items: center; }\n\n.article-meta { gap: 14px; color: var(--text-50); font-size: 9px; letter-spacing: .17em; text-transform: uppercase; }\n.article-view h2 {\n  max-width: 1000px;\n  margin: 13px 0 10px;\n  font-size: clamp(38px, 5vw, 70px);\n  line-height: 1.02;\n  letter-spacing: -.06em;\n  font-weight: 500;\n}\n.author { margin: 0 0 26px; color: var(--text-50); font-size: 12px; }\n.reader-help {\n  gap: 19px;\n  padding: 13px 0;\n  color: var(--text-50);\n  box-shadow: inset 0 1px rgba(255,255,255,.09), inset 0 -1px rgba(255,255,255,.09);\n  font-size: 10px;\n}\n.dot { width: 6px; height: 6px; display: inline-block; margin-right: 6px; border-radius: 50%; background: rgba(255,255,255,.55); }\n.sentence-dot { background: rgba(255,255,255,.9); }\n.article-body {\n  max-width: 860px;\n  padding-top: 27px;\n  color: var(--text-80);\n  font-family: "Source Serif 4", Georgia, serif;\n  font-size: clamp(19px, 1.55vw, 23px);\n  line-height: 1.92;\n}\n.article-body p { margin: 0 0 1.55em; }\n.sentence,\n.word { border-radius: 5px; transition: background .15s ease, box-shadow .15s ease, color .15s ease; }\n.sentence { cursor: pointer; }\n.sentence:hover { background: rgba(255,255,255,.075); }\n.sentence.selected { background: rgba(255,255,255,.14); box-shadow: 0 0 0 3px rgba(255,255,255,.07); }\n.word { cursor: pointer; }\n.word:hover { color: var(--white); background: rgba(255,255,255,.18); }\n.word.saved { color: var(--white); background: rgba(255,255,255,.2); box-shadow: inset 0 -1px rgba(255,255,255,.75); }\n\n.bottom-quote {\n  padding: 46px 12px 14px;\n  text-align: center;\n}\n.bottom-quote p {\n  margin: 12px auto 14px;\n  color: var(--text-65);\n  font-size: clamp(15px, 1.4vw, 20px);\n}\n.bottom-quote > div { justify-content: center; gap: 10px; }\n.bottom-quote i { width: 36px; height: 1px; background: rgba(255,255,255,.2); }\n.bottom-quote b { color: var(--text-35); font-size: 8px; font-weight: 500; letter-spacing: .18em; }\n\n.rail-topbar { justify-content: flex-end; gap: 8px; }\n.status-cluster { gap: 8px; min-height: 42px; padding: 9px 13px; background: rgba(255,255,255,.025); }\n.status-dot { width: 6px; height: 6px; border-radius: 50%; background: rgba(255,255,255,.65); box-shadow: 0 0 10px rgba(255,255,255,.3); }\n.status-pill { color: var(--text-65); font-size: 10px; white-space: nowrap; }\n.status-pill.ready { color: var(--text); }\n.status-pill.off { color: var(--text-50); }\n.vocab-button { min-height: 42px; padding: 9px 13px; gap: 7px; }\n.vocab-button svg { width: 16px; height: 16px; }\n.vocab-button span { font-size: 11px; }\n.vocab-button b {\n  min-width: 20px;\n  height: 20px;\n  display: grid;\n  place-items: center;\n  border-radius: 50%;\n  color: var(--gray-9);\n  background: rgba(255,255,255,.88);\n  font-size: 9px;\n}\n.ecosystem-card {\n  display: grid;\n  grid-template-columns: auto 1fr;\n  gap: 14px;\n  align-items: start;\n  padding: 17px;\n  border-radius: 24px;\n  background: rgba(255,255,255,.025);\n}\n.ecosystem-icon,\n.feature-icon,\n.panel-icon {\n  display: grid;\n  place-items: center;\n  border-radius: 50%;\n  color: var(--text-80);\n  background: rgba(255,255,255,.1);\n  box-shadow: inset 0 1px 1px rgba(255,255,255,.2);\n}\n.ecosystem-icon { width: 38px; height: 38px; }\n.ecosystem-icon svg { width: 18px; height: 18px; }\n.ecosystem-card h2 { margin: 6px 0 5px; font-size: 19px; font-weight: 500; letter-spacing: -.04em; }\n.ecosystem-card p { margin: 0; color: var(--text-50); font-size: 10px; line-height: 1.65; }\n\n.study-panel {\n  border-radius: 34px;\n  background: rgba(0,0,0,.16);\n  min-height: 610px;\n}\n.study-tabs {\n  display: grid;\n  grid-template-columns: repeat(3, 1fr);\n  padding: 9px;\n  gap: 5px;\n  box-shadow: inset 0 -1px rgba(255,255,255,.08);\n}\n.tab {\n  position: relative;\n  padding: 14px 8px;\n  border-radius: 999px;\n  color: var(--text-50);\n  background: transparent;\n  font-size: 11px;\n  font-weight: 500;\n  transition: color .2s ease, background .2s ease, transform .2s ease;\n}\n.tab:hover { color: var(--text-80); }\n.tab.active { color: var(--text); background: rgba(255,255,255,.09); box-shadow: inset 0 1px 1px rgba(255,255,255,.15); }\n.tab-content {\n  display: none;\n  max-height: calc(100vh - 235px);\n  min-height: 520px;\n  overflow: auto;\n  padding: 24px;\n  scrollbar-width: thin;\n  scrollbar-color: rgba(255,255,255,.2) transparent;\n}\n.tab-content.active { display: block; }\n.tab-content::-webkit-scrollbar { width: 6px; }\n.tab-content::-webkit-scrollbar-thumb { background: rgba(255,255,255,.2); border-radius: 99px; }\n.panel-empty {\n  min-height: 470px;\n  display: flex;\n  flex-direction: column;\n  align-items: center;\n  justify-content: center;\n  text-align: center;\n}\n.panel-icon { width: 56px; height: 56px; margin-bottom: 16px; }\n.panel-icon svg { width: 23px; height: 23px; }\n.serif-icon { font-family: "Source Serif 4", serif; font-size: 22px; font-style: italic; }\n.panel-empty h3 { margin: 8px 0; font-size: 22px; font-weight: 500; letter-spacing: -.04em; }\n.panel-empty p { max-width: 290px; margin: 0; color: var(--text-50); font-size: 11px; line-height: 1.7; }\n.selected-card {\n  position: relative;\n  padding: 17px 48px 17px 17px;\n  border-radius: 20px;\n  background: rgba(255,255,255,.035);\n}\n.selected-card p {\n  margin: 7px 0 0;\n  color: var(--text-80);\n  font-family: "Source Serif 4", serif;\n  font-size: 16px;\n  line-height: 1.6;\n}\n.icon-btn {\n  width: 34px;\n  height: 34px;\n  display: grid;\n  place-items: center;\n  border-radius: 50%;\n  background: rgba(255,255,255,.1);\n  box-shadow: inset 0 1px 1px rgba(255,255,255,.18);\n}\n.selected-card .icon-btn { position: absolute; top: 12px; right: 12px; }\n.icon-btn svg { width: 17px; height: 17px; }\n.loading { padding: 18px 4px; color: var(--text-50); font-size: 11px; }\n.loading span {\n  width: 11px;\n  height: 11px;\n  display: inline-block;\n  margin-right: 8px;\n  border-radius: 50%;\n  box-shadow: inset 0 0 0 2px rgba(255,255,255,.18);\n  border-top: 2px solid rgba(255,255,255,.85);\n  animation: spin .7s linear infinite;\n}\n@keyframes spin { to { transform: rotate(360deg); } }\n.result-section,\n.meaning-block,\n.vocab-card {\n  padding: 18px 2px;\n  box-shadow: inset 0 -1px rgba(255,255,255,.09);\n}\n.result-section h4 { margin: 6px 0 9px; font-size: 13px; font-weight: 500; }\n.result-section p { margin: 5px 0 0; color: var(--text-65); font-size: 12px; line-height: 1.7; }\n.translation { color: var(--text) !important; font-size: 17px !important; font-weight: 500; }\n.analysis-list { display: grid; gap: 9px; margin-top: 10px; }\n.analysis-item { padding: 11px 12px; border-radius: 15px; background: rgba(255,255,255,.045); }\n.analysis-item strong { display: block; margin-bottom: 4px; color: var(--text-80); font-size: 11px; }\n.analysis-item span { color: var(--text-50); font-size: 11px; line-height: 1.65; }\n\n.dict-head { justify-content: space-between; align-items: flex-start; gap: 12px; padding-bottom: 18px; box-shadow: inset 0 -1px rgba(255,255,255,.1); }\n.dict-head > div:last-child { display: flex; align-items: center; gap: 7px; }\n.dict-word { margin: 0; color: var(--text); font-family: "Source Serif 4", serif; font-size: 39px; font-style: italic; font-weight: 500; letter-spacing: -.04em; }\n.phonetic { margin-top: 4px; color: var(--text-50); font-size: 11px; }\n.save-btn.saved { color: var(--gray-9); background: rgba(255,255,255,.9); }\n.chinese-summary {\n  margin: 18px 0 2px;\n  padding: 16px;\n  border-radius: 20px;\n  background: rgba(255,255,255,.08);\n  box-shadow: inset 0 1px 1px rgba(255,255,255,.14);\n}\n.summary-label { margin-bottom: 10px; color: var(--text-50); font-size: 9px; letter-spacing: .14em; text-transform: uppercase; }\n.summary-words { display: flex; flex-wrap: wrap; gap: 7px; }\n.summary-words span { padding: 6px 10px; border-radius: 999px; color: var(--text); background: rgba(255,255,255,.1); font-size: 12px; font-weight: 500; }\n.muted-summary p { margin: 0; color: var(--text-50); font-size: 11px; line-height: 1.6; }\n.part { display: flex; align-items: baseline; gap: 8px; }\n.part strong { color: var(--text-80); font-size: 11px; font-weight: 500; }\n.part span { color: var(--text-35); font-size: 10px; font-style: italic; }\n.definition { margin: 11px 0; font-size: 12px; line-height: 1.6; }\n.zh-definition { margin-bottom: 5px; color: var(--text); font-weight: 500; }\n.en-definition { color: var(--text-65); }\n.example { margin-top: 6px; color: var(--text-50); font-family: "Source Serif 4", serif; font-size: 11px; font-style: italic; }\n.example span { margin-right: 6px; color: var(--text-35); font-family: "Poppins", sans-serif; font-size: 8px; font-style: normal; letter-spacing: .12em; }\n.dict-source { margin-top: 18px; color: var(--text-35); font-size: 9px; line-height: 1.6; }\n.dict-source a { color: var(--text-65); }\n\n.vocab-toolbar { display: grid; grid-template-columns: 1fr auto; gap: 8px; }\n.vocab-toolbar input { margin: 0; }\n.ghost-btn.small { white-space: nowrap; padding: 9px 12px; }\n.vocab-card h4 { margin: 0; color: var(--text); font-family: "Source Serif 4", serif; font-size: 21px; font-style: italic; font-weight: 500; }\n.vocab-card p { margin: 6px 0 0; color: var(--text-50); font-size: 11px; line-height: 1.55; }\n.vocab-card-head { justify-content: space-between; gap: 12px; }\n.remove-btn { padding: 5px; color: var(--text-35); background: transparent; font-size: 10px; }\n.remove-btn:hover { color: var(--text); }\n.vocab-english { color: var(--text-35) !important; }\n\n.feature-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }\n.feature-card {\n  min-height: 128px;\n  padding: 16px;\n  border-radius: 24px;\n  background: rgba(255,255,255,.025);\n  transition: transform .22s ease, background .22s ease;\n}\n.feature-card:hover { background: rgba(255,255,255,.06); }\n.feature-icon { width: 34px; height: 34px; margin-bottom: 18px; }\n.feature-icon svg { width: 16px; height: 16px; }\n.feature-card h3 { margin: 5px 0 0; font-size: 14px; font-weight: 500; letter-spacing: -.025em; }\n\n.toast {\n  position: fixed;\n  left: 50%;\n  bottom: 25px;\n  z-index: 50;\n  max-width: min(480px, calc(100vw - 30px));\n  padding: 12px 16px;\n  border-radius: 999px;\n  color: var(--text);\n  background: rgba(0,0,0,.42);\n  opacity: 0;\n  pointer-events: none;\n  transform: translate(-50%, 20px);\n  transition: opacity .2s ease, transform .2s ease;\n  font-size: 11px;\n  text-align: center;\n}\n.toast.show { opacity: 1; transform: translate(-50%, 0); }\n\nbody.article-ready .import-card { padding-top: 45px; padding-bottom: 24px; }\nbody.article-ready h1 { font-size: clamp(36px, 4.2vw, 64px); }\n\n@media (max-width: 1180px) {\n  .workspace { grid-template-columns: minmax(0, 1.1fr) minmax(350px, .9fr); }\n  .app-shell { padding: 14px; }\n  .left-panel { min-height: calc(100vh - 28px); }\n  .hero-bottom { align-items: flex-end; flex-direction: column; }\n  .settings-row { align-self: flex-start; }\n}\n\n@media (max-width: 980px) {\n  .workspace { grid-template-columns: 1fr; }\n  .right-rail { position: static; }\n  .tab-content { max-height: none; min-height: 470px; }\n  .study-panel { min-height: 560px; }\n  .ecosystem-card { display: none; }\n  .feature-grid { margin-bottom: 6px; }\n}\n\n@media (max-width: 700px) {\n  .app-shell { padding: 8px; }\n  .left-panel { min-height: calc(100vh - 16px); padding: 16px; border-radius: 24px; }\n  .brand-copy span, .menu-pill span { display: none; }\n  .menu-pill { width: 40px; height: 40px; padding: 0; justify-content: center; }\n  .import-card { padding: 58px 0 28px; }\n  h1 { font-size: clamp(42px, 15vw, 66px); }\n  .hero-description { font-size: 12px; }\n  .url-row { grid-template-columns: 34px minmax(0, 1fr); border-radius: 22px; }\n  .url-row .primary-btn { grid-column: 1 / -1; width: 100%; }\n  .import-footer { align-items: flex-start; flex-direction: column; }\n  .hero-bottom { align-items: flex-start; }\n  .feature-pills { width: 100%; }\n  .feature-pills > span { flex: 1; text-align: center; white-space: nowrap; }\n  .settings-row { width: 100%; }\n  .settings-row label { flex: 1; }\n  .reader-panel { padding: 24px 18px; border-radius: 24px; }\n  .empty-state { grid-template-columns: 1fr; min-height: 580px; text-align: center; }\n  .empty-copy p { margin-inline: auto; }\n  .article-view h2 { font-size: 42px; }\n  .article-body { font-size: 19px; }\n  .rail-topbar { justify-content: space-between; }\n  .status-cluster { min-width: 0; }\n  .status-pill { overflow: hidden; text-overflow: ellipsis; }\n  .study-panel { border-radius: 26px; }\n  .tab-content { padding: 18px; }\n  .dict-head { flex-direction: column; }\n  .feature-grid { grid-template-columns: 1fr 1fr; }\n}\n\n@media (max-width: 460px) {\n  .feature-pills > span:nth-child(3) { display: none; }\n  .settings-row { flex-direction: column; }\n  .settings-row label { width: 100%; }\n  .reader-help { align-items: flex-start; flex-direction: column; gap: 6px; }\n  .study-tabs { gap: 2px; padding: 7px; }\n  .tab { padding-inline: 5px; font-size: 10px; }\n  .feature-grid { grid-template-columns: 1fr; }\n  .feature-card { min-height: 105px; }\n  .vocab-toolbar { grid-template-columns: 1fr; }\n}\n\n@media (prefers-reduced-motion: reduce) {\n  html { scroll-behavior: auto; }\n  .background-video { display: none; }\n  *, *::before, *::after { animation-duration: .001ms !important; animation-iteration-count: 1 !important; transition-duration: .001ms !important; }\n}\n\n@supports not ((backdrop-filter: blur(4px)) or (-webkit-backdrop-filter: blur(4px))) {\n  .liquid-glass { background: rgba(20,20,20,.74); }\n  .liquid-glass-strong { background: rgba(12,12,12,.88); }\n}\n\n/* ---- graded vocabulary (CEFR) ---- */\n.word.above-level {\n  border-bottom: 1px dashed rgba(255,255,255,.45);\n}\n.word.above-level:hover { border-bottom-color: transparent; }\n.lvl-badge {\n  display: inline-block;\n  margin-left: 7px;\n  padding: 1px 7px;\n  border-radius: 999px;\n  background: rgba(255,255,255,.12);\n  box-shadow: inset 0 1px 1px rgba(255,255,255,.16);\n  color: var(--text-80);\n  font-size: 9px;\n  font-weight: 500;\n  letter-spacing: .06em;\n  vertical-align: middle;\n}\n.lvl-badge[data-lvl="A1"], .lvl-badge[data-lvl="A2"] { background: rgba(255,255,255,.06); color: var(--text-65); }\n.lvl-badge[data-lvl="C1"], .lvl-badge[data-lvl="C2"] { background: rgba(255,255,255,.2); color: var(--white); }\n.vocab-toolbar { grid-template-columns: 1fr auto auto; }\n.vocab-toolbar select {\n  margin: 0;\n  padding: 9px 26px 9px 11px;\n  border-radius: 14px;\n  font-size: 12px;\n}\n.difficulty-tag {\n  margin-left: auto;\n  color: var(--text-65);\n  font-size: 9px;\n  letter-spacing: .1em;\n  text-transform: none;\n}\n.difficulty-tag b { color: var(--text); font-weight: 600; }\n.reader-legend {\n  margin-left: 14px;\n  color: var(--text-35);\n  font-size: 9px;\n  letter-spacing: .02em;\n}\n.reader-legend i {\n  display: inline-block;\n  width: 14px;\n  border-bottom: 1px dashed rgba(255,255,255,.55);\n  margin-right: 5px;\n  vertical-align: middle;\n}\n@media (max-width: 460px) {\n  .vocab-toolbar { grid-template-columns: 1fr; }\n}\n'
APP_JS = 'const $ = (selector) => document.querySelector(selector);\nconst $$ = (selector) => [...document.querySelectorAll(selector)];\n\nconst state = {\n  article: null,\n  selectedSentence: "",\n  selectedElement: null,\n  dictionaryData: null,\n  vocabulary: JSON.parse(localStorage.getItem("lingoreader-vocabulary") || "[]"),\n};\n\nconst SYNC = { enabled: false };\n\nlet CEFR = {};\nconst CEFR_ORDER = { A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6 };\nfunction wordLevel(w) { return CEFR[String(w || "").toLowerCase()] || ""; }\nfunction readerLevelIdx() { return CEFR_ORDER[($("#levelSelect")?.value) || "A2"] || 2; }\nconst CEFR_SRC = "https://raw.githubusercontent.com/tyypgzl/Oxford-5000-words/main/full-word.json";\nfunction cacheCefr() { try { localStorage.setItem("lingoreader-cefr", JSON.stringify(CEFR)); } catch {} }\nasync function loadCefr() {\n  try { const c = localStorage.getItem("lingoreader-cefr"); if (c) { CEFR = JSON.parse(c) || {}; if (Object.keys(CEFR).length) return; } } catch {}\n  // fast path: backend proxy (used only if it returns a populated map)\n  try {\n    const r = await fetch("/api/cefr");\n    if (r.ok) { const d = await r.json(); if (d.words && Object.keys(d.words).length) { CEFR = d.words; cacheCefr(); return; } }\n  } catch {}\n  // fallback: fetch the Oxford word list directly and build the map client-side\n  try {\n    const arr = await fetch(CEFR_SRC, { cache: "force-cache" }).then(r => r.json());\n    const map = {};\n    for (const e of arr) {\n      const v = (e && e.value) || {};\n      const w = String(v.word || "").trim().toLowerCase();\n      const l = String(v.level || "").trim().toUpperCase();\n      if (w && CEFR_ORDER[l] && /^[a-z][a-z\' -]*$/.test(w)) {\n        if (!(w in map) || CEFR_ORDER[l] < CEFR_ORDER[map[w]]) map[w] = l;\n      }\n    }\n    if (Object.keys(map).length) { CEFR = map; cacheCefr(); }\n  } catch {}\n}\nfunction markAboveLevel() {\n  const idx = readerLevelIdx();\n  $$(".word").forEach(n => {\n    const l = n.dataset.level || "";\n    n.classList.toggle("above-level", !!l && (CEFR_ORDER[l] || 0) > idx);\n  });\n}\nfunction ensureLegend() {\n  const help = document.querySelector(".reader-help");\n  if (help && !$("#levelLegend")) {\n    const span = document.createElement("span");\n    span.id = "levelLegend";\n    span.className = "reader-legend";\n    span.innerHTML = \'<i></i>高於你程度的字\';\n    help.appendChild(span);\n  }\n}\nfunction showDifficulty(article) {\n  const words = (article.paragraphs || []).join(" ").toLowerCase().match(/[a-z][a-z\'-]*/g) || [];\n  const counts = { A1:0, A2:0, B1:0, B2:0, C1:0, C2:0 };\n  let graded = 0, above = 0;\n  const idx = readerLevelIdx();\n  for (const w of words) {\n    const l = wordLevel(w);\n    if (!l) continue;\n    counts[l]++; graded++;\n    if ((CEFR_ORDER[l] || 0) > idx) above++;\n  }\n  const meta = document.querySelector(".article-meta");\n  if (!meta) return;\n  let tag = $("#difficultyTag");\n  if (!tag) { tag = document.createElement("span"); tag.id = "difficultyTag"; tag.className = "difficulty-tag"; meta.appendChild(tag); }\n  if (!graded) { tag.innerHTML = ""; return; }\n  let cum = 0, level = "A1";\n  for (const l of ["A1","A2","B1","B2","C1","C2"]) { cum += counts[l]; if (cum >= graded * 0.85) { level = l; break; } }\n  const pct = Math.round(above / words.length * 100);\n  tag.innerHTML = `難度 <b>${level}</b> · 高於你程度 <b>${pct}%</b>`;\n}\n\n\nconst demoArticle = {\n  title: "Why Small Habits Matter More Than Big Plans",\n  author: "LingoReader Demo",\n  date: "",\n  url: "https://demo.local/small-habits",\n  paragraphs: [\n    "People often believe that meaningful change requires a dramatic plan. In reality, small actions repeated consistently can shape our lives more powerfully than a burst of motivation.",\n    "A habit may feel insignificant at first, but it reduces the number of decisions we need to make. Once an action becomes automatic, we can spend our attention on more difficult problems.",\n    "The key is not to aim for perfection. It is to create a system that is easy enough to continue, even on days when we feel tired or distracted."\n  ]\n};\n\nfunction toast(message) {\n  const node = $("#toast");\n  node.textContent = message;\n  node.classList.add("show");\n  clearTimeout(node.timer);\n  node.timer = setTimeout(() => node.classList.remove("show"), 2200);\n}\n\nfunction setLoading(button, loading, label) {\n  if (!button.dataset.original) button.dataset.original = button.textContent;\n  button.disabled = loading;\n  button.textContent = loading ? label : button.dataset.original;\n}\n\nfunction getAccessCode() {\n  return localStorage.getItem("lingoreader-access-code") || "";\n}\n\nasync function apiFetch(url, options = {}, allowRetry = true) {\n  const headers = new Headers(options.headers || {});\n  const code = getAccessCode();\n  if (code) headers.set("X-App-Code", code);\n\n  const response = await fetch(url, { ...options, headers });\n  if (response.status === 401 && allowRetry) {\n    const data = await response.clone().json().catch(() => ({}));\n    if (data.requiresAccessCode) {\n      const entered = window.prompt("請輸入你在 Vercel 設定的 APP_ACCESS_CODE：", code);\n      if (entered !== null && entered.trim()) {\n        localStorage.setItem("lingoreader-access-code", entered.trim());\n        return apiFetch(url, options, false);\n      }\n    }\n  }\n  return response;\n}\n\nfunction saveVocabulary() {\n  localStorage.setItem("lingoreader-vocabulary", JSON.stringify(state.vocabulary));\n  updateVocabCount();\n  renderVocabulary();\n  refreshSavedHighlights();\n}\n\nfunction updateVocabCount() {\n  $("#vocabCount").textContent = state.vocabulary.length;\n}\n\nfunction isSaved(word) {\n  return state.vocabulary.some(item => item.word.toLowerCase() === word.toLowerCase());\n}\n\nfunction refreshSavedHighlights() {\n  $$(".word").forEach(node => node.classList.toggle("saved", isSaved(node.dataset.word)));\n}\n\nfunction switchTab(name) {\n  $$(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.tab === name));\n  $$(".tab-content").forEach(content => content.classList.remove("active"));\n  $("#" + name + "Tab").classList.add("active");\n}\n\nfunction splitSentences(text) {\n  if (window.Intl?.Segmenter) {\n    const segmenter = new Intl.Segmenter("en", { granularity: "sentence" });\n    return [...segmenter.segment(text)].map(x => x.segment).filter(Boolean);\n  }\n  return text.match(/[^.!?]+[.!?]+[”’\\"]?|[^.!?]+$/g) || [text];\n}\n\nfunction tokenizeSentence(sentence) {\n  const fragment = document.createDocumentFragment();\n  const pieces = sentence.split(/([A-Za-z]+(?:[’\'][A-Za-z]+)*(?:-[A-Za-z]+)*)/g);\n  pieces.forEach(piece => {\n    if (/^[A-Za-z]+(?:[’\'][A-Za-z]+)*(?:-[A-Za-z]+)*$/.test(piece)) {\n      const word = document.createElement("span");\n      word.className = "word" + (isSaved(piece) ? " saved" : "");\n      word.dataset.word = piece;\n      word.dataset.level = wordLevel(piece);\n      word.textContent = piece;\n      word.addEventListener("click", event => {\n        event.stopPropagation();\n        lookupWord(piece);\n      });\n      fragment.appendChild(word);\n    } else {\n      fragment.appendChild(document.createTextNode(piece));\n    }\n  });\n  return fragment;\n}\n\nfunction renderArticle(article) {\n  state.article = article;\n  document.body.classList.add("article-ready");\n  $("#emptyState").classList.add("hidden");\n  $("#articleView").classList.remove("hidden");\n  $("#articleTitle").textContent = article.title || "Untitled article";\n  $("#articleAuthor").textContent = article.author ? `By ${article.author}` : "";\n  $("#articleDate").textContent = article.date || "";\n  try { $("#sourceHost").textContent = new URL(article.url).hostname.replace(/^www\\./, ""); }\n  catch { $("#sourceHost").textContent = "PASTED ARTICLE"; }\n\n  const body = $("#articleBody");\n  body.innerHTML = "";\n  article.paragraphs.forEach(paragraphText => {\n    const p = document.createElement("p");\n    splitSentences(paragraphText).forEach(sentenceText => {\n      const sentence = document.createElement("span");\n      sentence.className = "sentence";\n      sentence.dataset.sentence = sentenceText.trim();\n      sentence.appendChild(tokenizeSentence(sentenceText));\n      sentence.addEventListener("click", () => selectSentence(sentence.dataset.sentence, sentence));\n      p.appendChild(sentence);\n    });\n    body.appendChild(p);\n  });\n  markAboveLevel();\n  ensureLegend();\n  showDifficulty(article);\n  window.scrollTo({ top: document.querySelector(".workspace").offsetTop - 14, behavior: "smooth" });\n}\n\nfunction selectSentence(text, element) {\n  if (!text) return;\n  if (state.selectedElement) state.selectedElement.classList.remove("selected");\n  state.selectedElement = element;\n  element.classList.add("selected");\n  state.selectedSentence = text;\n  $("#selectedSentence").textContent = text;\n  $("#analysisEmpty").classList.add("hidden");\n  $("#analysisContent").classList.remove("hidden");\n  $("#analysisResult").innerHTML = "";\n  switchTab("analysis");\n}\n\nasync function loadArticleFromUrl() {\n  const url = $("#urlInput").value.trim();\n  if (!url) return toast("先貼上文章網址");\n  const button = $("#loadBtn");\n  setLoading(button, true, "正在抓取文章…");\n  try {\n    const response = await apiFetch("/api/article", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify({ url })\n    });\n    const data = await response.json();\n    if (!response.ok) throw new Error(data.error || "無法讀取文章");\n    renderArticle(data);\n    toast("互動文章已生成");\n  } catch (error) {\n    toast(error.message);\n    $("#pastePanel").classList.remove("hidden");\n  } finally {\n    setLoading(button, false);\n  }\n}\n\nasync function lookupWord(word) {\n  switchTab("dictionary");\n  $("#dictionaryEmpty").classList.add("hidden");\n  const panel = $("#dictionaryContent");\n  panel.classList.remove("hidden");\n  panel.innerHTML = `<div class="loading"><span></span>正在查 ${escapeHtml(word)}…</div>`;\n  try {\n    const response = await apiFetch("/api/dictionary", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify({ word })\n    });\n    const data = await response.json();\n    if (!response.ok) throw new Error(data.error || "查詢失敗");\n    state.dictionaryData = data;\n    renderDictionary(data);\n  } catch (error) {\n    panel.innerHTML = `<div class="panel-empty"><div class="panel-icon">!</div><h3>查不到</h3><p>${escapeHtml(error.message)}</p></div>`;\n  }\n}\n\nfunction renderDictionary(data) {\n  if (data.notFound) {\n    $("#dictionaryContent").innerHTML = `<div class="panel-empty"><div class="panel-icon">?</div><h3>${escapeHtml(data.word)}</h3><p>免費英中字典沒有找到這個詞，可能是專有名詞或變化形。</p></div>`;\n    return;\n  }\n  const saved = isSaved(data.word);\n  const summary = (data.chineseSummary || []).length\n    ? `<div class="chinese-summary"><div class="summary-label">繁體中文意思</div><div class="summary-words">${(data.chineseSummary || []).map(x => `<span>${escapeHtml(x)}</span>`).join("")}</div></div>`\n    : `<div class="chinese-summary muted-summary"><div class="summary-label">中文意思</div><p>這個詞在免費字典裡暫時沒有中文對應，下面保留英文定義。</p></div>`;\n  const meanings = (data.meanings || []).map(meaning => `\n    <div class="meaning-block">\n      <div class="part"><strong>${escapeHtml(meaning.partOfSpeechZh || meaning.partOfSpeech)}</strong><span>${escapeHtml(meaning.partOfSpeech || "")}</span></div>\n      ${(meaning.definitions || []).map((d, i) => `\n        <div class="definition">\n          ${d.chinese?.length ? `<div class="zh-definition"><b>${i + 1}.</b> ${d.chinese.map(escapeHtml).join("、")}</div>` : ""}\n          ${d.definition ? `<div class="en-definition">${d.chinese?.length ? "" : `<b>${i + 1}.</b> `}${escapeHtml(d.definition)}</div>` : ""}\n          ${d.example ? `<div class="example"><span>例句</span> “${escapeHtml(d.example)}”</div>` : ""}\n        </div>`).join("")}\n    </div>`).join("");\n  const source = data.aiSource\n    ? `<div class="dict-source">${data.note ? escapeHtml(data.note) + "<br>" : ""}由 AI（Groq）即時解釋，僅供參考。</div>`\n    : (data.sourceUrl\n      ? `<div class="dict-source">資料來源：<a href="${escapeHtml(data.sourceUrl)}" target="_blank" rel="noopener">Wiktionary</a>，由 <a href="https://freedictionaryapi.com" target="_blank" rel="noopener">FreeDictionaryAPI.com</a> 提供</div>`\n      : "");\n  $("#dictionaryContent").innerHTML = `\n    <div class="dict-head">\n      <div><h3 class="dict-word">${escapeHtml(data.word)}</h3><div class="phonetic">${escapeHtml(data.phonetic || "")}</div></div>\n      <div>\n        <button class="icon-btn" style="position:static" id="playWordBtn" title="免費朗讀單字">▶</button>\n        <button class="save-btn ${saved ? "saved" : ""}" id="saveWordBtn">${saved ? "已收藏" : "+ 加入單字本"}</button>\n      </div>\n    </div>\n    ${summary}\n    ${meanings || `<p class="panel-empty">沒有可顯示的定義。</p>`}\n    ${source}`;\n  $("#saveWordBtn").addEventListener("click", () => toggleSaveWord(data));\n  $("#playWordBtn").addEventListener("click", () => speak(data.word));\n}\n\nfunction toggleSaveWord(data) {\n  const index = state.vocabulary.findIndex(item => item.word.toLowerCase() === data.word.toLowerCase());\n  if (index >= 0) {\n    const [removed] = state.vocabulary.splice(index, 1);\n    toast("已從單字本移除");\n    remoteRemove(removed.word);\n  } else {\n    const firstMeaning = data.meanings?.[0];\n    const firstEntry = firstMeaning?.definitions?.[0];\n    const chineseDefinition = firstEntry?.chinese?.join("、") || data.chineseSummary?.join("、") || "";\n    const item = {\n      word: data.word,\n      phonetic: data.phonetic || "",\n      partOfSpeech: firstMeaning?.partOfSpeechZh || firstMeaning?.partOfSpeech || "",\n      definition: chineseDefinition || firstEntry?.definition || "",\n      englishDefinition: firstEntry?.definition || "",\n      sentence: state.selectedSentence || "",\n      createdAt: new Date().toISOString()\n    };\n    state.vocabulary.unshift(item);\n    toast("已加入單字本");\n    remoteUpsert(item);\n  }\n  saveVocabulary();\n  renderDictionary(data);\n}\n\nasync function analyzeSentence() {\n  if (!state.selectedSentence) return toast("請先選擇句子");\n  const button = $("#analyzeBtn");\n  $("#analysisLoading").classList.remove("hidden");\n  $("#analysisResult").innerHTML = "";\n  setLoading(button, true, "解析中…");\n  try {\n    const response = await apiFetch("/api/analyze", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify({\n        sentence: state.selectedSentence,\n        level: $("#levelSelect").value,\n        targetLanguage: $("#languageSelect").value\n      })\n    });\n    const data = await response.json();\n    if (!response.ok) throw new Error(data.error || "解析失敗");\n    renderAnalysis(data);\n  } catch (error) {\n    $("#analysisResult").innerHTML = `<div class="result-section"><div class="section-label">無法解析</div><p>${escapeHtml(error.message)}</p></div>`;\n  } finally {\n    $("#analysisLoading").classList.add("hidden");\n    setLoading(button, false);\n  }\n}\n\nfunction renderItems(items, titleKey, bodyKey) {\n  if (!items?.length) return `<p>這句沒有特別需要補充的內容。</p>`;\n  return `<div class="analysis-list">${items.map(item => `\n    <div class="analysis-item"><strong>${escapeHtml(item[titleKey] || "")}</strong><span>${escapeHtml(item[bodyKey] || "")}${item.example ? `<br>例：${escapeHtml(item.example)}` : ""}</span></div>\n  `).join("")}</div>`;\n}\n\nfunction renderAnalysis(data) {\n  $("#analysisResult").innerHTML = `\n    <section class="result-section"><div class="section-label">自然翻譯</div><p class="translation">${escapeHtml(data.translation || "")}</p></section>\n    <section class="result-section"><div class="section-label">這句在說什麼</div><p>${escapeHtml(data.plainMeaning || "")}</p></section>\n    <section class="result-section"><div class="section-label">句子結構</div><p>${escapeHtml(data.structure || "")}</p></section>\n    <section class="result-section"><div class="section-label">文法與句型</div>${renderItems(data.grammar, "pattern", "explanation")}</section>\n    <section class="result-section"><div class="section-label">慣用語與搭配</div>${renderItems(data.phrases, "phrase", "meaning")}</section>\n    <section class="result-section"><div class="section-label">重點單字</div>${renderItems(data.keyWords, "word", "meaning")}</section>\n    ${data.note ? `<section class="result-section"><div class="section-label">注意</div><p>${escapeHtml(data.note)}</p></section>` : ""}\n  `;\n}\n\nfunction renderVocabulary() {\n  const query = $("#vocabSearch")?.value.toLowerCase().trim() || "";\n  const lvlFilter = $("#vocabLevelFilter")?.value || "";\n  const items = state.vocabulary.filter(item => {\n    const textOk = !query || item.word.toLowerCase().includes(query) || (item.definition || "").toLowerCase().includes(query);\n    if (!textOk) return false;\n    if (!lvlFilter) return true;\n    const l = wordLevel(item.word);\n    return lvlFilter === "none" ? !l : l === lvlFilter;\n  });\n  const list = $("#vocabList");\n  if (!items.length) {\n    list.innerHTML = `<div class="panel-empty"><div class="panel-icon">☆</div><h3>${query ? "找不到單字" : "單字本還是空的"}</h3><p>閱讀時點一下單字，再按「加入單字本」。</p></div>`;\n    return;\n  }\n  list.innerHTML = items.map(item => `\n    <div class="vocab-card">\n      <div class="vocab-card-head"><h4>${escapeHtml(item.word)}${wordLevel(item.word) ? `<span class="lvl-badge" data-lvl="${wordLevel(item.word)}">${wordLevel(item.word)}</span>` : ""}</h4><button class="remove-btn" data-remove="${escapeHtml(item.word)}">移除</button></div>\n      <div class="phonetic">${escapeHtml(item.phonetic || "")} ${item.partOfSpeech ? `· ${escapeHtml(item.partOfSpeech)}` : ""}</div>\n      <p>${escapeHtml(item.definition || "")}</p>\n      ${item.englishDefinition ? `<p class="vocab-english">${escapeHtml(item.englishDefinition)}</p>` : ""}\n      ${item.sentence ? `<p><i>${escapeHtml(item.sentence)}</i></p>` : ""}\n    </div>`).join("");\n  $$(\'[data-remove]\').forEach(button => button.addEventListener("click", () => {\n    state.vocabulary = state.vocabulary.filter(item => item.word !== button.dataset.remove);\n    remoteRemove(button.dataset.remove);\n    saveVocabulary();\n  }));\n}\n\nfunction exportCsv() {\n  if (!state.vocabulary.length) return toast("單字本還是空的");\n  const rows = [["word", "phonetic", "part_of_speech", "chinese_meaning", "english_definition", "example_sentence"], ...state.vocabulary.map(i => [i.word, i.phonetic, i.partOfSpeech, i.definition, i.englishDefinition || "", i.sentence])];\n  const csv = rows.map(row => row.map(cell => `"${String(cell || "").replaceAll(\'"\', \'""\')}"`).join(",")).join("\\n");\n  const blob = new Blob(["\\ufeff" + csv], { type: "text/csv;charset=utf-8" });\n  const link = document.createElement("a");\n  link.href = URL.createObjectURL(blob);\n  link.download = "lingoreader-vocabulary.csv";\n  link.click();\n  URL.revokeObjectURL(link.href);\n}\n\nfunction speak(text) {\n  speechSynthesis.cancel();\n  const utterance = new SpeechSynthesisUtterance(text);\n  utterance.lang = "en-US";\n  utterance.rate = .88;\n  speechSynthesis.speak(utterance);\n}\n\nfunction escapeHtml(value) {\n  return String(value ?? "").replace(/[&<>\'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\'":"&#39;",\'"\':"&quot;"}[char]));\n}\n\nasync function checkStatus() {\n  try {\n    const data = await fetch("/api/status").then(r => r.json());\n    const pill = $("#aiStatus");\n    const lockLabel = data.accessProtected ? " · 已鎖定" : "";\n    pill.textContent = (data.aiReady ? ((data.aiProvider || "AI") + " 解析可用") : "免費朗讀／字典可用") + lockLabel;\n    pill.classList.remove("ready", "off");\n    pill.classList.add(data.aiReady ? "ready" : "off");\n    pill.title = data.aiReady ? "整句翻譯、文法與慣用語解析已啟用" : "朗讀與字典不需要 API Key；整句 AI 解析尚未啟用";\n  } catch {}\n}\n\nasync function remoteUpsert(item) {\n  if (!SYNC.enabled) return;\n  try {\n    await apiFetch("/api/vocab", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify(item)\n    });\n  } catch { toast("雲端同步失敗，已存在本機"); }\n}\n\nasync function remoteRemove(word) {\n  if (!SYNC.enabled) return;\n  try {\n    await apiFetch("/api/vocab?word=" + encodeURIComponent(word), { method: "DELETE" });\n  } catch { toast("雲端移除失敗，已改本機"); }\n}\n\nasync function initVocab() {\n  try {\n    const response = await apiFetch("/api/vocab");\n    if (!response.ok) throw new Error("sync-off");\n    const data = await response.json();\n    SYNC.enabled = true;\n    const remote = data.items || [];\n    const remoteWords = new Set(remote.map(i => (i.word || "").toLowerCase()));\n    const localOnly = state.vocabulary.filter(i => !remoteWords.has((i.word || "").toLowerCase()));\n    if (localOnly.length) {\n      try {\n        await apiFetch("/api/vocab/bulk", {\n          method: "POST",\n          headers: { "Content-Type": "application/json" },\n          body: JSON.stringify(localOnly)\n        });\n      } catch {}\n    }\n    state.vocabulary = [...remote, ...localOnly]\n      .sort((a, b) => String(b.createdAt || "").localeCompare(String(a.createdAt || "")));\n    localStorage.setItem("lingoreader-vocabulary", JSON.stringify(state.vocabulary));\n  } catch {\n    SYNC.enabled = false; // 離線或尚未設定雲端 → 只用本機\n  }\n  updateVocabCount();\n  renderVocabulary();\n  refreshSavedHighlights();\n}\n\n$("#loadBtn").addEventListener("click", loadArticleFromUrl);\n$("#urlInput").addEventListener("keydown", e => { if (e.key === "Enter") loadArticleFromUrl(); });\n$("#pasteModeBtn").addEventListener("click", () => $("#pastePanel").classList.toggle("hidden"));\n$("#useTextBtn").addEventListener("click", () => {\n  const text = $("#manualText").value.trim();\n  if (!text) return toast("請貼上文章文字");\n  renderArticle({ title: $("#manualTitle").value.trim() || "Pasted article", author: "", date: "", url: "pasted://article", paragraphs: text.split(/\\n\\s*\\n/).map(p => p.replace(/\\s+/g, " ").trim()).filter(Boolean) });\n});\n$("#demoBtn").addEventListener("click", () => renderArticle(demoArticle));\n$("#analyzeBtn").addEventListener("click", analyzeSentence);\n$("#speakSentenceBtn").addEventListener("click", () => speak(state.selectedSentence));\n$("#openVocabBtn").addEventListener("click", () => {\n  switchTab("vocabulary");\n  if (window.matchMedia("(max-width: 980px)").matches) {\n    document.querySelector(".study-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });\n  }\n});\n$("#vocabSearch").addEventListener("input", renderVocabulary);\n$("#exportBtn").addEventListener("click", exportCsv);\n$$(\'.tab\').forEach(tab => tab.addEventListener("click", () => switchTab(tab.dataset.tab)));\n\n(function injectVocabFilter() {\n  const tb = document.querySelector(".vocab-toolbar");\n  if (tb && !$("#vocabLevelFilter")) {\n    const sel = document.createElement("select");\n    sel.id = "vocabLevelFilter";\n    sel.title = "依 CEFR 等級篩選";\n    sel.innerHTML = \'<option value="">全部等級</option>\' + ["A1","A2","B1","B2","C1","C2"].map(l => `<option value="${l}">${l}</option>`).join("") + \'<option value="none">未分級</option>\';\n    tb.insertBefore(sel, $("#exportBtn"));\n    sel.addEventListener("change", renderVocabulary);\n  }\n})();\n$("#levelSelect")?.addEventListener("change", markAboveLevel);\n\ninitVocab();\ncheckStatus();\nloadCefr().then(() => { if (state.article) markAboveLevel(); renderVocabulary(); if (state.article) showDifficulty(state.article); });\n'

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
MAX_REMOTE_BYTES = 4_000_000

app = FastAPI(title="LingoReader", docs_url=None, redoc_url=None)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
VOCAB_TABLE = os.getenv("SUPABASE_VOCAB_TABLE", "vocabulary").strip() or "vocabulary"


class ArticleRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class DictionaryRequest(BaseModel):
    word: str = Field(min_length=1, max_length=100)


class AnalyzeRequest(BaseModel):
    sentence: str = Field(min_length=1, max_length=1200)
    level: str = Field(default="A2", max_length=10)
    targetLanguage: str = Field(default="繁體中文", max_length=40)


class VocabItem(BaseModel):
    word: str = Field(min_length=1, max_length=100)
    phonetic: str = Field(default="", max_length=120)
    partOfSpeech: str = Field(default="", max_length=80)
    definition: str = Field(default="", max_length=2000)
    englishDefinition: str = Field(default="", max_length=2000)
    sentence: str = Field(default="", max_length=1200)
    createdAt: str = Field(default="", max_length=40)


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

def build_analyze_prompt(sentence: str, level: str, target_language: str) -> str:
    return f"""你是細心、簡單好懂的英文閱讀老師。學習者程度是 CEFR {level}，請使用{target_language}說明。
分析下列英文句子。翻譯要自然，文法說明要符合程度；只指出句中真的存在的片語、搭配與文法，不要硬湊。

英文句子：
{sentence}

輸出要求（請只回傳一個 JSON 物件，不要有 JSON 以外的任何文字或 markdown）：
- translation：完整自然翻譯
- plainMeaning：用白話解釋整句意思
- structure：清楚拆解主詞、動詞、受詞、子句與修飾語
- grammar：最多 4 個真正重要的文法或句型，每個含 pattern、explanation、example
- phrases：最多 4 個句中實際存在的慣用語、片語或搭配詞，每個含 phrase、meaning
- keyWords：最多 5 個值得學的單字，每個含 word、meaning
- note：容易誤解或值得注意處；沒有就回空字串
"""


def call_groq(api_key: str, model: str, prompt: str) -> dict[str, Any]:
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你只會輸出一個合法的 JSON 物件，不含任何多餘文字或 markdown。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 2600,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    return fetch_json(endpoint, method="POST", payload=payload, headers=headers, timeout=45)


def groq_output_text(data: dict[str, Any]) -> str:
    try:
        text = data["choices"][0]["message"]["content"]
        return text if isinstance(text, str) else ""
    except (KeyError, IndexError, TypeError):
        return ""


CEFR_SOURCE = os.getenv("CEFR_SOURCE_URL", "https://raw.githubusercontent.com/tyypgzl/Oxford-5000-words/main/full-word.json").strip()
_CEFR_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
_cefr_cache: dict[str, str] = {}


def build_cefr_map() -> dict[str, str]:
    if _cefr_cache:
        return _cefr_cache
    data = fetch_json(CEFR_SOURCE, timeout=25)
    result: dict[str, str] = {}
    if isinstance(data, list):
        for entry in data:
            value = entry.get("value") if isinstance(entry, dict) else None
            if not isinstance(value, dict):
                continue
            word = str(value.get("word", "")).strip().lower()
            level = str(value.get("level", "")).strip().upper()
            if word and level in _CEFR_ORDER and re.fullmatch(r"[a-z][a-z' -]*", word):
                if word not in result or _CEFR_ORDER[level] < _CEFR_ORDER[result[word]]:
                    result[word] = level
    if result:
        _cefr_cache.update(result)
    return result


def groq_chinese_gloss(api_key: str, word: str) -> list[str]:
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", model):
        model = "llama-3.3-70b-versatile"
    prompt = (
        f'\u8acb\u7d66\u82f1\u6587\u55ae\u5b57 "{word}" \u6700\u5e38\u898b\u7684 1 \u5230 3 \u500b\u7e41\u9ad4\u4e2d\u6587\u610f\u601d\u3002'
        '\u53ea\u8f38\u51fa\u4e00\u500b JSON \u7269\u4ef6\uff0c\u683c\u5f0f\uff1a{"meanings": ["\u610f\u601d1", "\u610f\u601d2"]}\uff0c\u4e0d\u8981\u5176\u4ed6\u6587\u5b57\u3002'
    )
    try:
        response = call_groq(api_key, model, prompt)
        text = groq_output_text(response).strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
        parsed = json.loads(text)
        items = parsed.get("meanings") if isinstance(parsed, dict) else None
        if isinstance(items, list):
            return _unique_strings([str(x) for x in items], 4)
    except Exception:
        return []
    return []


def groq_dictionary_entry(api_key: str, word: str) -> dict[str, Any] | None:
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", model):
        model = "llama-3.3-70b-versatile"
    prompt = (
        f'\u4f60\u662f\u82f1\u8a9e\u5b78\u7fd2\u5b57\u5178\u3002\u4f7f\u7528\u8005\u67e5\u7684\u8a5e "{word}" \u53ef\u80fd\u662f\u82f1\u6587\u55ae\u5b57\u3001\u8b8a\u5316\u5f62\uff08\u8907\u6578/\u904e\u53bb\u5f0f/\u73fe\u5728\u5206\u8a5e\u7b49\uff09\u3001\u5c08\u6709\u540d\u8a5e\uff0c\u6216\u5176\u4ed6\u8a9e\u8a00\u7684\u8a5e\u3002'
        '\u8acb\u4ea7\u51fa\u4e00\u500b JSON \u5b57\u5178\u8a5e\u689d\uff0c\u53ea\u8f38\u51fa JSON\uff0c\u4e0d\u8981\u5176\u4ed6\u6587\u5b57\u3002\u683c\u5f0f\uff1a'
        '{"phonetic": "IPA \u97f3\u6a19\uff0c\u82e5\u7121\u628a\u63e1\u5c31\u7559\u7a7a\u5b57\u4e32", '
        '"chineseSummary": ["\u6700\u5e38\u898b\u7684 1-3 \u500b\u7e41\u9ad4\u4e2d\u6587\u610f\u601d"], '
        '"meanings": [{"partOfSpeech": "\u82f1\u6587\u8a5e\u6027\u5982 noun/verb", "partOfSpeechZh": "\u7e41\u4e2d\u8a5e\u6027\u5982 \u540d\u8a5e/\u52d5\u8a5e", '
        '"definitions": [{"chinese": ["\u7e41\u4e2d\u610f\u601d"], "definition": "\u7c21\u77ed\u82f1\u6587\u89e3\u91cb", "example": "\u82f1\u6587\u4f8b\u53e5"}]}], '
        '"note": "\u82e5\u662f\u8b8a\u5316\u5f62\u8acb\u6307\u51fa\u539f\u5f62\uff1b\u82e5\u662f\u5176\u4ed6\u8a9e\u8a00\u8acb\u6307\u51fa\u8a9e\u8a00\u8207\u610f\u601d\uff1b\u5426\u5247\u7a7a\u5b57\u4e32"}\u3002'
        '\u6700\u591a 3 \u500b meanings\uff0c\u6bcf\u500b\u6700\u591a 2 \u500b definitions\u3002'
    )
    try:
        response = call_groq(api_key, model, prompt)
        text = groq_output_text(response).strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return None
        raw_meanings = parsed.get("meanings") if isinstance(parsed.get("meanings"), list) else []
        clean_meanings: list[dict[str, Any]] = []
        for mn in raw_meanings[:3]:
            if not isinstance(mn, dict):
                continue
            raw_defs = mn.get("definitions") if isinstance(mn.get("definitions"), list) else []
            clean_defs = []
            for d in raw_defs[:2]:
                if not isinstance(d, dict):
                    continue
                ch = d.get("chinese")
                ch_list = [str(x) for x in ch] if isinstance(ch, list) else ([str(ch)] if ch else [])
                clean_defs.append({
                    "chinese": _unique_strings(ch_list, 4),
                    "definition": str(d.get("definition", "")),
                    "example": str(d.get("example", "")),
                })
            clean_meanings.append({
                "partOfSpeech": str(mn.get("partOfSpeech", "")),
                "partOfSpeechZh": str(mn.get("partOfSpeechZh", "")),
                "definitions": clean_defs,
            })
        summary = parsed.get("chineseSummary")
        summary_list = [str(x) for x in summary] if isinstance(summary, list) else []
        result = {
            "word": word,
            "phonetic": str(parsed.get("phonetic", "")),
            "audio": "",
            "chineseSummary": _unique_strings(summary_list, 8),
            "meanings": clean_meanings,
            "sourceUrl": "",
            "aiSource": True,
            "note": str(parsed.get("note", "")),
        }
        if result["chineseSummary"] or clean_meanings:
            return result
    except Exception:
        return None
    return None


def _dictionary_not_found(word: str) -> dict[str, Any]:
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        entry = groq_dictionary_entry(groq_key, word)
        if entry:
            return entry
    return {"word": word, "notFound": True}


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


def supabase_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def supabase_call(method: str, path: str, *, params: dict[str, str] | None = None, payload: Any | None = None, prefer: str | None = None) -> Any:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urlencode(params)
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=15) as response:
        raw = response.read(MAX_REMOTE_BYTES + 1)
    if not raw:
        return []
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return []


def _vocab_row(item: VocabItem) -> dict[str, Any]:
    row = {
        "word": item.word.strip(),
        "phonetic": item.phonetic,
        "part_of_speech": item.partOfSpeech,
        "definition": item.definition,
        "english_definition": item.englishDefinition,
        "sentence": item.sentence,
    }
    if item.createdAt:
        row["created_at"] = item.createdAt
    return row


def _vocab_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "word": row.get("word", "") or "",
        "phonetic": row.get("phonetic", "") or "",
        "partOfSpeech": row.get("part_of_speech", "") or "",
        "definition": row.get("definition", "") or "",
        "englishDefinition": row.get("english_definition", "") or "",
        "sentence": row.get("sentence", "") or "",
        "createdAt": row.get("created_at", "") or "",
    }


def _require_sync() -> None:
    if not supabase_ready():
        raise HTTPException(status_code=503, detail={"message": "雲端同步尚未設定", "syncDisabled": True})


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
    groq_key = bool(os.getenv("GROQ_API_KEY", "").strip())
    gemini_key = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "aiReady": groq_key or gemini_key,
        "aiProvider": "Groq" if groq_key else ("Gemini" if gemini_key else "None"),
        "accessProtected": bool(os.getenv("APP_ACCESS_CODE", "").strip()),
        "syncReady": supabase_ready(),
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


POS_ZH = {
    "noun": "名詞", "verb": "動詞", "adjective": "形容詞", "adverb": "副詞",
    "pronoun": "代名詞", "preposition": "介系詞", "conjunction": "連接詞",
    "interjection": "感嘆詞", "determiner": "限定詞", "article": "冠詞",
    "numeral": "數詞", "proper noun": "專有名詞", "phrase": "片語",
}
CHINESE_CODES = {"zh", "zho", "cmn", "zh-hant", "zh-tw", "yue", "nan"}


def _unique_strings(values: list[str], limit: int = 12) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = " ".join(str(value or "").split()).strip(" ,;；")
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
        if len(result) >= limit:
            break
    return result


def _chinese_translations(sense: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in sense.get("translations", []) or []:
        language = item.get("language", {}) or {}
        code = str(language.get("code", "")).lower()
        name = str(language.get("name", "")).lower()
        if code in CHINESE_CODES or "chinese" in name or "mandarin" in name:
            values.append(str(item.get("word", "")))
    return _unique_strings(values, 8)


@app.post("/api/dictionary")
def api_dictionary(payload: DictionaryRequest, x_app_code: str | None = Header(default=None)) -> dict[str, Any]:
    check_access(x_app_code)
    word = re.sub(r"[^A-Za-z'-]", "", payload.word).strip("'-")
    if not word:
        raise HTTPException(status_code=400, detail="無效的單字")

    url = f"https://freedictionaryapi.com/api/v1/entries/en/{quote(word)}?translations=true"
    try:
        data = fetch_json(url, timeout=15)
    except HTTPError as exc:
        if exc.code == 404:
            return _dictionary_not_found(word)
        if exc.code == 429:
            raise HTTPException(status_code=429, detail="免費英中字典請求太頻繁，請稍後再試") from exc
        raise HTTPException(status_code=502, detail=http_error_message(exc)) from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise HTTPException(status_code=502, detail="免費英中字典暫時無法連線") from exc

    entries = data.get("entries", []) if isinstance(data, dict) else []
    if not entries:
        return _dictionary_not_found(word)

    phonetic = ""
    summary_words: list[str] = []
    grouped: dict[str, dict[str, Any]] = {}
    total_definitions = 0

    for entry in entries:
        if not phonetic:
            for pronunciation in entry.get("pronunciations", []) or []:
                if pronunciation.get("type") == "ipa" and pronunciation.get("text"):
                    phonetic = str(pronunciation["text"])
                    break
        pos = str(entry.get("partOfSpeech", "")).strip() or "other"
        key = pos.lower()
        group = grouped.setdefault(
            key,
            {"partOfSpeech": pos, "partOfSpeechZh": POS_ZH.get(key, pos), "definitions": []},
        )
        for sense in entry.get("senses", []) or []:
            if total_definitions >= 18 or len(group["definitions"]) >= 5:
                break
            chinese = _chinese_translations(sense)
            summary_words.extend(chinese)
            examples = sense.get("examples", []) or []
            definition = " ".join(str(sense.get("definition", "")).split())
            example = " ".join(str(examples[0]).split()) if examples else ""
            if definition or chinese:
                group["definitions"].append(
                    {"definition": definition, "example": example, "chinese": chinese}
                )
                total_definitions += 1
        if total_definitions >= 18:
            break

    meanings = [item for item in grouped.values() if item["definitions"]]
    chinese_summary = _unique_strings(summary_words, 14)
    ai_chinese = False
    if not chinese_summary:
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if groq_key:
            gloss = groq_chinese_gloss(groq_key, str(data.get("word") or word))
            if gloss:
                chinese_summary = gloss
                ai_chinese = True
    return {
        "word": str(data.get("word") or word),
        "phonetic": phonetic,
        "audio": "",
        "chineseSummary": chinese_summary,
        "aiChinese": ai_chinese,
        "meanings": meanings,
        "sourceUrl": str((data.get("source") or {}).get("url") or ""),
    }


@app.post("/api/analyze")
def api_analyze(payload: AnalyzeRequest, x_app_code: str | None = Header(default=None)) -> dict[str, Any]:
    check_access(x_app_code)
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not groq_key and not gemini_key:
        raise HTTPException(
            status_code=503,
            detail="尚未設定 AI 金鑰。朗讀、字典與單字本完全免費可用；設定 GROQ_API_KEY（推薦，較快）或 GEMINI_API_KEY 後才會啟用整句翻譯與文法解析。",
        )

    level = payload.level if payload.level in {"A1", "A2", "B1", "B2", "C1"} else "A2"
    target_language = payload.targetLanguage if payload.targetLanguage in {"繁體中文", "日文", "英文"} else "繁體中文"
    prompt = build_analyze_prompt(payload.sentence.strip(), level, target_language)

    if groq_key:
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", model):
            model = "llama-3.3-70b-versatile"
        try:
            response = call_groq(groq_key, model, prompt)
        except HTTPError as exc:
            message = http_error_message(exc)
            if exc.code == 429:
                message = "Groq 免費額度暫時用完或請求太頻繁，稍後再試。朗讀與字典不受影響。"
            elif exc.code in {401, 403}:
                message = "Groq API Key 無效或沒有權限，請到 console.groq.com 檢查金鑰。"
            raise HTTPException(status_code=502, detail=message) from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise HTTPException(status_code=502, detail="Groq 暫時無法連線，請稍後再試") from exc
        output = groq_output_text(response).strip()
    else:
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip() or "gemini-2.5-flash-lite"
        if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
            model = "gemini-2.5-flash-lite"
        try:
            response = call_gemini(gemini_key, model, prompt)
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
        raise HTTPException(status_code=502, detail="AI 沒有回傳可用內容，請再試一次")
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="AI 回傳格式不完整，請再試一次") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="AI 回傳格式不正確，請再試一次")
    return parsed

@app.get("/api/vocab")
def api_vocab_list(x_app_code: str | None = Header(default=None)) -> dict[str, Any]:
    check_access(x_app_code)
    _require_sync()
    try:
        rows = supabase_call("GET", VOCAB_TABLE, params={"select": "*", "order": "created_at.desc"})
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=http_error_message(exc)) from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise HTTPException(status_code=502, detail="雲端單字本暫時無法連線") from exc
    items = [_vocab_item(row) for row in rows] if isinstance(rows, list) else []
    return {"items": items}


@app.post("/api/vocab")
def api_vocab_upsert(payload: VocabItem, x_app_code: str | None = Header(default=None)) -> dict[str, Any]:
    check_access(x_app_code)
    _require_sync()
    try:
        supabase_call("POST", VOCAB_TABLE, payload=[_vocab_row(payload)], prefer="resolution=merge-duplicates,return=minimal")
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=http_error_message(exc)) from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise HTTPException(status_code=502, detail="雲端同步失敗") from exc
    return {"ok": True}


@app.post("/api/vocab/bulk")
def api_vocab_bulk(payload: list[VocabItem], x_app_code: str | None = Header(default=None)) -> dict[str, Any]:
    check_access(x_app_code)
    _require_sync()
    rows = [_vocab_row(item) for item in payload[:500]]
    if not rows:
        return {"ok": True, "count": 0}
    try:
        supabase_call("POST", VOCAB_TABLE, payload=rows, prefer="resolution=merge-duplicates,return=minimal")
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=http_error_message(exc)) from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise HTTPException(status_code=502, detail="雲端同步失敗") from exc
    return {"ok": True, "count": len(rows)}


@app.delete("/api/vocab")
def api_vocab_delete(word: str, x_app_code: str | None = Header(default=None)) -> dict[str, Any]:
    check_access(x_app_code)
    _require_sync()
    target = (word or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="缺少要移除的單字")
    try:
        supabase_call("DELETE", VOCAB_TABLE, params={"word": f"eq.{target}"}, prefer="return=minimal")
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=http_error_message(exc)) from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise HTTPException(status_code=502, detail="雲端移除失敗") from exc
    return {"ok": True}


@app.get("/api/cefr")
def api_cefr() -> Response:
    try:
        words = build_cefr_map()
    except Exception as exc:  # noqa: BLE001
        print("CEFR fetch failed:", repr(exc))
        words = {}
    body = json.dumps({"words": words}, ensure_ascii=False)
    return Response(body, media_type="application/json; charset=utf-8", headers={"Cache-Control": "public, max-age=86400"})
