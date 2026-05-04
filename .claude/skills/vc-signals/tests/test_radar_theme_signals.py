from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "items",
    [
        [
            {"source": "github", "title": "Bring Back /buddy", "url": "https://github.com/acme/cmux/issues/1"},
            {"source": "github", "title": "Restore cmux themes", "url": "https://github.com/acme/cmux/issues/2"},
        ],
        [
            {"source": "reddit", "title": "$100 bounty: write an MCP docs example", "url": "https://reddit.com/bounty-1"},
            {"source": "hackernews", "title": "Share your MCP server config", "url": "https://news.ycombinator.com/item?id=1"},
        ],
        [
            {"source": "github", "title": "fix: restore theme toggle", "url": "https://github.com/acme/tool/pull/3"},
            {"source": "github", "title": "chore: merge package update", "url": "https://github.com/acme/tool/pull/4"},
        ],
        [
            {"source": "reddit", "title": "Interesting new helper", "url": "https://reddit.com/generic-1"},
            {"source": "hackernews", "title": "Tiny utility plugin", "url": "https://news.ycombinator.com/item?id=2"},
        ],
    ],
)
def test_generic_activity_clusters_do_not_create_theme_signals(items):
    from radar_sources import classify_source_item
    from radar_theme_signals import build_theme_signals

    signals = [classify_source_item(sector="devtools", item=item) for item in items]

    assert build_theme_signals(signals, sectors=("devtools",)) == []


def test_clustered_reddit_pain_creates_theme_signal():
    from radar_sources import classify_source_item
    from radar_theme_signals import build_theme_signals

    signals = [
        classify_source_item(
            sector="cybersecurity",
            item={
                "source": "reddit",
                "title": "How are teams controlling AI agent permissions?",
                "url": "https://reddit.com/1",
            },
        ),
        classify_source_item(
            sector="cybersecurity",
            item={
                "source": "reddit",
                "title": "MCP tools are creating security review headaches",
                "url": "https://reddit.com/2",
            },
        ),
    ]

    themes = build_theme_signals(signals, sectors=("cybersecurity",))

    assert len(themes) == 1
    assert themes[0].market_sector == "Cybersecurity"
    assert themes[0].theme == "AI agent security"
    assert themes[0].confidence == "Medium"
    assert "No verified company" in themes[0].why_no_company_yet


def test_generic_jobs_and_resume_posts_do_not_create_theme_signal():
    from radar_sources import classify_source_item
    from radar_theme_signals import build_theme_signals

    signals = [
        classify_source_item(
            sector="data-infra",
            item={
                "source": "reddit",
                "title": "Remote Job - Data Engineering Manager",
                "url": "https://reddit.com/job",
            },
        ),
        classify_source_item(
            sector="data-infra",
            item={
                "source": "reddit",
                "title": "Review my resume for data engineer roles",
                "url": "https://reddit.com/resume",
            },
        ),
    ]

    assert build_theme_signals(signals, sectors=("data-infra",)) == []


def test_social_hype_without_named_product_is_filtered():
    from radar_sources import classify_source_item
    from radar_theme_signals import build_theme_signals

    signals = [
        classify_source_item(
            sector="vertical-ai",
            item={
                "source": "tiktok",
                "title": "This unnamed AI tool changed my workflow forever",
                "url": "https://tiktok.com/1",
            },
        ),
        classify_source_item(
            sector="vertical-ai",
            item={
                "source": "instagram",
                "title": "You need this insane AI productivity hack",
                "url": "https://instagram.com/2",
            },
        ),
    ]

    assert build_theme_signals(signals, sectors=("vertical-ai",)) == []
