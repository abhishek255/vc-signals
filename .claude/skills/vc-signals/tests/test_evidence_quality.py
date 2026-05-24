from __future__ import annotations


def test_stage_funding_source_quality_separates_durable_from_weak_sources():
    from evidence_quality import classify_evidence_source

    assert classify_evidence_source("https://zencoder.ai/about", candidate_domain="zencoder.ai").quality == "durable"
    assert classify_evidence_source("https://www.ycombinator.com/companies/voker", candidate_domain="voker.ai").quality == "durable"
    assert classify_evidence_source("https://www.businesswire.com/news/home/example", candidate_domain="zencoder.ai").quality == "durable"
    assert classify_evidence_source("https://tracxn.com/d/companies/zencoder/example", candidate_domain="zencoder.ai").quality == "weak"
    assert classify_evidence_source("https://nubiapage.com/zencoder-review-2026-ai-login-extension-alternatives-user-experience-and-faqs/", candidate_domain="zencoder.ai").quality == "weak"

