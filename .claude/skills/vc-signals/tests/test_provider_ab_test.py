import json


def test_provider_ab_test_dry_run_estimates_without_live_calls(tmp_path):
    from provider_ab_test import build_provider_ab_test_plan

    plan = build_provider_ab_test_plan(
        queries=["AI agent security startup", "Product Hunt devtools launch"],
        providers=["brave", "exa", "serper", "dataforseo"],
        max_results=5,
    )

    assert plan["live"] is False
    assert plan["query_count"] == 2
    assert plan["provider_count"] == 4
    assert len(plan["planned_searches"]) == 8
    assert plan["provider_estimates"]["brave"]["estimated_cost_usd"] > plan["provider_estimates"]["serper"]["estimated_cost_usd"]


def test_provider_ab_test_live_uses_guarded_provider_queries(tmp_path, monkeypatch):
    import provider_ab_test

    calls = []
    env_loaded = []

    def fake_run_provider_query(provider, query, **kwargs):
        calls.append((provider, query, kwargs))
        return {
            "provider": provider,
            "query": query["topic"],
            "items": [{"title": f"{provider} result", "url": f"https://{provider}.example"}],
            "skipped": False,
            "skip_reason": "",
            "cache_status": "miss",
            "cost_usd": 0.001,
        }

    monkeypatch.setattr(provider_ab_test, "run_provider_query", fake_run_provider_query)
    monkeypatch.setattr(provider_ab_test, "load_provider_env_files", lambda: env_loaded.append(True))

    result = provider_ab_test.run_provider_ab_test(
        queries=["AI agent security startup"],
        providers=["brave", "serper"],
        live=True,
        cache_dir=tmp_path / "cache",
        ledger_path=tmp_path / "ledger.jsonl",
        max_usd=1.0,
    )

    assert env_loaded == [True]
    assert len(calls) == 2
    assert result["live"] is True
    assert result["results"][0]["items"][0]["url"] == "https://brave.example"
    assert result["paid_search"]["enabled"] is True
    assert result["paid_search"]["live_calls"] == 0


def test_provider_ab_test_cli_dry_run_outputs_json(tmp_path, monkeypatch, capsys):
    import provider_ab_test

    queries_file = tmp_path / "queries.json"
    queries_file.write_text(json.dumps(["AI agent security startup"]))

    monkeypatch.setattr(
        "sys.argv",
        [
            "provider_ab_test.py",
            "--queries-file",
            str(queries_file),
            "--providers",
            "brave,serper",
        ],
    )

    provider_ab_test.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["live"] is False
    assert payload["query_count"] == 1
    assert set(payload["provider_estimates"]) == {"brave", "serper"}
