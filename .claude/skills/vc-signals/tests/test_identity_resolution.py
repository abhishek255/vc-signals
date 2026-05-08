import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from radar_models import Candidate


def _candidate(**overrides):
    payload = {
        "name": "Burrow",
        "sector": "Cybersecurity",
        "theme": "AI agent security",
        "source": "https://news.ycombinator.com/item?id=47761957",
        "candidate_type": "company_web",
        "stable_key": "hn:47761957",
        "domain": "",
        "why_on_radar": "Show HN: Burrow - Runtime Security for AI Agents",
        "sources": ["https://news.ycombinator.com/item?id=47761957"],
        "attio_status": "no_match",
        "evidence_confidence_score": 30,
    }
    payload.update(overrides)
    return Candidate(**payload)


def test_launch_style_missing_domain_stays_research_deeper(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    def fake_fetch(url, cache=None, timeout_seconds=8):
        raise TimeoutError("network timeout")

    monkeypatch.setattr("identity_resolution.fetch_existing_url", fake_fetch)

    result = resolve_candidate_identity(_candidate(), hn_cache={})

    assert result.original_name == "Burrow"
    assert result.identity_type == "launch_style_needs_identity"
    assert result.verified_domain == ""
    assert result.identity_confidence == "Low"
    assert result.recommended_identity_action == "Research deeper"
    assert "no verified domain" in result.missing_identity_evidence
    assert "no founder or maintainer identity" in result.missing_identity_evidence
    assert result.attio_safe_to_match is False


def test_launch_style_with_domain_and_founder_can_assign_owner():
    from identity_resolution import resolve_candidate_identity

    result = resolve_candidate_identity(
        _candidate(
            domain="burrow.security",
            founders=["Jane Founder"],
            founder_profiles=[{"name": "Jane Founder", "source": "launch page"}],
        ),
        hn_cache={},
    )

    assert result.identity_type == "verified_company"
    assert result.verified_domain == "burrow.security"
    assert result.identity_confidence_score >= 70
    assert result.commercial_intent_score >= 50
    assert result.attio_safe_to_match is True
    assert "burrow.security" in result.attio_match_keys
    assert result.recommended_identity_action == "Assign owner"


def test_parse_hn_item_extracts_title_and_outbound_url():
    from identity_resolution import parse_hn_item

    html = """
    <html>
      <tr class="athing" id="47761957">
        <span class="titleline">
          <a href="https://burrow.security">Show HN: Burrow - Runtime Security for AI Agents</a>
        </span>
      </tr>
    </html>
    """

    result = parse_hn_item(html)

    assert result["title"] == "Show HN: Burrow - Runtime Security for AI Agents"
    assert result["outbound_url"] == "https://burrow.security"


def test_hn_item_with_outbound_url_improves_identity_domain(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    html = """
    <html>
      <span class="titleline">
        <a href="https://burrow.security">Show HN: Burrow - Runtime Security for AI Agents</a>
      </span>
    </html>
    """

    def fake_fetch(url, cache=None, timeout_seconds=8):
        return html

    monkeypatch.setattr("identity_resolution.fetch_existing_url", fake_fetch)

    result = resolve_candidate_identity(_candidate(), hn_cache={})

    assert result.verified_domain == "burrow.security"
    assert result.domain_confidence == "High"
    assert "hn_enrichment_outbound_url" in result.verified_domain_basis
    assert "https://burrow.security" in result.source_outbound_urls
    assert result.identity_confidence_score >= 55


def test_hn_algolia_outbound_url_improves_identity_domain(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    def fake_algolia(item_id, cache=None, timeout_seconds=8):
        assert item_id == "47761957"
        return {
            "title": "Show HN: Burrow - Runtime Security for AI Agents",
            "url": "https://burrow.security",
            "author": "saranshrana",
            "points": 3,
            "num_comments": 0,
        }

    def fail_page_fetch(url, cache=None, timeout_seconds=8):
        raise AssertionError("page fallback should not run after Algolia success")

    monkeypatch.setattr("identity_resolution.fetch_hn_algolia_item", fake_algolia)
    monkeypatch.setattr("identity_resolution.fetch_existing_url", fail_page_fetch)

    result = resolve_candidate_identity(_candidate(), hn_cache={})

    assert result.verified_domain == "burrow.security"
    assert result.domain_confidence == "High"
    assert "hn_enrichment_outbound_url" in result.verified_domain_basis
    assert "hn_algolia" in result.resolved_from
    assert result.recommended_identity_action == "Assign owner"


def test_hn_cache_hit_avoids_live_fetch(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    def fail_algolia(item_id, cache=None, timeout_seconds=8):
        raise AssertionError("Algolia should not run on cache hit")

    def fail_fetch(url, cache=None, timeout_seconds=8):
        raise AssertionError("page fetch should not run on cache hit")

    monkeypatch.setattr("identity_resolution.fetch_hn_algolia_item", fail_algolia)
    monkeypatch.setattr("identity_resolution.fetch_existing_url", fail_fetch)

    result = resolve_candidate_identity(
        _candidate(),
        hn_cache={
            "47761957": {
                "title": "Show HN: Burrow - Runtime Security for AI Agents",
                "outbound_url": "https://burrow.security",
                "domain": "burrow.security",
                "resolved_from": "hn_algolia",
            }
        },
    )

    assert result.verified_domain == "burrow.security"
    assert result.fetch_warnings == []


def test_hn_internal_or_blocked_outbound_url_is_not_verified(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    def fake_algolia(item_id, cache=None, timeout_seconds=8):
        return {
            "title": "Show HN: Burrow - Runtime Security for AI Agents",
            "url": "https://github.com/example/burrow",
        }

    def fake_fetch(url, cache=None, timeout_seconds=8):
        return """
        <html>
          <span class="titleline">
            <a href="https://news.ycombinator.com/item?id=123">Internal</a>
          </span>
        </html>
        """

    monkeypatch.setattr("identity_resolution.fetch_hn_algolia_item", fake_algolia)
    monkeypatch.setattr("identity_resolution.fetch_existing_url", fake_fetch)

    result = resolve_candidate_identity(_candidate(), hn_cache={})

    assert result.verified_domain == ""
    assert result.recommended_identity_action == "Research deeper"
    assert any("hn_internal_url_only" in warning for warning in result.fetch_warnings)


def test_stored_hn_outbound_url_resolves_without_live_fetch(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    def fail_fetch(url, cache=None, timeout_seconds=8):
        raise AssertionError("stored metadata should avoid live HN fetch")

    monkeypatch.setattr("identity_resolution.fetch_existing_url", fail_fetch)

    result = resolve_candidate_identity(
        _candidate(
            evidence_metadata=[
                {
                    "source": "hackernews",
                    "source_url": "https://news.ycombinator.com/item?id=47761957",
                    "title": "Show HN: Burrow - Runtime Security for AI Agents",
                    "outbound_url": "https://burrow.security",
                    "domain": "burrow.security",
                }
            ]
        ),
        hn_cache={},
    )

    assert result.verified_domain == "burrow.security"
    assert result.domain_confidence == "High"
    assert "hn_outbound_url_metadata" in result.verified_domain_basis
    assert "metadata" in result.resolved_from
    assert result.fetch_warnings == []


def test_hn_fetch_failure_keeps_launch_style_needs_identity(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    def fake_fetch(url, cache=None, timeout_seconds=8):
        raise TimeoutError("network timeout")

    monkeypatch.setattr("identity_resolution.fetch_existing_url", fake_fetch)

    result = resolve_candidate_identity(_candidate())

    assert result.identity_type == "launch_style_needs_identity"
    assert result.verified_domain == ""
    assert result.recommended_identity_action == "Research deeper"
    assert result.fetch_warnings


def test_hn_429_with_no_stored_outbound_url_remains_research_deeper(monkeypatch):
    from identity_resolution import resolve_candidate_identity

    from urllib.error import HTTPError

    def fake_algolia(item_id, cache=None, timeout_seconds=8):
        raise HTTPError("https://hn.algolia.com/api/v1/items/47761957", 429, "Too Many Requests", hdrs=None, fp=None)

    def fake_fetch(url, cache=None, timeout_seconds=8):
        raise HTTPError(url, 429, "Too Many Requests", hdrs=None, fp=None)

    monkeypatch.setattr("identity_resolution.fetch_hn_algolia_item", fake_algolia)
    monkeypatch.setattr("identity_resolution.fetch_existing_url", fake_fetch)

    result = resolve_candidate_identity(
        _candidate(
            evidence_metadata=[
                {
                    "source": "hackernews",
                    "source_url": "https://news.ycombinator.com/item?id=47761957",
                    "title": "Show HN: Burrow - Runtime Security for AI Agents",
                }
            ]
        ),
        hn_cache={},
    )

    assert result.verified_domain == ""
    assert result.recommended_identity_action == "Research deeper"
    assert any("hn_fetch_429" in warning for warning in result.fetch_warnings)


def test_github_only_row_extracts_project_but_not_company_domain():
    from identity_resolution import parse_github_url, resolve_candidate_identity

    parsed = parse_github_url("https://github.com/slowql/slowql")
    assert parsed["owner"] == "slowql"
    assert parsed["repo"] == "slowql"
    assert parsed["project_url"] == "https://github.com/slowql/slowql"

    result = resolve_candidate_identity(
        _candidate(
            name="slowql/slowql",
            stable_key="repo:slowql",
            candidate_type="oss_project",
            source="https://github.com/slowql/slowql",
            sources=["https://github.com/slowql/slowql"],
            domain="",
            attio_status="unknown",
        )
    )

    assert result.project_url == "https://github.com/slowql/slowql"
    assert result.verified_domain == ""
    assert result.attio_safe_to_match is False
    assert "github_project_identity" in result.identity_confidence_basis


def test_github_metadata_produces_project_identity_not_company_domain():
    from identity_resolution import resolve_candidate_identity

    result = resolve_candidate_identity(
        _candidate(
            name="slowql/slowql",
            stable_key="repo:slowql",
            candidate_type="oss_project",
            source="https://github.com/slowql/slowql",
            sources=["https://github.com/slowql/slowql"],
            attio_status="unknown",
            evidence_metadata=[
                {
                    "source": "github",
                    "source_url": "https://github.com/slowql/slowql",
                    "owner_name": "slowql",
                    "owner_type": "Organization",
                    "topics": ["sql", "security", "compliance"],
                    "description": "SQL static analyzer for performance and compliance",
                }
            ],
        )
    )

    assert result.project_url == "https://github.com/slowql/slowql"
    assert result.maintainers == ["slowql"]
    assert result.verified_domain == ""
    assert "github_project_identity" in result.identity_confidence_basis
    assert "github_owner_metadata" in result.identity_confidence_basis


def test_github_homepage_is_domain_candidate_not_owner_ready_by_itself():
    from identity_resolution import resolve_candidate_identity

    result = resolve_candidate_identity(
        _candidate(
            name="slowql/slowql",
            stable_key="repo:slowql",
            candidate_type="oss_project",
            source="https://github.com/slowql/slowql",
            sources=["https://github.com/slowql/slowql"],
            attio_status="no_match",
            evidence_metadata=[
                {
                    "source": "github",
                    "source_url": "https://github.com/slowql/slowql",
                    "owner_name": "slowql",
                    "owner_type": "Organization",
                    "homepage": "https://slowql.dev",
                    "description": "SQL static analyzer for performance and compliance",
                }
            ],
        )
    )

    assert result.verified_domain == "slowql.dev"
    assert result.domain_confidence == "Medium"
    assert "github_homepage_verified_project_site" in result.verified_domain_basis
    assert result.identity_type != "verified_company"
    assert result.recommended_identity_action != "Assign owner"


def test_github_homepage_domain_mismatch_is_not_verified_or_owner_ready():
    from identity_resolution import resolve_candidate_identity

    result = resolve_candidate_identity(
        _candidate(
            name="affaan-m/agentshield",
            stable_key="repo:agentshield",
            candidate_type="oss_project",
            source="https://github.com/affaan-m/agentshield",
            sources=["https://github.com/affaan-m/agentshield"],
            attio_status="no_match",
            why_on_radar="AI agent security scanner with MCP permissions focus.",
            evidence_metadata=[
                {
                    "source": "github",
                    "source_url": "https://github.com/affaan-m/agentshield",
                    "owner_name": "affaan-m",
                    "owner_type": "User",
                    "homepage": "https://cerebralvalley.ai",
                    "description": "AI agent security scanner",
                }
            ],
        )
    )

    assert result.verified_domain == ""
    assert result.identity_type in {"oss_project_watch", "oss_with_commercial_intent"}
    assert result.attio_safe_to_match is False
    assert "github_homepage_present" in result.identity_confidence_basis
    assert "github_homepage_domain_mismatch" in result.identity_confidence_basis
    assert result.recommended_identity_action != "Assign owner"


def test_verified_discovery_does_not_turn_github_only_project_into_company():
    from identity_resolution import resolve_candidate_identity

    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        domain="",
        sources=["https://github.com/affaan-m/agentshield"],
        evidence_metadata=[
            {
                "source": "github",
                "source_url": "https://github.com/affaan-m/agentshield",
                "owner_name": "affaan-m",
                "owner_type": "User",
                "homepage": "https://cerebralvalley.ai",
                "description": "AI agent security scanner for MCP permissions.",
            }
        ],
        attio_status="no_match",
    )

    result = resolve_candidate_identity(candidate)

    assert result.identity_type in {"oss_project_watch", "oss_with_commercial_intent"}
    assert result.verified_domain == ""
    assert result.attio_safe_to_match is False
    assert result.recommended_identity_action != "Assign owner"


def test_apply_identity_resolution_updates_candidate_fields():
    from identity_resolution import apply_identity_resolution

    candidates = [
        _candidate(
            domain="burrow.security",
            founders=["Jane Founder"],
            founder_profiles=[{"name": "Jane Founder"}],
        )
    ]

    resolved, resolutions = apply_identity_resolution(candidates)

    assert len(resolutions) == 1
    assert resolved[0].domain == "burrow.security"
    assert resolved[0].identity_type == "verified_company"
    assert resolved[0].identity_confidence_score >= 70
    assert resolved[0].commercial_intent_score >= 50
    assert resolved[0].attio_safe_to_match is True
    assert resolved[0].recommended_identity_action == "Assign owner"


def test_apply_identity_resolution_demotes_weak_unknown_oss_row():
    from identity_resolution import apply_identity_resolution

    candidates = [
        _candidate(
            name="example/weak-demo",
            stable_key="repo:weak-demo",
            candidate_type="oss_project",
            source="https://github.com/example/weak-demo",
            sources=["https://github.com/example/weak-demo"],
            domain="",
            founders=[],
            founder_profiles=[],
            maintainer_profiles=[],
            attio_status="unknown",
            why_on_radar="Example tutorial repo for trying a toy workflow.",
        )
    ]

    resolved, resolutions = apply_identity_resolution(candidates)

    assert resolutions[0].identity_type == "oss_project_watch"
    assert resolutions[0].recommended_identity_action == "Monitor only"
    assert resolved[0].recommended_identity_action == "Monitor only"
