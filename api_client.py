"""Xiaotiangong Gemini gateway client.

This module deliberately has no Streamlit dependency so the API integration can
be tested without starting the UI.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional

from google import genai
from google.genai import types


StatusCallback = Optional[Callable[[str], None]]


@dataclass
class ApiResult:
    text: str = ""
    model: str = ""
    sources: List[dict] = field(default_factory=list)
    error: str = ""
    response: Any = None

    @property
    def ok(self) -> bool:
        return bool(self.text)


def _status(callback: StatusCallback, message: str) -> None:
    if callback:
        callback(message)


def _safe_error(exc: Exception, api_key: str) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    if api_key:
        message = message.replace(api_key, "***")
    return message[:800]


def _response_text(response: Any) -> str:
    try:
        if response.text:
            return response.text.strip()
    except Exception:
        pass

    chunks = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            value = getattr(part, "text", None)
            if value:
                chunks.append(value)
    return "".join(chunks).strip()


def extract_grounding_sources(response: Any) -> List[dict]:
    """Extract deduplicated web citations from a google-genai response."""
    sources = []
    seen = set()
    for candidate in getattr(response, "candidates", None) or []:
        metadata = getattr(candidate, "grounding_metadata", None)
        for chunk in getattr(metadata, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            uri = (getattr(web, "uri", None) or "").strip()
            title = (getattr(web, "title", None) or "来源").strip()
            if uri and uri not in seen:
                seen.add(uri)
                sources.append({"title": title, "url": uri})
    return sources


def _config(use_search: bool) -> types.GenerateContentConfig:
    kwargs = {"response_modalities": ["TEXT"]}
    if use_search:
        kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    return types.GenerateContentConfig(**kwargs)


def generate_text(
    *,
    api_key: str,
    base_url: str,
    api_version: str,
    models: Iterable[str],
    prompt: str,
    use_search: bool = False,
    on_status: StatusCallback = None,
) -> ApiResult:
    """Generate text with model fallback and optional search-tool fallback."""
    if not api_key:
        return ApiResult(error="API Key 未配置")

    model_names = []
    for model in models:
        name = (model or "").strip().removeprefix("models/")
        if name and name not in model_names:
            model_names.append(name)
    if not model_names:
        return ApiResult(error="未配置可用模型")

    http_options = types.HttpOptions(
        api_version=api_version.strip("/"),
        base_url=base_url.rstrip("/"),
        timeout=120_000,
        retry_options=types.HttpRetryOptions(
            attempts=3,
            initial_delay=1,
            max_delay=8,
            http_status_codes=[429, 500, 502, 503, 504],
        ),
    )

    errors = []
    client = genai.Client(api_key=api_key, http_options=http_options)
    try:
        for index, model in enumerate(model_names, start=1):
            attempts = [use_search, False] if use_search else [False]
            for search_enabled in attempts:
                mode = "联网检索" if search_enabled else "文本生成"
                _status(
                    on_status,
                    f"🔄 正在调用 \u0060{model}\u0060（{index}/{len(model_names)}，{mode}）...",
                )
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=_config(search_enabled),
                    )
                    text = _response_text(response)
                    if text:
                        return ApiResult(
                            text=text,
                            model=model,
                            sources=extract_grounding_sources(response),
                            response=response,
                        )
                    errors.append(f"{model} ({mode}): 返回了空内容")
                except Exception as exc:
                    detail = _safe_error(exc, api_key)
                    errors.append(f"{model} ({mode}): {detail}")
                    if search_enabled:
                        _status(on_status, "⚠️ 检索工具不可用，正在降级为纯文本模式...")
    finally:
        client.close()

    return ApiResult(error="；".join(errors[-4:]) or "API 调用失败")
