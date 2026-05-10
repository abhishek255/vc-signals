import json
from pathlib import Path

from discovery_search_providers import (
    normalize_provider_response,
    provider_available,
    run_provider_query,
)


def test_normalize_provider_response_tracks_capabilities():
    normalized = normalize_provider_response(
        provider="brave",
        query="AI agent security startup",
        raw_items=[
            {
                "title": "Example",
                "url": "https://example.com",
                "description": "Snippet",
            }
        ],
        latency_ms=12,
        cost_usd=0.001,
        cache_status="miss",
        capabilities={"snippet_only": True, "page_content_returned": False},
    )

    assert normalized["capabilities"]["snippet_only"] is True
    assert normalized["items"][0]["snippet"] == "Snippet"


def test_provider_available_false_when_env_missing(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)

    assert provider_available("brave") is False


def test_provider_available_accepts_you_api_key_or_ydc_api_key(monkeypatch):
    monkeypatch.delenv("YOU_API_KEY", raising=False)
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    assert provider_available("you") is False

    monkeypatch.setenv("YOU_API_KEY", "you-key")
    assert provider_available("you") is True

    monkeypatch.delenv("YOU_API_KEY", raising=False)
    monkeypatch.setenv("YDC_API_KEY", "ydc-key")
    assert provider_available("you") is True


def test_run_provider_query_records_unavailable_skip(monkeypatch, tmp_path):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)

    result = run_provider_query(
        "brave",
        {"query_id": "q1", "topic": "AI agent security startup"},
        cache_dir=tmp_path,
        max_results=3,
    )

    assert result["skipped"] is True
    assert result["skip_reason"] == "missing_api_key"


def test_cache_hit_avoids_live_client(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAVE_API_KEY", "brave-key")
    query = {"query_id": "q1", "topic": "AI agent security startup"}

    def fake_http_get(url, *, headers, params, timeout_seconds):
        return {
            "web": {
                "results": [
                    {
                        "title": "Agent Co",
                        "url": "https://agentco.ai",
                        "description": "Agent security startup",
                    }
                ]
            }
        }

    first = run_provider_query(
        "brave",
        query,
        cache_dir=tmp_path,
        max_results=3,
        http_get=fake_http_get,
    )
    assert first["cache_status"] == "miss"

    def should_not_call(*_args, **_kwargs):
        raise AssertionError("live client should not be called on cache hit")

    second = run_provider_query(
        "brave",
        query,
        cache_dir=tmp_path,
        max_results=3,
        http_get=should_not_call,
    )
    assert second["cache_status"] == "hit"
    assert second["items"][0]["url"] == "https://agentco.ai"


def test_brave_uses_subscription_token_header(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAVE_API_KEY", "brave-key")
    seen = {}

    def fake_http_get(url, *, headers, params, timeout_seconds):
        seen["url"] = url
        seen["headers"] = headers
        seen["params"] = params
        return {"web": {"results": []}}

    run_provider_query(
        "brave",
        {"query_id": "q1", "topic": "AI agent security startup"},
        cache_dir=tmp_path,
        http_get=fake_http_get,
    )

    assert seen["headers"]["X-Subscription-Token"] == "brave-key"
    assert seen["params"]["q"] == "AI agent security startup"


def test_you_uses_x_api_key_header(monkeypatch, tmp_path):
    monkeypatch.delenv("YOU_API_KEY", raising=False)
    monkeypatch.setenv("YDC_API_KEY", "you-key")
    seen = {}

    def fake_http_get(url, *, headers, params, timeout_seconds):
        seen["url"] = url
        seen["headers"] = headers
        seen["params"] = params
        return {
            "results": {
                "web": [
                    {
                        "title": "AgentCo",
                        "url": "https://agentco.ai",
                        "description": "AgentCo builds AI agent security.",
                    }
                ]
            }
        }

    result = run_provider_query(
        "you",
        {"query_id": "q1", "topic": "AI agent security startup"},
        cache_dir=tmp_path,
        max_results=3,
        http_get=fake_http_get,
    )

    assert seen["url"] == "https://ydc-index.io/v1/search"
    assert seen["headers"]["X-API-Key"] == "you-key"
    assert seen["params"]["query"] == "AI agent security startup"
    assert seen["params"]["count"] == 3
    assert result["items"][0]["url"] == "https://agentco.ai"


def test_perplexity_search_uses_raw_results_only(monkeypatch, tmp_path):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-key")

    def fake_http_get(url, *, headers, params, timeout_seconds):
        return {
            "answer": "The answer says ExampleCo is the best.",
            "results": [
                {
                    "title": "ExampleCo",
                    "url": "https://exampleco.ai",
                    "snippet": "ExampleCo builds agent tooling.",
                }
            ],
        }

    result = run_provider_query(
        "perplexity_search",
        {"query_id": "q1", "topic": "AI agent security startup"},
        cache_dir=tmp_path,
        http_get=fake_http_get,
    )

    assert len(result["items"]) == 1
    serialized = json.dumps(result)
    assert "best" not in serialized
