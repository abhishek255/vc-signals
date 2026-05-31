def test_reddit_pain_signal_cannot_create_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="data-infra",
        item={
            "source": "reddit",
            "title": "What are people using for data lineage now?",
            "url": "https://reddit.com/r/dataengineering/example",
            "snippet": "Comments mention broken pipelines and lineage pain.",
        },
    )

    assert signal.role == "pain"
    assert signal.can_create_candidate is False
    assert "support themes" in signal.reason


def test_hn_show_can_create_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="cybersecurity",
        item={
            "source": "hackernews",
            "title": "Show HN: BeeSafe AI stops voice phishing for banks",
            "url": "https://news.ycombinator.com/item?id=1",
        },
    )

    assert signal.role == "launch"
    assert signal.can_create_candidate is True


def test_product_hunt_launch_can_create_research_deeper_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="company-formation",
        item={
            "source": "producthunt",
            "title": "AgentFence by Ada Rao",
            "url": "https://www.producthunt.com/products/agentfence",
            "description": "Permission firewall for AI agents",
            "company_name": "AgentFence",
            "maker_name": "Ada Rao",
            "action": "research deeper",
        },
    )

    assert signal.role == "producthunt_launch"
    assert signal.can_create_candidate is True
    assert signal.metadata["source_lane"] == "Product Hunt"
    assert signal.metadata["action"] == "research deeper"


def test_github_issue_cannot_create_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="oss",
        item={
            "source": "github",
            "title": "Add MCP server",
            "url": "https://github.com/org/repo/issues/1",
        },
    )

    assert signal.role == "activity"
    assert signal.can_create_candidate is False


def test_source_lane_preserves_social_video_sources():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="vertical-ai",
        item={
            "source": "tiktok",
            "title": "DentalDesk AI shows automated front desk intake for clinics",
            "url": "https://www.tiktok.com/@dentaldesk/video/1",
            "company_name": "DentalDesk AI",
            "website": "https://dentaldesk.ai",
        },
    )

    assert signal.role == "product_demo"
    assert signal.can_create_candidate is True
    assert signal.metadata["source_lane"] == "TikTok"


def test_yc_directory_with_official_domain_can_create_research_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="company-formation",
        item={
            "source": "yc_directory",
            "title": "AgentForge | Y Combinator",
            "url": "https://www.ycombinator.com/companies/agentforge",
            "company_name": "AgentForge",
            "website": "https://agentforge.dev",
            "domain": "agentforge.dev",
            "stage": "Early",
            "batch": "Spring 2026",
            "action": "research deeper",
        },
    )

    assert signal.role == "yc_company"
    assert signal.can_create_candidate is True
    assert signal.metadata["source_lane"] == "YC Directory"
    assert signal.metadata["action"] == "research deeper"


def test_yc_directory_without_official_domain_needs_enrichment():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="company-formation",
        item={
            "source": "yc_directory",
            "title": "AgentForge | Y Combinator",
            "url": "https://www.ycombinator.com/companies/agentforge",
            "company_name": "AgentForge",
        },
    )

    assert signal.role == "yc_company"
    assert signal.can_create_candidate is False
    assert "official website" in signal.reason.lower()


def test_x_launch_needs_company_evidence_before_candidate_creation():
    from radar_sources import classify_source_item

    weak = classify_source_item(
        sector="company-formation",
        item={
            "source": "x",
            "title": "Launching something new for AI agent security",
            "url": "https://x.com/founder/status/1",
        },
    )
    strong = classify_source_item(
        sector="company-formation",
        item={
            "source": "x",
            "title": "Launching AgentForge for AI agent security",
            "url": "https://x.com/founder/status/2",
            "company_name": "AgentForge",
            "website": "https://agentforge.dev",
        },
    )

    assert weak.role == "social_launch"
    assert weak.can_create_candidate is False
    assert strong.role == "social_launch"
    assert strong.can_create_candidate is True
    assert strong.metadata["source_lane"] == "X"


def test_generic_social_video_does_not_create_candidate():
    from radar_sources import classify_source_item

    signal = classify_source_item(
        sector="vertical-ai",
        item={
            "source": "instagram",
            "title": "AI agents are going to change every local business",
            "url": "https://www.instagram.com/p/example",
        },
    )

    assert signal.role == "social_demo"
    assert signal.can_create_candidate is False
    assert signal.metadata["source_lane"] == "Instagram"
