from __future__ import annotations

import html
import hmac
import ipaddress
import json
import os
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from fastapi import FastAPI, Header, HTTPException, Request as FastAPIRequest
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
MAX_REMOTE_BYTES = 4_000_000

app = FastAPI(title="LingoReader", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=PUBLIC_DIR / "static"), name="static")


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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")


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

