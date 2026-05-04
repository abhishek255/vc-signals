from __future__ import annotations


def test_classify_agent_security_repo_as_cybersecurity_high():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="AgentShield",
        text="AI agent security scanner for MCP server permissions and tool risk.",
        source_lane="OSS",
    )

    assert result.market_sector == "Cybersecurity"
    assert result.sector_confidence == "High"
    assert "security" in result.sector_reason.lower()


def test_pentest_cli_with_api_testing_terms_classifies_as_cybersecurity():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="watchtower",
        text="CLI for penetration testing API security checks, vulnerability scanning, and automated testing pipelines.",
        source_lane="OSS",
    )

    assert result.market_sector == "Cybersecurity"
    assert result.sector_confidence == "High"
    assert "penetration testing" in result.sector_reason.lower()


def test_guardian_cli_mcp_permissions_classifies_as_cybersecurity():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="guardian-cli",
        text="Developer CLI that audits MCP permissions, secrets exposure, auth flows, and prompt injection risk.",
        source_lane="OSS",
    )

    assert result.market_sector == "Cybersecurity"
    assert result.sector_confidence == "High"
    assert "mcp permissions" in result.sector_reason.lower()


def test_praetorian_style_red_team_api_security_classifies_as_cybersecurity():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="praetorian-inc/hadrian",
        text="API security testing platform for red team workflows, threat discovery, and vulnerability validation.",
        source_lane="OSS",
    )

    assert result.market_sector == "Cybersecurity"
    assert result.sector_confidence == "High"
    assert "api security" in result.sector_reason.lower()


def test_classify_github_actions_repo_as_devtools():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="ActionPilot",
        text="GitHub Actions workflow that debugs CI pipeline failures for pull requests.",
        source_lane="OSS",
    )

    assert result.market_sector == "Devtools"
    assert result.sector_confidence in {"High", "Medium"}


def test_classify_data_lineage_signal_as_data_infra():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="Data lineage for modern warehouses",
        text="Teams need metadata catalog and data pipeline governance.",
    )

    assert result.market_sector == "Data Infra"


def test_weak_helper_script_is_unclassified_low():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="tiny helper script",
        text="A small utility for formatting text files.",
    )

    assert result.market_sector == "Unclassified"
    assert result.sector_confidence == "Low"


def test_embedded_short_keywords_do_not_match_inside_words():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="facial placid social bragging",
        text="Magic carpet clips from a rapid prototype with no product evidence.",
    )

    assert result.market_sector == "Unclassified"
    assert result.sector_confidence == "Low"


def test_short_keywords_still_match_as_tokens():
    from radar_sector_classifier import classify_market_sector

    result = classify_market_sector(
        title="CI helper",
        text="CLI for CI/CD pipeline debugging.",
    )

    assert result.market_sector == "Devtools"
    assert result.sector_confidence == "High"
