from __future__ import annotations

from datetime import date


def _candidate():
    from radar_models import Candidate

    return Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://beesafe.ai",
        candidate_type="company_web",
    )


def test_cached_enrichment_requires_fresh_entry_and_field_evidence():
    from radar_enrichment import apply_candidate_enrichment

    candidates = apply_candidate_enrichment(
        [_candidate()],
        cache={
            "beesafe ai": {
                "fetched_at": "2026-05-01",
                "stage": "Seed",
                "raised": "$4M",
                "headcount": "12",
                "evidence": {
                    "stage": "https://beesafe.ai/about",
                    "raised": "https://beesafe.ai/blog/seed",
                },
            }
        },
        now=date(2026, 5, 4),
    )

    candidate = candidates[0]
    assert candidate.stage == "Seed"
    assert candidate.raised == "$4M"
    assert candidate.headcount == ""
    assert candidate.enrichment_evidence == {
        "stage": "https://beesafe.ai/about",
        "raised": "https://beesafe.ai/blog/seed",
    }


def test_stale_cache_entry_is_ignored():
    from radar_enrichment import apply_candidate_enrichment

    candidates = apply_candidate_enrichment(
        [_candidate()],
        cache={
            "beesafe ai": {
                "fetched_at": "2026-04-01",
                "stage": "Seed",
                "evidence": {"stage": "https://beesafe.ai/about"},
            }
        },
        now=date(2026, 5, 4),
    )

    assert candidates[0].stage == ""
    assert candidates[0].enrichment_evidence == {}


def test_source_enrichment_does_not_hallucinate_without_evidence():
    from radar_enrichment import merge_source_enrichment

    candidate = merge_source_enrichment(
        _candidate(),
        {
            "stage": "Seed",
            "founders": ["Asha Rao"],
            "evidence": {"founders": "https://beesafe.ai/about"},
        },
    )

    assert candidate.stage == ""
    assert candidate.founders == ["Asha Rao"]
    assert candidate.enrichment_evidence == {"founders": "https://beesafe.ai/about"}


def test_attio_enrichment_maps_stage_raised_and_headcount():
    from radar_enrichment import merge_attio_enrichment

    candidate = merge_attio_enrichment(
        _candidate(),
        {
            "last_round_type": "Seed",
            "total_amount_raised": "$4M",
            "employee_range": "11-50",
        },
    )

    assert candidate.stage == "Seed"
    assert candidate.raised == "$4M"
    assert candidate.headcount == "11-50"
    assert candidate.enrichment_evidence == {
        "stage": "attio",
        "raised": "attio",
        "headcount": "attio",
    }
