from __future__ import annotations


def test_parse_atom_feed_extracts_launch_identity_and_links():
    from product_hunt_launches import parse_product_hunt_feed

    feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>AgentFence by Ada Rao</title>
    <published>2026-05-25T07:15:00-07:00</published>
    <updated>2026-05-25T08:00:00-07:00</updated>
    <link rel="alternate" type="text/html" href="https://www.producthunt.com/products/agentfence"/>
    <content type="html">
      &lt;p&gt; Permission firewall for AI agents &lt;/p&gt;
      &lt;p&gt;
        &lt;a href="https://www.producthunt.com/products/agentfence"&gt;Discussion&lt;/a&gt; |
        &lt;a href="https://www.producthunt.com/r/p/123?app_id=339"&gt;Link&lt;/a&gt;
      &lt;/p&gt;
    </content>
  </entry>
</feed>
"""

    launches = parse_product_hunt_feed(feed, limit=5)

    assert launches == [
        {
            "source": "producthunt",
            "source_lane": "Product Hunt",
            "name": "AgentFence",
            "company_name": "AgentFence",
            "maker_name": "Ada Rao",
            "title": "AgentFence by Ada Rao",
            "tagline": "Permission firewall for AI agents",
            "description": "Permission firewall for AI agents",
            "published_at": "2026-05-25T07:15:00-07:00",
            "launch_date": "2026-05-25",
            "url": "https://www.producthunt.com/products/agentfence",
            "product_hunt_url": "https://www.producthunt.com/products/agentfence",
            "outbound_url": "https://www.producthunt.com/r/p/123?app_id=339",
            "domain": "",
            "website": "",
            "action": "research deeper",
            "lead_route": "research_deeper",
            "missing_evidence": ["official_domain_identity_not_confirmed"],
            "why_this_may_be_noise": "Product Hunt launch feed row; needs official domain, founder/team, stage, and customer evidence before owner routing.",
        }
    ]


def test_resolve_product_hunt_redirect_adds_domain_when_available():
    from product_hunt_launches import enrich_launch_domains

    launches = [
        {
            "outbound_url": "https://www.producthunt.com/r/p/123?app_id=339",
            "missing_evidence": ["official_domain_identity_not_confirmed"],
        }
    ]

    def fake_resolver(url: str) -> tuple[str, str]:
        assert url == "https://www.producthunt.com/r/p/123?app_id=339"
        return "https://agentfence.dev", ""

    enriched = enrich_launch_domains(launches, resolver=fake_resolver)

    assert enriched[0]["website"] == "https://agentfence.dev"
    assert enriched[0]["domain"] == "agentfence.dev"
    assert enriched[0]["missing_evidence"] == []
    assert enriched[0]["domain_resolution_status"] == "resolved"


def test_unresolved_product_hunt_redirect_keeps_identity_gap():
    from product_hunt_launches import enrich_launch_domains

    launches = [
        {
            "outbound_url": "https://www.producthunt.com/r/p/123?app_id=339",
            "missing_evidence": ["official_domain_identity_not_confirmed"],
        }
    ]

    enriched = enrich_launch_domains(launches, resolver=lambda _url: ("", "403 Cloudflare challenge"))

    assert enriched[0]["domain"] == ""
    assert enriched[0]["website"] == ""
    assert enriched[0]["missing_evidence"] == ["official_domain_identity_not_confirmed"]
    assert enriched[0]["domain_resolution_status"] == "unresolved"
    assert enriched[0]["domain_resolution_warning"] == "403 Cloudflare challenge"
