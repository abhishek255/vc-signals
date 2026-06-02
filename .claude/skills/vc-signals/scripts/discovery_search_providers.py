from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROVIDER_ENV_KEYS = {
    "brave": ("BRAVE_API_KEY",),
    "exa": ("EXA_API_KEY",),
    "you": ("YOU_API_KEY", "YDC_API_KEY"),
    "perplexity_search": ("PERPLEXITY_API_KEY",),
}
DEFAULT_PROVIDER_ENV_PATHS = (
    Path.home() / ".config" / "last30days" / ".env",
    Path.home() / ".config" / "vc-signals" / ".env",
)


def provider_available(provider: str, env: dict | None = None) -> bool:
    return bool(_provider_api_key(provider, env=env))


def load_provider_env_files(paths: list[Path | str] | None = None) -> dict[str, str]:
    loaded = {}
    for path in paths or list(DEFAULT_PROVIDER_ENV_PATHS):
        candidate = Path(path)
        if not candidate.exists():
            continue
        for line in candidate.read_text().splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and not os.environ.get(key):
                os.environ[key] = value
                loaded[key] = str(candidate)
    return loaded


def normalize_provider_response(
    *,
    provider: str,
    query: str,
    raw_items: list[dict],
    latency_ms: int,
    cost_usd: float,
    cache_status: str,
    capabilities: dict | None = None,
) -> dict:
    return {
        "provider": provider,
        "query": query,
        "items": [_normalize_item(provider, item) for item in raw_items or []],
        "skipped": False,
        "skip_reason": "",
        "cache_status": cache_status,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "capabilities": _provider_capabilities(provider, capabilities or {}),
    }


def run_provider_query(
    provider: str,
    query: dict,
    *,
    cache_dir: Path | str | None = None,
    max_results: int = 10,
    timeout_seconds: int = 20,
    http_get=None,
    http_post=None,
    env: dict | None = None,
) -> dict:
    topic = query.get("topic") or query.get("query") or ""
    cache_path = _cache_path(cache_dir, provider, topic, max_results) if cache_dir else None
    if cache_path and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            cached["cache_status"] = "hit"
            cached["skipped"] = False
            cached["skip_reason"] = ""
            return cached
        except json.JSONDecodeError:
            pass

    api_key = _provider_api_key(provider, env=env)
    if not api_key:
        return {
            "provider": provider,
            "query_id": query.get("query_id") or query.get("id") or "",
            "query": topic,
            "items": [],
            "skipped": True,
            "skip_reason": "missing_api_key",
            "cache_status": "skip",
            "latency_ms": 0,
            "cost_usd": 0.0,
            "capabilities": _provider_capabilities(provider, {}),
        }

    started = time.monotonic()
    raw_items = []
    cost_usd = 0.0
    capability_overrides = {}
    if provider == "brave":
        raw_items = _run_brave(topic, api_key, max_results, timeout_seconds, http_get)
    elif provider == "exa":
        payload = _run_exa(topic, api_key, max_results, timeout_seconds, http_post)
        raw_items = payload.get("results") or []
        cost_usd = _extract_total_cost(payload)
        capability_overrides = {
            "snippet_only": False,
            "page_content_returned": True,
            "livecrawl_available": True,
            "cost_estimated": True,
        }
    elif provider == "you":
        raw_items = _run_you(topic, api_key, max_results, timeout_seconds, http_get)
    elif provider == "perplexity_search":
        raw_items = _run_perplexity_search(topic, api_key, max_results, timeout_seconds, http_get)
    else:
        return {
            "provider": provider,
            "query_id": query.get("query_id") or query.get("id") or "",
            "query": topic,
            "items": [],
            "skipped": True,
            "skip_reason": "unsupported_provider",
            "cache_status": "skip",
            "latency_ms": 0,
            "cost_usd": 0.0,
            "capabilities": {},
        }

    result = normalize_provider_response(
        provider=provider,
        query=topic,
        raw_items=raw_items[:max_results],
        latency_ms=int((time.monotonic() - started) * 1000),
        cost_usd=cost_usd,
        cache_status="miss",
        capabilities=capability_overrides,
    )
    result["query_id"] = query.get("query_id") or query.get("id") or ""
    result["query_family"] = query.get("query_family", "")
    result["movement"] = query.get("movement", "")
    result["market_sector"] = query.get("market_sector", "")

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, indent=2))
    return result


def _run_brave(topic: str, api_key: str, max_results: int, timeout_seconds: int, http_get) -> list[dict]:
    payload = _http_get_json(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        params={"q": topic, "count": max_results},
        timeout_seconds=timeout_seconds,
        http_get=http_get,
    )
    return payload.get("web", {}).get("results") or payload.get("results") or []


def _run_exa(topic: str, api_key: str, max_results: int, timeout_seconds: int, http_post) -> dict:
    return _http_post_json(
        "https://api.exa.ai/search",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        payload={
            "query": topic,
            "type": "auto",
            "numResults": max_results,
            "contents": {"highlights": True},
        },
        timeout_seconds=timeout_seconds,
        http_post=http_post,
    )


def _run_you(topic: str, api_key: str, max_results: int, timeout_seconds: int, http_get) -> list[dict]:
    payload = _http_get_json(
        "https://ydc-index.io/v1/search",
        headers={"X-API-Key": api_key, "Accept": "application/json"},
        params={"query": topic, "count": max_results},
        timeout_seconds=timeout_seconds,
        http_get=http_get,
    )
    results = payload.get("results")
    if isinstance(results, dict):
        return results.get("web") or results.get("results") or []
    return results or payload.get("hits") or payload.get("data") or []


def _run_perplexity_search(topic: str, api_key: str, max_results: int, timeout_seconds: int, http_get) -> list[dict]:
    payload = _http_get_json(
        "https://api.perplexity.ai/search",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        params={"query": topic, "max_results": max_results},
        timeout_seconds=timeout_seconds,
        http_get=http_get,
    )
    # Deliberately ignore synthesized answer text. Only source-result objects are evidence.
    raw_results = payload.get("results") or payload.get("search_results") or payload.get("citations") or []
    if raw_results and isinstance(raw_results[0], str):
        return [{"title": "", "url": url, "snippet": ""} for url in raw_results[:max_results]]
    return raw_results


def _http_get_json(url: str, *, headers: dict, params: dict, timeout_seconds: int, http_get) -> dict:
    if http_get:
        return http_get(url, headers=headers, params=params, timeout_seconds=timeout_seconds)
    full_url = f"{url}?{urlencode(params)}"
    request = Request(full_url, headers=headers)
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


def _http_post_json(url: str, *, headers: dict, payload: dict, timeout_seconds: int, http_post) -> dict:
    if http_post:
        return http_post(url, headers=headers, payload=payload, timeout_seconds=timeout_seconds)
    request = Request(url, headers=headers, data=json.dumps(payload).encode("utf-8"), method="POST")
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


def _provider_api_key(provider: str, env: dict | None = None) -> str:
    lookup = env or os.environ
    for key in PROVIDER_ENV_KEYS.get(provider, ()):
        value = lookup.get(key)
        if value:
            return value
    return ""


def _provider_capabilities(provider: str, overrides: dict) -> dict:
    defaults = {
        "provider": provider,
        "snippet_only": True,
        "page_content_returned": False,
        "livecrawl_available": provider in {"exa", "you"},
        "cost_estimated": True,
    }
    defaults.update(overrides or {})
    return defaults


def _normalize_item(provider: str, item: dict) -> dict:
    url = item.get("url") or item.get("link") or item.get("href") or item.get("source_url") or ""
    title = item.get("title") or item.get("name") or ""
    snippet = (
        item.get("snippet")
        or item.get("description")
        or item.get("summary")
        or item.get("content")
        or _highlights_to_snippet(item.get("highlights"))
        or item.get("text")
        or ""
    )
    return {
        "provider": provider,
        "title": title,
        "url": url,
        "snippet": snippet,
        "description": snippet,
        "source": provider,
    }


def _highlights_to_snippet(highlights) -> str:
    if not highlights:
        return ""
    if isinstance(highlights, str):
        return highlights
    if not isinstance(highlights, list):
        return ""
    parts = []
    for item in highlights:
        if isinstance(item, str):
            parts.append(item.strip())
        elif isinstance(item, dict):
            value = item.get("text") or item.get("highlight") or item.get("content") or ""
            if value:
                parts.append(str(value).strip())
    return " ".join(part for part in parts if part)


def _extract_total_cost(payload: dict) -> float:
    cost = payload.get("costDollars") or {}
    try:
        return float(cost.get("total") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _cache_path(cache_dir: Path | str | None, provider: str, topic: str, max_results: int) -> Path | None:
    if not cache_dir:
        return None
    digest = hashlib.sha256(f"{provider}|{topic}|{max_results}".encode("utf-8")).hexdigest()[:24]
    return Path(cache_dir) / provider / f"{digest}.json"
