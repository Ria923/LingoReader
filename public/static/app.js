const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = {
  article: null,
  selectedSentence: "",
  selectedElement: null,
  dictionaryData: null,
  vocabulary: JSON.parse(localStorage.getItem("lingoreader-vocabulary") || "[]"),
};

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

function renderArticle(article) {
  state.article = article;
  $("#emptyState").classList.add("hidden");
  $("#articleView").classList.remove("hidden");
  $("#articleTitle").textContent = article.title || "Untitled article";
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
    $("#dictionaryContent").innerHTML = `<div class="panel-empty"><div class="panel-icon">?</div><h3>${escapeHtml(data.word)}</h3><p>免費字典沒有找到這個詞，可能是專有名詞或變化形。</p></div>`;
    return;
  }
  const saved = isSaved(data.word);
  const meanings = (data.meanings || []).map(meaning => `
    <div class="meaning-block">
      <div class="part">${escapeHtml(meaning.partOfSpeech)}</div>
      ${(meaning.definitions || []).map((d, i) => `
        <div class="definition"><b>${i + 1}.</b> ${escapeHtml(d.definition)}
          ${d.example ? `<div class="example">“${escapeHtml(d.example)}”</div>` : ""}
        </div>`).join("")}
    </div>`).join("");
  $("#dictionaryContent").innerHTML = `
    <div class="dict-head">
      <div><h3 class="dict-word">${escapeHtml(data.word)}</h3><div class="phonetic">${escapeHtml(data.phonetic || "")}</div></div>
      <div>
        <button class="icon-btn" style="position:static" id="playWordBtn" title="免費朗讀單字">▶</button>
        <button class="save-btn ${saved ? "saved" : ""}" id="saveWordBtn">${saved ? "已收藏" : "+ 加入單字本"}</button>
      </div>
    </div>
    ${meanings || `<p class="panel-empty">沒有可顯示的定義。</p>`}`;
  $("#saveWordBtn").addEventListener("click", () => toggleSaveWord(data));
  $("#playWordBtn").addEventListener("click", () => {
    if (data.audio) {
      const audio = new Audio(data.audio);
      audio.play().catch(() => speak(data.word));
    } else {
      speak(data.word);
    }
  });
}

function toggleSaveWord(data) {
  const index = state.vocabulary.findIndex(item => item.word.toLowerCase() === data.word.toLowerCase());
  if (index >= 0) {
    state.vocabulary.splice(index, 1);
    toast("已從單字本移除");
  } else {
    const firstMeaning = data.meanings?.[0];
    const firstDefinition = firstMeaning?.definitions?.[0]?.definition || "";
    state.vocabulary.unshift({
      word: data.word,
      phonetic: data.phonetic || "",
      partOfSpeech: firstMeaning?.partOfSpeech || "",
      definition: firstDefinition,
      sentence: state.selectedSentence || "",
      createdAt: new Date().toISOString()
    });
    toast("已加入單字本");
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
  const items = state.vocabulary.filter(item => !query || item.word.toLowerCase().includes(query) || item.definition.toLowerCase().includes(query));
  const list = $("#vocabList");
  if (!items.length) {
    list.innerHTML = `<div class="panel-empty"><div class="panel-icon">☆</div><h3>${query ? "找不到單字" : "單字本還是空的"}</h3><p>閱讀時點一下單字，再按「加入單字本」。</p></div>`;
    return;
  }
  list.innerHTML = items.map(item => `
    <div class="vocab-card">
      <div class="vocab-card-head"><h4>${escapeHtml(item.word)}</h4><button class="remove-btn" data-remove="${escapeHtml(item.word)}">移除</button></div>
      <div class="phonetic">${escapeHtml(item.phonetic || "")} ${item.partOfSpeech ? `· ${escapeHtml(item.partOfSpeech)}` : ""}</div>
      <p>${escapeHtml(item.definition || "")}</p>
      ${item.sentence ? `<p><i>${escapeHtml(item.sentence)}</i></p>` : ""}
    </div>`).join("");
  $$('[data-remove]').forEach(button => button.addEventListener("click", () => {
    state.vocabulary = state.vocabulary.filter(item => item.word !== button.dataset.remove);
    saveVocabulary();
  }));
}

function exportCsv() {
  if (!state.vocabulary.length) return toast("單字本還是空的");
  const rows = [["word", "phonetic", "part_of_speech", "definition", "example_sentence"], ...state.vocabulary.map(i => [i.word, i.phonetic, i.partOfSpeech, i.definition, i.sentence])];
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
    pill.textContent = (data.aiReady ? "Gemini 解析可用" : "免費朗讀／字典可用") + lockLabel;
    pill.classList.add(data.aiReady ? "ready" : "off");
    pill.title = data.aiReady ? "整句翻譯、文法與慣用語解析已啟用" : "朗讀與字典不需要 API Key；整句 AI 解析尚未啟用";
  } catch {}
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
$("#openVocabBtn").addEventListener("click", () => switchTab("vocabulary"));
$("#vocabSearch").addEventListener("input", renderVocabulary);
$("#exportBtn").addEventListener("click", exportCsv);
$$('.tab').forEach(tab => tab.addEventListener("click", () => switchTab(tab.dataset.tab)));

updateVocabCount();
renderVocabulary();
checkStatus();
