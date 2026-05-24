from __future__ import annotations


def test_candidate_quality_rejects_category_article_fragments_from_validation_artifact():
    from candidate_quality import candidate_name_quality

    cases = [
        {
            "name": "Agentic AI Operations",
            "domain": "digitalapplied.com",
            "url": "https://www.digitalapplied.com/blog/agentic-ai-operations-team-playbook-process-automation-2026",
            "headline": "Agentic AI Operations Team Playbook: Process Automation 2026",
        },
        {
            "name": "AI Workflow Automation",
            "domain": "make.com",
            "url": "https://www.make.com/en",
            "headline": "AI Workflow Automation Software & Tools | Make",
        },
        {
            "name": "AI Data Infrastructure",
            "domain": "logiciel.io",
            "url": "https://logiciel.io/blog/ai-data-infrastructure-guide",
            "headline": "AI Data Infrastructure: Architecture, Strategy, and Challenges",
        },
        {
            "name": "Application Security",
            "domain": "blackduck.com",
            "url": "https://www.blackduck.com/",
            "headline": "Application Security | Open Source Security | SAST/DAST/SCA Tools | Black Duck",
        },
        {
            "name": "I Tried This",
            "domain": "virtualizationhowto.com",
            "url": "https://www.virtualizationhowto.com/2026/05/i-tried-this-new-open-source-kubernetes-dashboard-and-its-surprisingly-good/",
            "headline": "I Tried This New Open Source Kubernetes Dashboard and It’s Surprisingly Good - Virtualization Howto",
        },
        {
            "name": "Introducing Agentic Pipelines",
            "domain": "atlassian.com",
            "url": "https://www.atlassian.com/blog/bitbucket/introducing-agentic-pipelines-ai-automation",
            "headline": "Introducing Agentic Pipelines: AI automation for chores devs don't want to do - Inside Atlassian",
        },
        {
            "name": "About",
            "domain": "docs.cloud.google.com",
            "url": "https://docs.cloud.google.com/dataplex/docs/about-data-lineage",
            "headline": "About data lineage | Knowledge Catalog | Google Cloud Documentation",
        },
    ]

    for case in cases:
        quality = candidate_name_quality(
            name=case["name"],
            domain=case["domain"],
            urls=[case["url"]],
            source_headline=case["headline"],
            why_on_radar=case["headline"],
            candidate_type="company_web",
        )
        assert quality.usable is False, case["name"]
        assert quality.reason == "article_title_fragment"


def test_candidate_quality_keeps_domain_matched_company_homepage():
    from candidate_quality import candidate_name_quality

    quality = candidate_name_quality(
        name="Zencoder",
        domain="zencoder.ai",
        urls=["https://zencoder.ai/"],
        source_headline="Zencoder | The AI Coding Agent",
        why_on_radar="Zencoder | The AI Coding Agent",
        candidate_type="company_web",
    )

    assert quality.usable is True


def test_candidate_quality_rejects_incumbent_developer_platform_context():
    from candidate_quality import candidate_name_quality

    quality = candidate_name_quality(
        name="Google for Developers",
        domain="developers.google.com",
        urls=["https://developers.google.com/"],
        source_headline="Google for Developers | Build with Gemini",
        why_on_radar="Build with Gemini and Google developer tools.",
        candidate_type="company_web",
    )

    assert quality.usable is False
    assert quality.reason == "incumbent_platform_context"


def test_candidate_quality_rejects_pronoun_led_hn_title_fragment_when_domain_mismatches():
    from candidate_quality import candidate_name_quality

    quality = candidate_name_quality(
        name="My AI",
        domain="wuphf.team",
        urls=["https://wuphf.team"],
        source_headline="Show HN: My AI agents bully each other to prevent context drift",
        why_on_radar="Show HN: My AI agents bully each other to prevent context drift",
        candidate_type="company_web",
    )

    assert quality.usable is False
    assert quality.reason == "article_title_fragment"


def test_candidate_quality_rejects_observed_hn_product_title_fragments():
    from candidate_quality import candidate_name_quality

    quality = candidate_name_quality(
        name="AI CAD Harness",
        domain="fusion.adam.new",
        urls=["https://fusion.adam.new/install"],
        source_headline="Show HN: AI CAD Harness",
        why_on_radar="Show HN: AI CAD Harness",
        candidate_type="company_web",
    )

    assert quality.usable is False
    assert quality.reason == "article_title_fragment"
