from __future__ import annotations

from pathlib import Path


def _clear_provider_env(monkeypatch):
    from source_access import PROVIDERS

    monkeypatch.setattr("source_access.VC_SIGNALS_CONFIG_PATH", Path("/tmp/vc-signals-test-missing.env"))
    for provider in PROVIDERS.values():
        for key in provider["keys"]:
            if key == "AUTH_TOKEN+CT0":
                monkeypatch.delenv("AUTH_TOKEN", raising=False)
                monkeypatch.delenv("CT0", raising=False)
            elif key == "TWITTER_AUTH_TOKEN+TWITTER_CT0":
                monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
                monkeypatch.delenv("TWITTER_CT0", raising=False)
            else:
                monkeypatch.delenv(key, raising=False)


def test_detect_enrichment_provider_access_reports_configured_and_missing_sources(tmp_path, monkeypatch):
    from source_access import detect_enrichment_provider_access

    _clear_provider_env(monkeypatch)
    report = detect_enrichment_provider_access(
        {"CRUNCHBASE_API_KEY": "cb-key", "CORESIGNAL_API_KEY": ""},
        config_path=tmp_path / "missing.env",
    )

    assert report["providers"]["Crunchbase"]["status"] == "configured"
    assert report["providers"]["Coresignal"]["status"] == "manual_mode"
    assert report["providers"]["Coresignal"]["direct_access_status"] == "missing"
    assert report["providers"]["Coresignal"]["manual_mode"] is True
    assert report["providers"]["PitchBook"]["status"] == "missing"
    assert "company_identity_funding_founders_headcount" in report["providers"]["Crunchbase"]["coverage"]
    assert report["summary"]["configured"] == ["Crunchbase"]


def test_detect_enrichment_provider_access_treats_manual_sources_as_non_blocking(tmp_path, monkeypatch):
    from source_access import detect_enrichment_provider_access

    _clear_provider_env(monkeypatch)
    report = detect_enrichment_provider_access(
        {"PRODUCT_HUNT_TOKEN": "ph-token"},
        config_path=tmp_path / "missing.env",
    )

    assert report["providers"]["Product Hunt API"]["status"] == "configured"
    assert report["summary"]["configured"] == ["Product Hunt API"]
    assert set(report["summary"]["manual_mode"]) == {"Crunchbase", "Coresignal", "LinkedIn"}
    assert "Crunchbase" not in report["summary"]["missing"]
    assert "Coresignal" not in report["summary"]["missing"]
    assert "LinkedIn" not in report["summary"]["missing"]
    assert "X" in report["summary"]["missing"]


def test_detect_enrichment_provider_access_reports_product_hunt_and_x_configured(tmp_path, monkeypatch):
    from source_access import detect_enrichment_provider_access

    _clear_provider_env(monkeypatch)
    report = detect_enrichment_provider_access(
        {"PRODUCT_HUNT_TOKEN": "ph-token", "XAI_API_KEY": "xai-key"},
        config_path=tmp_path / "missing.env",
    )

    assert report["providers"]["Product Hunt API"]["status"] == "configured"
    assert report["providers"]["X"]["status"] == "configured"
    assert report["summary"]["configured"] == ["Product Hunt API", "X"]
    assert "Product Hunt and X are configured" in report["summary"]["recommendation"]


def test_detect_enrichment_provider_access_accepts_twitter_cookie_alias_pair(tmp_path, monkeypatch):
    from source_access import detect_enrichment_provider_access

    _clear_provider_env(monkeypatch)
    report = detect_enrichment_provider_access(
        {"TWITTER_AUTH_TOKEN": "auth-cookie", "TWITTER_CT0": "csrf-cookie"},
        config_path=tmp_path / "missing.env",
    )

    assert report["providers"]["X"]["status"] == "configured"
    assert report["providers"]["X"]["configured_keys"] == ["TWITTER_AUTH_TOKEN+TWITTER_CT0"]


def test_detect_enrichment_provider_access_reads_attio_from_vc_signals_config(tmp_path, monkeypatch):
    import source_access

    _clear_provider_env(monkeypatch)
    vc_config = tmp_path / "vc-signals.env"
    vc_config.write_text("ATTIO_ACCESS_TOKEN=attio-token\n")
    monkeypatch.setattr(source_access, "VC_SIGNALS_CONFIG_PATH", vc_config)

    report = source_access.detect_enrichment_provider_access(config_path=tmp_path / "last30days.env")

    assert report["providers"]["Attio"]["status"] == "configured"
    assert report["providers"]["Attio"]["configured_keys"] == ["ATTIO_ACCESS_TOKEN"]
    assert "Attio" in report["summary"]["configured"]


def test_detect_enrichment_provider_access_keeps_non_empty_key_across_config_paths(tmp_path, monkeypatch):
    import source_access

    _clear_provider_env(monkeypatch)
    last30days_config = tmp_path / "last30days.env"
    vc_config = tmp_path / "vc-signals.env"
    last30days_config.write_text("ATTIO_ACCESS_TOKEN=attio-token\n")
    vc_config.write_text("ATTIO_ACCESS_TOKEN=\n")
    monkeypatch.setattr(source_access, "VC_SIGNALS_CONFIG_PATH", vc_config)

    report = source_access.detect_enrichment_provider_access(config_path=last30days_config)

    assert report["providers"]["Attio"]["status"] == "configured"
