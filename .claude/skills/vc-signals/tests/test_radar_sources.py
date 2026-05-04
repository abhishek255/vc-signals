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
