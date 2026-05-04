"""Tests for the Attio read-only integration."""

from __future__ import annotations

import json


def test_check_config_reads_token_from_env(monkeypatch):
    from attio import check_config

    monkeypatch.setenv("ATTIO_ACCESS_TOKEN", "token")

    result = check_config()
    assert result == {
        "configured": True,
        "base_url": "https://api.attio.com/v2",
        "token_source": "ATTIO_ACCESS_TOKEN",
    }


def test_check_config_reads_token_from_vc_signals_env_file(tmp_path, monkeypatch):
    from attio import check_config

    env_path = tmp_path / ".env"
    env_path.write_text("ATTIO_ACCESS_TOKEN=file-token\n")
    monkeypatch.delenv("ATTIO_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr("attio.DEFAULT_CONFIG_PATH", env_path)

    result = check_config()
    assert result == {
        "configured": True,
        "base_url": "https://api.attio.com/v2",
        "token_source": str(env_path),
    }


def test_check_config_missing_token(monkeypatch):
    from attio import check_config

    monkeypatch.delenv("ATTIO_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr("attio.DEFAULT_CONFIG_PATH", None)

    result = check_config()
    assert result["configured"] is False
    assert "ATTIO_ACCESS_TOKEN" in result["error"]


def test_parse_objects_and_lists():
    from attio import parse_lists, parse_objects

    objects = parse_objects({
        "data": [
            {"api_slug": "companies", "singular_noun": "Company", "plural_noun": "Companies"},
            {"api_slug": "people", "singular_noun": "Person", "plural_noun": "People"},
        ]
    })
    lists = parse_lists({
        "data": [
            {"api_slug": "pipeline_2", "name": "Tier 1 Investors Deal Activity MASTER", "parent_object": ["companies"]},
            {"api_slug": "individual_investors", "name": "Individual Investors", "parent_object": ["people"]},
        ]
    })

    assert objects[0]["api_slug"] == "companies"
    assert lists == [
        {
            "api_slug": "pipeline_2",
            "name": "Tier 1 Investors Deal Activity MASTER",
            "parent_object": ["companies"],
        }
    ]


def test_classify_no_match():
    from attio import classify_match

    result = classify_match([])
    assert result["attio_status"] == "no_match"
    assert result["attio_action"] == "assign owner"


def test_classify_active_pipeline_match():
    from attio import classify_match

    result = classify_match([
        {"list_api_slug": "pipeline_2", "list_name": "Tier 1 Investors Deal Activity MASTER"}
    ], attributes={"mmp_owner": [{"value": "Michael"}]})
    assert result["attio_status"] == "active"
    assert result["attio_action"] == "monitor only"
    assert result["attio_lists"] == ["Tier 1 Investors Deal Activity MASTER"]


def test_classify_active_pipeline_without_owner():
    from attio import classify_match

    result = classify_match([
        {"list_api_slug": "pipeline_2", "list_name": "Tier 1 Investors Deal Activity MASTER"}
    ], attributes={"mmp_owner": []})
    assert result["attio_status"] == "no_owner"
    assert result["attio_action"] == "assign owner"


def test_classify_old_pipeline_as_stale():
    from attio import classify_match

    result = classify_match([{"list_api_slug": "pipeline", "list_name": "Z_Pipeline_OLD"}])
    assert result["attio_status"] == "stale"
    assert result["attio_action"] == "refresh note"


def test_classify_passed_list_flags_quietly():
    from attio import classify_match

    result = classify_match([{"list_api_slug": "passed", "list_name": "Passed Companies"}])
    assert result["attio_status"] == "passed"
    assert result["attio_action"] == "flag quietly"


def test_classify_deprioritized_status_flags_quietly():
    from attio import classify_match

    result = classify_match(
        [{"list_api_slug": "pipeline_2", "list_name": "Tier 1 Investors Deal Activity MASTER"}],
        attributes={"status_8": [{"status": {"title": "Deprioritized"}}]},
    )
    assert result["attio_status"] == "passed"
    assert result["attio_action"] == "flag quietly"


def test_match_company_uses_domain_before_name(monkeypatch):
    from attio import AttioClient

    calls = []

    def fake_request(method, path, payload=None):
        calls.append((method, path, payload))
        if path == "/objects/records/search":
            return {
                "data": [
                    {
                        "id": {"record_id": "rec_1"},
                        "record_text": "Cursor",
                        "object_slug": "companies",
                    }
                ]
            }
        if path == "/objects/companies/records/rec_1/entries":
            return {"data": [{"list_api_slug": "pipeline_2", "created_at": "2026-01-01T00:00:00Z"}]}
        if path == "/objects/companies/records/rec_1/attributes/domains/values":
            return {"data": [{"domain": "cursor.com", "root_domain": "cursor.com"}]}
        if "/attributes/" in path:
            return {"data": []}
        if path == "/lists":
            return {
                "data": [
                    {
                        "api_slug": "pipeline_2",
                        "name": "Tier 1 Investors Deal Activity MASTER",
                        "parent_object": ["companies"],
                    }
                ]
            }
        raise AssertionError(path)

    client = AttioClient("token", request_fn=fake_request)
    result = client.match_company({"name": "Anysphere", "domain": "cursor.com"})

    assert calls[0][2]["query"] == "cursor.com"
    assert result["attio_status"] == "no_owner"
    assert result["attio_match"]["record_text"] == "Cursor"


def test_match_company_rejects_fuzzy_domain_mismatch(monkeypatch):
    from attio import AttioClient

    def fake_request(method, path, payload=None):
        if path == "/objects/records/search":
            return {
                "data": [
                    {
                        "id": {"record_id": "rec_1"},
                        "record_text": "PILLARZ",
                        "object_slug": "companies",
                    }
                ]
            }
        if path == "/objects/companies/records/rec_1/attributes/domains/values":
            return {"data": [{"domain": "pillarzllc.com", "root_domain": "pillarzllc.com"}]}
        raise AssertionError(path)

    client = AttioClient("token", request_fn=fake_request)
    result = client.match_company({"name": "Pillar", "domain": "pillarhq.com"})
    assert result["attio_status"] == "no_match"
    assert "attio_match" not in result


def test_enrich_companies_preserves_original_fields():
    from attio import AttioClient, enrich_companies

    def fake_request(method, path, payload=None):
        if path == "/objects/records/search":
            return {"data": []}
        raise AssertionError(path)

    client = AttioClient("token", request_fn=fake_request)
    companies = [{"name": "NewCo", "domain": "newco.ai", "why_on_radar": "fresh signal"}]

    result = enrich_companies(companies, client)
    assert result[0]["why_on_radar"] == "fresh signal"
    assert result[0]["attio_status"] == "no_match"
    assert result[0]["attio_action"] == "assign owner"


def test_cli_enrich_reads_companies_json(monkeypatch, capsys):
    import attio

    monkeypatch.setenv("ATTIO_ACCESS_TOKEN", "token")
    monkeypatch.setattr("sys.argv", ["attio.py", "enrich"])
    monkeypatch.setattr("sys.stdin", type("Stdin", (), {"read": lambda self: json.dumps({"companies": [{"name": "NewCo"}]})})())

    class FakeClient:
        def match_company(self, company):
            return {"attio_status": "no_match", "attio_action": "assign owner"}

    monkeypatch.setattr(attio, "AttioClient", lambda token: FakeClient())

    attio._cli_main()
    out = json.loads(capsys.readouterr().out)
    assert out["companies"][0]["attio_status"] == "no_match"
