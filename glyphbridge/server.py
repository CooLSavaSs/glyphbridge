"""REST API for Glyphbridge.

Run it with ``glyphbridge serve``. If an API key is configured (``--api-key`` or the
``GLYPHBRIDGE_API_KEY`` environment variable), every request except ``/v1/health``
must send ``Authorization: Bearer <key>`` (or ``X-API-Key: <key>``). Without a key
the server only listens on localhost by default, so nothing is exposed. Each client
may make ``GLYPHBRIDGE_RATE_LIMIT`` requests per minute (default 120; 0 = no limit).
"""

from __future__ import annotations

import hmac
import os
import time
import uuid
from typing import List, Optional, Union

import threading
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from . import __version__
from .engine import SUPPORTED_LANGUAGES, Engine, TranslationError, get_engine

MAX_TEXTS = 64
MAX_CHARS = 20_000


class TranslateRequest(BaseModel):
    text: Optional[str] = Field(None, description="A single text to translate.")
    texts: Optional[List[str]] = Field(None, description="Several texts to translate in one call.")
    source: str = Field("auto", description="Source language code, or 'auto'.")
    target: str = Field(..., description="Target language code, e.g. 'en'.")


class RateLimiter:
    """Sliding-window limit per client (API key if given, else IP address)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client: str) -> Optional[int]:
        """Return None if allowed, else the seconds to wait."""
        if self.per_minute <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            hits = self._hits[client]
            while hits and now - hits[0] >= 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return int(60 - (now - hits[0])) + 1
            hits.append(now)
        return None


def create_app(engine: Optional[Engine] = None, api_key: Optional[str] = None,
               rate_limit: Optional[int] = None) -> FastAPI:
    key = api_key if api_key is not None else os.environ.get("GLYPHBRIDGE_API_KEY") or None
    limiter = RateLimiter(rate_limit if rate_limit is not None
                          else int(os.environ.get("GLYPHBRIDGE_RATE_LIMIT", "120")))
    app = FastAPI(title="Glyphbridge", version=__version__, description="Free, offline translation API.")

    def engine_dep() -> Engine:
        return engine or get_engine()

    def auth(request: Request, authorization: Optional[str] = Header(None),
             x_api_key: Optional[str] = Header(None)) -> None:
        supplied = x_api_key
        if authorization and authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
        if key and (not supplied or not hmac.compare_digest(supplied, key)):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        client = request.client.host if request.client else "unknown"
        wait = limiter.check(client)
        if wait is not None:
            raise HTTPException(status_code=429, detail="Too many requests",
                                headers={"Retry-After": str(wait)})

    @app.get("/v1/health")
    def health():
        return {"status": "ok", "version": __version__, "auth": bool(key)}

    @app.get("/v1/languages", dependencies=[Depends(auth)])
    def languages():
        return {"languages": [{"code": c, "name": n} for c, n in SUPPORTED_LANGUAGES.items()]}

    @app.post("/v1/translate", dependencies=[Depends(auth)])
    def translate(req: TranslateRequest, eng: Engine = Depends(engine_dep)):
        texts = req.texts if req.texts is not None else ([req.text] if req.text is not None else [])
        if not texts:
            raise HTTPException(status_code=422, detail="Send 'text' or 'texts'")
        if len(texts) > MAX_TEXTS or sum(len(t) for t in texts) > MAX_CHARS:
            raise HTTPException(status_code=413, detail=f"At most {MAX_TEXTS} texts and {MAX_CHARS} characters")
        try:
            results = eng.translate_batch(texts, target=req.target, source=req.source)
        except TranslationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if req.texts is None:
            return results[0].to_dict()
        return {"results": [r.to_dict() for r in results]}

    # -- OpenAI-compatible endpoint ---------------------------------------
    # Lets tools that speak the OpenAI Chat Completions API use Glyphbridge with no
    # code changes: set base_url to http://host:8080/v1 and model to
    # "glyphbridge-<target>" (e.g. "glyphbridge-en"). The last user message is
    # translated; the reply is the translation.

    @app.get("/v1/models", dependencies=[Depends(auth)])
    def models():
        return {"object": "list", "data": [
            {"id": f"glyphbridge-{code}", "object": "model", "owned_by": "glyphbridge"}
            for code in SUPPORTED_LANGUAGES]}

    @app.post("/v1/chat/completions", dependencies=[Depends(auth)])
    def chat_completions(req: ChatRequest, eng: Engine = Depends(engine_dep)):
        if not req.model.startswith("glyphbridge-"):
            raise HTTPException(status_code=400, detail="model must be 'glyphbridge-<target language>'")
        target = req.model[len("glyphbridge-"):]
        user = [m for m in req.messages if m.role == "user"]
        if not user or not _content_text(user[-1].content).strip():
            raise HTTPException(status_code=422, detail="Send at least one user message with text")
        text = _content_text(user[-1].content)
        if len(text) > MAX_CHARS:
            raise HTTPException(status_code=413, detail=f"At most {MAX_CHARS} characters")
        try:
            r = eng.translate(text, target=target, source=req.source or "auto")
        except TranslationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": r.translation}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "glyphbridge": r.to_dict(),
        }

    return app


class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[dict]]


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    source: Optional[str] = Field(None, description="Glyphbridge extension: source language code.")


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
