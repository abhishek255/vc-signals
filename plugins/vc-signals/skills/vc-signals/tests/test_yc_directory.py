from __future__ import annotations


def test_normalize_yc_company_preserves_official_identity_and_stage():
    from yc_directory import normalize_yc_company

    row = {
        "name": "Voker",
        "slug": "voker",
        "website": "https://voker.ai",
        "url": "https://www.ycombinator.com/companies/voker",
        "one_liner": "The Agent Analytics Platform",
        "long_description": "Monitoring and improving AI agents.",
        "team_size": 6,
        "batch": "Summer 2024",
        "stage": "Early",
        "status": "Active",
        "tags": ["Developer Tools", "AI"],
        "industry": "B2B",
        "subindustry": "B2B -> Engineering, Product and Design",
        "launched_at": 1722887304,
    }

    company = normalize_yc_company(row)

    assert company["source"] == "yc_directory"
    assert company["source_lane"] == "YC Directory"
    assert company["name"] == "Voker"
    assert company["domain"] == "voker.ai"
    assert company["website"] == "https://voker.ai"
    assert company["stage"] == "Early"
    assert company["headcount"] == "6"
    assert company["batch"] == "Summer 2024"
    assert company["evidence"]["stage"] == "https://www.ycombinator.com/companies/voker"
    assert company["evidence"]["headcount"] == "https://www.ycombinator.com/companies/voker"
    assert "founder_team_missing_from_yc_public_api" in company["missing_evidence"]
    assert company["action"] == "research deeper"


def test_normalize_yc_company_without_website_keeps_identity_gap():
    from yc_directory import normalize_yc_company

    company = normalize_yc_company(
        {
            "name": "ShieldAgent",
            "slug": "shieldagent",
            "url": "https://www.ycombinator.com/companies/shieldagent",
            "one_liner": "Runtime security for AI agents",
            "batch": "Spring 2026",
            "stage": "Early",
        }
    )

    assert company["domain"] == ""
    assert company["website"] == ""
    assert "yc_official_website_missing" in company["missing_evidence"]
    assert company["lead_route"] == "research_deeper"


def test_run_yc_directory_filters_terms_batches_and_limits():
    from yc_directory import run_yc_directory

    payload = [
        {
            "name": "Old Consumer Co",
            "website": "https://old.example",
            "url": "https://www.ycombinator.com/companies/old-consumer",
            "one_liner": "Consumer shopping app",
            "batch": "Winter 2015",
            "stage": "Early",
        },
        {
            "name": "AgentForge",
            "website": "https://agentforge.dev",
            "url": "https://www.ycombinator.com/companies/agentforge",
            "one_liner": "AI agent security for developer teams",
            "long_description": "Security monitoring for AI agents.",
            "tags": ["Developer Tools", "Security", "AI"],
            "batch": "Spring 2026",
            "stage": "Early",
        },
    ]

    result = run_yc_directory(
        limit=1,
        terms=("agent", "security"),
        batches=("Spring 2026",),
        fetcher=lambda **_kwargs: payload,
        detail_fetcher=None,
    )

    assert result["companies"][0]["name"] == "AgentForge"
    assert result["companies"][0]["domain"] == "agentforge.dev"
    assert result["source_meta"]["endpoint"].endswith("/companies/all.json")
    assert result["warnings"] == []


def test_parse_yc_company_page_extracts_founders_and_social_links():
    from yc_directory import parse_yc_company_page

    html = """
<div data-page="{&quot;props&quot;:{&quot;company&quot;:{&quot;name&quot;:&quot;Voker&quot;,&quot;linkedin_url&quot;:&quot;https://www.linkedin.com/company/voker-ai/&quot;,&quot;twitter_url&quot;:&quot;https://x.com/Voker_ai&quot;,&quot;year_founded&quot;:2024,&quot;founders&quot;:[{&quot;full_name&quot;:&quot;Tyler Postle&quot;,&quot;title&quot;:&quot;Co-Founder&quot;,&quot;linkedin_url&quot;:&quot;https://www.linkedin.com/in/tyler-postle/&quot;,&quot;twitter_url&quot;:&quot;https://x.com/tylerpostle&quot;},{&quot;full_name&quot;:&quot;Alex Rudolph&quot;,&quot;title&quot;:&quot;Founder&quot;,&quot;linkedin_url&quot;:&quot;https://www.linkedin.com/in/alex-r-87470a198/&quot;,&quot;twitter_url&quot;:&quot;https://www.x.com/alexrudolphdev&quot;}]}}}"></div>
"""

    detail = parse_yc_company_page(html)

    assert detail["company_linkedin"] == "https://www.linkedin.com/company/voker-ai/"
    assert detail["company_x"] == "https://x.com/Voker_ai"
    assert detail["founding_year"] == "2024"
    assert detail["founder_profiles"] == [
        {
            "name": "Tyler Postle",
            "role": "Co-Founder",
            "linkedin": "https://www.linkedin.com/in/tyler-postle/",
            "x": "https://x.com/tylerpostle",
        },
        {
            "name": "Alex Rudolph",
            "role": "Founder",
            "linkedin": "https://www.linkedin.com/in/alex-r-87470a198/",
            "x": "https://www.x.com/alexrudolphdev",
        },
    ]


def test_run_yc_directory_merges_public_company_page_details():
    from yc_directory import run_yc_directory

    rows = [
        {
            "name": "Voker",
            "slug": "voker",
            "website": "https://voker.ai",
            "url": "https://www.ycombinator.com/companies/voker",
            "one_liner": "Agent analytics",
            "batch": "Summer 2024",
            "stage": "Early",
        }
    ]
    details = {
        "https://www.ycombinator.com/companies/voker": {
            "founder_profiles": [{"name": "Tyler Postle", "role": "Co-Founder", "linkedin": "", "x": ""}],
            "company_linkedin": "https://www.linkedin.com/company/voker-ai/",
            "company_x": "https://x.com/Voker_ai",
            "founding_year": "2024",
        }
    }

    result = run_yc_directory(
        limit=1,
        terms=("agent",),
        batches=("Summer 2024",),
        fetcher=lambda **_kwargs: rows,
        detail_fetcher=lambda url, **_kwargs: details[url],
    )

    company = result["companies"][0]
    assert company["company_linkedin"] == "https://www.linkedin.com/company/voker-ai/"
    assert company["company_x"] == "https://x.com/Voker_ai"
    assert company["founder_profiles"][0]["name"] == "Tyler Postle"
    assert company["founders"] == ["Tyler Postle"]
    assert "founder_team_missing_from_yc_public_api" not in company["missing_evidence"]
    assert company["evidence"]["founders"] == "https://www.ycombinator.com/companies/voker"
