const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = {
  article: null,
  selectedSentence: "",
  selectedElement: null,
  dictionaryData: null,
  vocabulary: JSON.parse(localStorage.getItem("lingoreader-vocabulary") || "[]"),
};

const SYNC = { enabled: false };

let CEFR = {};
const CEFR_ORDER = { A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6 };
function wordLevel(w) { return CEFR[String(w || "").toLowerCase()] || ""; }
function readerLevelIdx() { return CEFR_ORDER[($("#levelSelect")?.value) || "A2"] || 2; }
const CEFR_SRC = "https://raw.githubusercontent.com/tyypgzl/Oxford-5000-words/main/full-word.json";
function cacheCefr() { try { localStorage.setItem("lingoreader-cefr", JSON.stringify(CEFR)); } catch {} }
async function loadCefr() {
  try { const c = localStorage.getItem("lingoreader-cefr"); if (c) { CEFR = JSON.parse(c) || {}; if (Object.keys(CEFR).length) return; } } catch {}
  // fast path: backend proxy (used only if it returns a populated map)
  try {
    const r = await fetch("/api/cefr");
    if (r.ok) { const d = await r.json(); if (d.words && Object.keys(d.words).length) { CEFR = d.words; cacheCefr(); return; } }
  } catch {}
  // fallback: fetch the Oxford word list directly and build the map client-side
  try {
    const arr = await fetch(CEFR_SRC, { cache: "force-cache" }).then(r => r.json());
    const map = {};
    for (const e of arr) {
      const v = (e && e.value) || {};
      const w = String(v.word || "").trim().toLowerCase();
      const l = String(v.level || "").trim().toUpperCase();
      if (w && CEFR_ORDER[l] && /^[a-z][a-z' -]*$/.test(w)) {
        if (!(w in map) || CEFR_ORDER[l] < CEFR_ORDER[map[w]]) map[w] = l;
      }
    }
    if (Object.keys(map).length) { CEFR = map; cacheCefr(); }
  } catch {}
}
function markAboveLevel() {
  const idx = readerLevelIdx();
  $$(".word").forEach(n => {
    const l = n.dataset.level || "";
    n.classList.toggle("above-level", !!l && (CEFR_ORDER[l] || 0) > idx);
  });
}
function ensureLegend() {
  const help = document.querySelector(".reader-help");
  if (help && !$("#levelLegend")) {
    const span = document.createElement("span");
    span.id = "levelLegend";
    span.className = "reader-legend";
    span.innerHTML = '<i></i>高於你程度的字';
    help.appendChild(span);
  }
}
function showDifficulty(article) {
  const words = (article.paragraphs || []).join(" ").toLowerCase().match(/[a-z][a-z'-]*/g) || [];
  const counts = { A1:0, A2:0, B1:0, B2:0, C1:0, C2:0 };
  let graded = 0, above = 0;
  const idx = readerLevelIdx();
  for (const w of words) {
    const l = wordLevel(w);
    if (!l) continue;
    counts[l]++; graded++;
    if ((CEFR_ORDER[l] || 0) > idx) above++;
  }
  const meta = document.querySelector(".article-meta");
  if (!meta) return;
  let tag = $("#difficultyTag");
  if (!tag) { tag = document.createElement("span"); tag.id = "difficultyTag"; tag.className = "difficulty-tag"; meta.appendChild(tag); }
  if (!graded) { tag.innerHTML = ""; return; }
  let cum = 0, level = "A1";
  for (const l of ["A1","A2","B1","B2","C1","C2"]) { cum += counts[l]; if (cum >= graded * 0.85) { level = l; break; } }
  const pct = Math.round(above / words.length * 100);
  tag.innerHTML = `難度 <b>${level}</b> · 高於你程度 <b>${pct}%</b>`;
}


const demoArticle = {
  title: "Why Small Habits Matter More Than Big Plans",
  author: "LingoReader Demo",
  date: "",
  url: "https://demo.local/small-habits",
  paragraphs: [
    "People often believe that meaningful change requires a dramatic plan. In reality, small actions repeated consistently can shape our lives more powerfully than a burst of motivation.",
    "A habit may feel insignificant at first, but it reduces the number of decisions we need to make. Once an action becomes automatic, we can spend our attention on more difficult problems.",
    "The key is not to aim for perfection. It is to create a system that is easy enough to continue, even on days when we feel tired or distracted."
  ]
};

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(node.timer);
  node.timer = setTimeout(() => node.classList.remove("show"), 2200);
}

function setLoading(button, loading, label) {
  if (!button.dataset.original) button.dataset.original = button.textContent;
  button.disabled = loading;
  button.textContent = loading ? label : button.dataset.original;
}

function getAccessCode() {
  return localStorage.getItem("lingoreader-access-code") || "";
}

async function apiFetch(url, options = {}, allowRetry = true) {
  const headers = new Headers(options.headers || {});
  const code = getAccessCode();
  if (code) headers.set("X-App-Code", code);

  const response = await fetch(url, { ...options, headers });
  if (response.status === 401 && allowRetry) {
    const data = await response.clone().json().catch(() => ({}));
    if (data.requiresAccessCode) {
      const entered = window.prompt("請輸入你在 Vercel 設定的 APP_ACCESS_CODE：", code);
      if (entered !== null && entered.trim()) {
        localStorage.setItem("lingoreader-access-code", entered.trim());
        return apiFetch(url, options, false);
      }
    }
  }
  return response;
}

function saveVocabulary() {
  localStorage.setItem("lingoreader-vocabulary", JSON.stringify(state.vocabulary));
  updateVocabCount();
  renderVocabulary();
  refreshSavedHighlights();
}

function updateVocabCount() {
  $("#vocabCount").textContent = state.vocabulary.length;
}

function isSaved(word) {
  return state.vocabulary.some(item => item.word.toLowerCase() === word.toLowerCase());
}

function refreshSavedHighlights() {
  $$(".word").forEach(node => node.classList.toggle("saved", isSaved(node.dataset.word)));
}

function switchTab(name) {
  $$(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.tab === name));
  $$(".tab-content").forEach(content => content.classList.remove("active"));
  $("#" + name + "Tab").classList.add("active");
}

function splitSentences(text) {
  if (window.Intl?.Segmenter) {
    const segmenter = new Intl.Segmenter("en", { granularity: "sentence" });
    return [...segmenter.segment(text)].map(x => x.segment).filter(Boolean);
  }
  return text.match(/[^.!?]+[.!?]+[”’\"]?|[^.!?]+$/g) || [text];
}

function tokenizeSentence(sentence) {
  const fragment = document.createDocumentFragment();
  const pieces = sentence.split(/([A-Za-z]+(?:[’'][A-Za-z]+)*(?:-[A-Za-z]+)*)/g);
  pieces.forEach(piece => {
    if (/^[A-Za-z]+(?:[’'][A-Za-z]+)*(?:-[A-Za-z]+)*$/.test(piece)) {
      const word = document.createElement("span");
      word.className = "word" + (isSaved(piece) ? " saved" : "");
      word.dataset.word = piece;
      word.dataset.level = wordLevel(piece);
      word.textContent = piece;
      word.addEventListener("click", event => {
        event.stopPropagation();
        lookupWord(piece);
      });
      fragment.appendChild(word);
    } else {
      fragment.appendChild(document.createTextNode(piece));
    }
  });
  return fragment;
}

function renderArticle(article, opts = {}) {
  state.article = article;
  document.body.classList.add("article-ready");
  $("#emptyState").classList.add("hidden");
  $("#articleView").classList.remove("hidden");
  const titleEl = $("#articleTitle");
  titleEl.innerHTML = "";
  titleEl.appendChild(tokenizeSentence(article.title || "Untitled article"));
  $("#articleAuthor").textContent = article.author ? `By ${article.author}` : "";
  $("#articleDate").textContent = article.date || "";
  try { $("#sourceHost").textContent = new URL(article.url).hostname.replace(/^www\./, ""); }
  catch { $("#sourceHost").textContent = "PASTED ARTICLE"; }

  const body = $("#articleBody");
  body.innerHTML = "";
  article.paragraphs.forEach(paragraphText => {
    const p = document.createElement("p");
    splitSentences(paragraphText).forEach(sentenceText => {
      const sentence = document.createElement("span");
      sentence.className = "sentence";
      sentence.dataset.sentence = sentenceText.trim();
      sentence.appendChild(tokenizeSentence(sentenceText));
      sentence.addEventListener("click", () => selectSentence(sentence.dataset.sentence, sentence));
      p.appendChild(sentence);
    });
    body.appendChild(p);
  });
  markAboveLevel();
  ensureLegend();
  showDifficulty(article);
  if (!opts.fromHistory) saveArticleHistory(article);
  window.scrollTo({ top: document.querySelector(".workspace").offsetTop - 14, behavior: "smooth" });
}

function selectSentence(text, element) {
  if (!text) return;
  if (state.selectedElement) state.selectedElement.classList.remove("selected");
  state.selectedElement = element;
  element.classList.add("selected");
  state.selectedSentence = text;
  $("#selectedSentence").textContent = text;
  $("#analysisEmpty").classList.add("hidden");
  $("#analysisContent").classList.remove("hidden");
  $("#analysisResult").innerHTML = "";
  switchTab("analysis");
}

async function loadArticleFromUrl() {
  const url = $("#urlInput").value.trim();
  if (!url) return toast("先貼上文章網址");
  const button = $("#loadBtn");
  setLoading(button, true, "正在抓取文章…");
  try {
    const response = await apiFetch("/api/article", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "無法讀取文章");
    renderArticle(data);
    toast("互動文章已生成");
  } catch (error) {
    toast(error.message);
    $("#pastePanel").classList.remove("hidden");
  } finally {
    setLoading(button, false);
  }
}

async function lookupWord(word) {
  switchTab("dictionary");
  $("#dictionaryEmpty").classList.add("hidden");
  const panel = $("#dictionaryContent");
  panel.classList.remove("hidden");
  panel.innerHTML = `<div class="loading"><span></span>正在查 ${escapeHtml(word)}…</div>`;
  try {
    const response = await apiFetch("/api/dictionary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ word })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "查詢失敗");
    state.dictionaryData = data;
    renderDictionary(data);
  } catch (error) {
    panel.innerHTML = `<div class="panel-empty"><div class="panel-icon">!</div><h3>查不到</h3><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function renderDictionary(data) {
  if (data.notFound) {
    $("#dictionaryContent").innerHTML = `<div class="panel-empty"><div class="panel-icon">?</div><h3>${escapeHtml(data.word)}</h3><p>免費英中字典沒有找到這個詞，可能是專有名詞或變化形。</p></div>`;
    return;
  }
  const saved = isSaved(data.word);
  const summary = (data.chineseSummary || []).length
    ? `<div class="chinese-summary"><div class="summary-label">繁體中文意思</div><div class="summary-words">${(data.chineseSummary || []).map(x => `<span>${escapeHtml(x)}</span>`).join("")}</div></div>`
    : `<div class="chinese-summary muted-summary"><div class="summary-label">中文意思</div><p>這個詞在免費字典裡暫時沒有中文對應，下面保留英文定義。</p></div>`;
  const meanings = (data.meanings || []).map(meaning => `
    <div class="meaning-block">
      <div class="part"><strong>${escapeHtml(meaning.partOfSpeechZh || meaning.partOfSpeech)}</strong><span>${escapeHtml(meaning.partOfSpeech || "")}</span></div>
      ${(meaning.definitions || []).map((d, i) => `
        <div class="definition">
          ${d.chinese?.length ? `<div class="zh-definition"><b>${i + 1}.</b> ${d.chinese.map(escapeHtml).join("、")}</div>` : ""}
          ${d.definition ? `<div class="en-definition">${d.chinese?.length ? "" : `<b>${i + 1}.</b> `}${escapeHtml(d.definition)}</div>` : ""}
          ${d.example ? `<div class="example"><span>例句</span> “${escapeHtml(d.example)}”</div>` : ""}
        </div>`).join("")}
    </div>`).join("");
  const source = data.aiSource
    ? `<div class="dict-source">${data.note ? escapeHtml(data.note) + "<br>" : ""}由 AI（Groq）即時解釋，僅供參考。</div>`
    : (data.sourceUrl
      ? `<div class="dict-source">資料來源：<a href="${escapeHtml(data.sourceUrl)}" target="_blank" rel="noopener">Wiktionary</a>，由 <a href="https://freedictionaryapi.com" target="_blank" rel="noopener">FreeDictionaryAPI.com</a> 提供</div>`
      : "");
  $("#dictionaryContent").innerHTML = `
    <div class="dict-head">
      <div><h3 class="dict-word">${escapeHtml(data.word)}</h3><div class="phonetic">${escapeHtml(data.phonetic || "")}</div></div>
      <div>
        <button class="icon-btn" style="position:static" id="playWordBtn" title="免費朗讀單字">▶</button>
        <button class="save-btn ${saved ? "saved" : ""}" id="saveWordBtn">${saved ? "已收藏" : "+ 加入單字本"}</button>
      </div>
    </div>
    ${summary}
    ${meanings || `<p class="panel-empty">沒有可顯示的定義。</p>`}
    ${source}`;
  $("#saveWordBtn").addEventListener("click", () => toggleSaveWord(data));
  $("#playWordBtn").addEventListener("click", () => speak(data.word));
}

function toggleSaveWord(data) {
  const index = state.vocabulary.findIndex(item => item.word.toLowerCase() === data.word.toLowerCase());
  if (index >= 0) {
    const [removed] = state.vocabulary.splice(index, 1);
    toast("已從單字本移除");
    remoteRemove(removed.word);
  } else {
    const firstMeaning = data.meanings?.[0];
    const firstEntry = firstMeaning?.definitions?.[0];
    const chineseDefinition = firstEntry?.chinese?.join("、") || data.chineseSummary?.join("、") || "";
    const item = {
      word: data.word,
      phonetic: data.phonetic || "",
      partOfSpeech: firstMeaning?.partOfSpeechZh || firstMeaning?.partOfSpeech || "",
      definition: chineseDefinition || firstEntry?.definition || "",
      englishDefinition: firstEntry?.definition || "",
      sentence: state.selectedSentence || "",
      createdAt: new Date().toISOString()
    };
    state.vocabulary.unshift(item);
    toast("已加入單字本");
    remoteUpsert(item);
  }
  saveVocabulary();
  renderDictionary(data);
}

async function analyzeSentence() {
  if (!state.selectedSentence) return toast("請先選擇句子");
  const button = $("#analyzeBtn");
  $("#analysisLoading").classList.remove("hidden");
  $("#analysisResult").innerHTML = "";
  setLoading(button, true, "解析中…");
  try {
    const response = await apiFetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sentence: state.selectedSentence,
        level: $("#levelSelect").value,
        targetLanguage: $("#languageSelect").value
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "解析失敗");
    renderAnalysis(data);
  } catch (error) {
    $("#analysisResult").innerHTML = `<div class="result-section"><div class="section-label">無法解析</div><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    $("#analysisLoading").classList.add("hidden");
    setLoading(button, false);
  }
}

function renderItems(items, titleKey, bodyKey) {
  if (!items?.length) return `<p>這句沒有特別需要補充的內容。</p>`;
  return `<div class="analysis-list">${items.map(item => `
    <div class="analysis-item"><strong>${escapeHtml(item[titleKey] || "")}</strong><span>${escapeHtml(item[bodyKey] || "")}${item.example ? `<br>例：${escapeHtml(item.example)}` : ""}</span></div>
  `).join("")}</div>`;
}

function renderAnalysis(data) {
  $("#analysisResult").innerHTML = `
    <section class="result-section"><div class="section-label">自然翻譯</div><p class="translation">${escapeHtml(data.translation || "")}</p></section>
    <section class="result-section"><div class="section-label">這句在說什麼</div><p>${escapeHtml(data.plainMeaning || "")}</p></section>
    <section class="result-section"><div class="section-label">句子結構</div><p>${escapeHtml(data.structure || "")}</p></section>
    <section class="result-section"><div class="section-label">文法與句型</div>${renderItems(data.grammar, "pattern", "explanation")}</section>
    <section class="result-section"><div class="section-label">慣用語與搭配</div>${renderItems(data.phrases, "phrase", "meaning")}</section>
    <section class="result-section"><div class="section-label">重點單字</div>${renderItems(data.keyWords, "word", "meaning")}</section>
    ${data.note ? `<section class="result-section"><div class="section-label">注意</div><p>${escapeHtml(data.note)}</p></section>` : ""}
  `;
}

function renderVocabulary() {
  const query = $("#vocabSearch")?.value.toLowerCase().trim() || "";
  const lvlFilter = $("#vocabLevelFilter")?.value || "";
  const items = state.vocabulary.filter(item => {
    const textOk = !query || item.word.toLowerCase().includes(query) || (item.definition || "").toLowerCase().includes(query);
    if (!textOk) return false;
    if (!lvlFilter) return true;
    const l = wordLevel(item.word);
    return lvlFilter === "none" ? !l : l === lvlFilter;
  });
  const list = $("#vocabList");
  if (!items.length) {
    list.innerHTML = `<div class="panel-empty"><div class="panel-icon">☆</div><h3>${query ? "找不到單字" : "單字本還是空的"}</h3><p>閱讀時點一下單字，再按「加入單字本」。</p></div>`;
    return;
  }
  list.innerHTML = items.map(item => `
    <div class="vocab-card">
      <div class="vocab-card-head"><h4>${escapeHtml(item.word)}${wordLevel(item.word) ? `<span class="lvl-badge" data-lvl="${wordLevel(item.word)}">${wordLevel(item.word)}</span>` : ""}</h4><button class="remove-btn" data-remove="${escapeHtml(item.word)}">移除</button></div>
      <div class="phonetic">${escapeHtml(item.phonetic || "")} ${item.partOfSpeech ? `· ${escapeHtml(item.partOfSpeech)}` : ""}</div>
      <p>${escapeHtml(item.definition || "")}</p>
      ${item.englishDefinition ? `<p class="vocab-english">${escapeHtml(item.englishDefinition)}</p>` : ""}
      ${item.sentence ? `<p><i>${escapeHtml(item.sentence)}</i></p>` : ""}
    </div>`).join("");
  $$('[data-remove]').forEach(button => button.addEventListener("click", () => {
    state.vocabulary = state.vocabulary.filter(item => item.word !== button.dataset.remove);
    remoteRemove(button.dataset.remove);
    saveVocabulary();
  }));
}

function exportCsv() {
  if (!state.vocabulary.length) return toast("單字本還是空的");
  const rows = [["word", "phonetic", "part_of_speech", "chinese_meaning", "english_definition", "example_sentence"], ...state.vocabulary.map(i => [i.word, i.phonetic, i.partOfSpeech, i.definition, i.englishDefinition || "", i.sentence])];
  const csv = rows.map(row => row.map(cell => `"${String(cell || "").replaceAll('"', '""')}"`).join(",")).join("\n");
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "lingoreader-vocabulary.csv";
  link.click();
  URL.revokeObjectURL(link.href);
}

function speak(text) {
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = .88;
  speechSynthesis.speak(utterance);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
}

async function checkStatus() {
  try {
    const data = await fetch("/api/status").then(r => r.json());
    const pill = $("#aiStatus");
    const lockLabel = data.accessProtected ? " · 已鎖定" : "";
    pill.textContent = (data.aiReady ? ((data.aiProvider || "AI") + " 解析可用") : "免費朗讀／字典可用") + lockLabel;
    pill.classList.remove("ready", "off");
    pill.classList.add(data.aiReady ? "ready" : "off");
    pill.title = data.aiReady ? "整句翻譯、文法與慣用語解析已啟用" : "朗讀與字典不需要 API Key；整句 AI 解析尚未啟用";
  } catch {}
}

async function remoteUpsert(item) {
  if (!SYNC.enabled) return;
  try {
    await apiFetch("/api/vocab", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(item)
    });
  } catch { toast("雲端同步失敗，已存在本機"); }
}

async function remoteRemove(word) {
  if (!SYNC.enabled) return;
  try {
    await apiFetch("/api/vocab?word=" + encodeURIComponent(word), { method: "DELETE" });
  } catch { toast("雲端移除失敗，已改本機"); }
}

async function initVocab() {
  try {
    const response = await apiFetch("/api/vocab");
    if (!response.ok) throw new Error("sync-off");
    const data = await response.json();
    SYNC.enabled = true;
    const remote = data.items || [];
    const remoteWords = new Set(remote.map(i => (i.word || "").toLowerCase()));
    const localOnly = state.vocabulary.filter(i => !remoteWords.has((i.word || "").toLowerCase()));
    if (localOnly.length) {
      try {
        await apiFetch("/api/vocab/bulk", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(localOnly)
        });
      } catch {}
    }
    state.vocabulary = [...remote, ...localOnly]
      .sort((a, b) => String(b.createdAt || "").localeCompare(String(a.createdAt || "")));
    localStorage.setItem("lingoreader-vocabulary", JSON.stringify(state.vocabulary));
  } catch {
    SYNC.enabled = false; // 離線或尚未設定雲端 → 只用本機
  }
  updateVocabCount();
  renderVocabulary();
  refreshSavedHighlights();
}

const ARTS = { list: [] };
function djb2(str) { let h = 5381; for (let i = 0; i < str.length; i++) { h = (((h << 5) + h) + str.charCodeAt(i)) & 0xffffffff; } return (h >>> 0).toString(36); }
function articleKey(a) {
  const url = a.url || "";
  if (url && url !== "pasted://article" && !/^https?:\/\/demo/.test(url)) return "u:" + url;
  return "p:" + djb2((a.title || "") + "|" + ((a.paragraphs && a.paragraphs[0]) || ""));
}
function articleHost(a) {
  try { return new URL(a.url).hostname.replace(/^www\./, ""); }
  catch { return (a.url === "pasted://article" || !a.url) ? "貼上的文章" : ""; }
}
async function remoteArticleSave(rec) {
  if (!SYNC.enabled) return;
  try { await apiFetch("/api/articles", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(rec) }); } catch {}
}
async function remoteArticleRemove(key) {
  if (!SYNC.enabled) return;
  try { await apiFetch("/api/articles?key=" + encodeURIComponent(key), { method: "DELETE" }); } catch {}
}
function saveArticleHistory(a) {
  if (!a || !a.paragraphs || !a.paragraphs.length) return;
  if (/^https?:\/\/demo/.test(a.url || "")) return;
  const realUrl = (a.url && a.url.indexOf("://") > 0 && a.url !== "pasted://article") ? a.url : "";
  const rec = { key: articleKey(a), title: a.title || "Untitled", url: realUrl, host: articleHost(a), paragraphs: a.paragraphs.slice(0, 200), createdAt: new Date().toISOString() };
  ARTS.list = [rec, ...ARTS.list.filter(x => x.key !== rec.key)].slice(0, 60);
  try { localStorage.setItem("lingoreader-articles", JSON.stringify(ARTS.list)); } catch {}
  renderRecentArticles();
  remoteArticleSave(rec);
}
async function loadArticles() {
  try { const c = localStorage.getItem("lingoreader-articles"); if (c) ARTS.list = JSON.parse(c) || []; } catch {}
  renderRecentArticles();
  try {
    const r = await apiFetch("/api/articles");
    if (r.ok) { const d = await r.json(); if (Array.isArray(d.items)) { ARTS.list = d.items; try { localStorage.setItem("lingoreader-articles", JSON.stringify(ARTS.list)); } catch {} renderRecentArticles(); } }
  } catch {}
}
function injectRecentArticles() {
  const card = document.querySelector(".import-card");
  if (card && !$("#recentArticles")) {
    const sec = document.createElement("section");
    sec.id = "recentArticles";
    sec.className = "recent-articles hidden";
    card.appendChild(sec);
  }
}
function renderRecentArticles() {
  const sec = $("#recentArticles");
  if (!sec) return;
  if (!ARTS.list.length) { sec.classList.add("hidden"); sec.innerHTML = ""; return; }
  sec.classList.remove("hidden");
  sec.innerHTML = `<div class="recent-head">最近文章</div>` + ARTS.list.slice(0, 10).map(a => `
    <div class="recent-item" data-open="${escapeHtml(a.key)}">
      <div class="recent-info"><span class="recent-title">${escapeHtml(a.title || "Untitled")}</span><span class="recent-meta">${escapeHtml(a.host || "")}</span></div>
      <button class="recent-remove" data-del="${escapeHtml(a.key)}" title="移除" aria-label="移除">×</button>
    </div>`).join("");
  sec.querySelectorAll("[data-open]").forEach(el => el.addEventListener("click", event => {
    if (event.target.closest("[data-del]")) return;
    const rec = ARTS.list.find(x => x.key === el.dataset.open);
    if (rec) renderArticle({ title: rec.title, author: "", date: "", url: rec.url || "pasted://article", paragraphs: rec.paragraphs || [] }, { fromHistory: true });
  }));
  sec.querySelectorAll("[data-del]").forEach(btn => btn.addEventListener("click", event => {
    event.stopPropagation();
    const key = btn.dataset.del;
    ARTS.list = ARTS.list.filter(x => x.key !== key);
    try { localStorage.setItem("lingoreader-articles", JSON.stringify(ARTS.list)); } catch {}
    renderRecentArticles();
    remoteArticleRemove(key);
  }));
}

$("#loadBtn").addEventListener("click", loadArticleFromUrl);
$("#urlInput").addEventListener("keydown", e => { if (e.key === "Enter") loadArticleFromUrl(); });
$("#pasteModeBtn").addEventListener("click", () => $("#pastePanel").classList.toggle("hidden"));
$("#useTextBtn").addEventListener("click", () => {
  const text = $("#manualText").value.trim();
  if (!text) return toast("請貼上文章文字");
  renderArticle({ title: $("#manualTitle").value.trim() || "Pasted article", author: "", date: "", url: "pasted://article", paragraphs: text.split(/\n\s*\n/).map(p => p.replace(/\s+/g, " ").trim()).filter(Boolean) });
});
$("#demoBtn").addEventListener("click", () => renderArticle(demoArticle));
$("#analyzeBtn").addEventListener("click", analyzeSentence);
$("#speakSentenceBtn").addEventListener("click", () => speak(state.selectedSentence));
$("#openVocabBtn").addEventListener("click", () => {
  switchTab("vocabulary");
  if (window.matchMedia("(max-width: 980px)").matches) {
    document.querySelector(".study-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});
$("#vocabSearch").addEventListener("input", renderVocabulary);
$("#exportBtn").addEventListener("click", exportCsv);
$$('.tab').forEach(tab => tab.addEventListener("click", () => switchTab(tab.dataset.tab)));

(function injectVocabFilter() {
  const tb = document.querySelector(".vocab-toolbar");
  if (tb && !$("#vocabLevelFilter")) {
    const sel = document.createElement("select");
    sel.id = "vocabLevelFilter";
    sel.title = "依 CEFR 等級篩選";
    sel.innerHTML = '<option value="">全部等級</option>' + ["A1","A2","B1","B2","C1","C2"].map(l => `<option value="${l}">${l}</option>`).join("") + '<option value="none">未分級</option>';
    tb.insertBefore(sel, $("#exportBtn"));
    sel.addEventListener("change", renderVocabulary);
  }
})();
$("#levelSelect")?.addEventListener("change", markAboveLevel);

initVocab();
checkStatus();
loadCefr().then(() => { if (state.article) markAboveLevel(); renderVocabulary(); if (state.article) showDifficulty(state.article); });
injectRecentArticles();
loadArticles();
