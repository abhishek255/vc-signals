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
