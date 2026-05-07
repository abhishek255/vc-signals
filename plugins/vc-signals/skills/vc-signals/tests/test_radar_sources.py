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
