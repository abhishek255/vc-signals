from __future__ import annotations


def test_sector_intelligence_explains_pain_signal_no_company():
    from radar_models import RejectedSignal, SectorCoverage, ThemeSignal
    from radar_sector_intelligence import build_sector_intelligence

    coverage = {
        "cybersecurity": SectorCoverage(sector="cybersecurity", raw_signals=2, candidates=0, rejected=2)
    }
    theme_signals = [
        ThemeSignal(
            market_sector="Cybersecurity",
            theme="AI agent security",
            source_lanes=["Reddit"],
            evidence_count=2,
            evidence_summary="Agent permission pain",
            why_it_matters="Repeated security pain.",
            why_no_company_yet="No verified company/domain/founder evidence appeared in this run.",
            suggested_search="AI agent security startups",
            confidence="Medium",
        )
    ]

    result = build_sector_intelligence(
        sectors=("cybersecurity",),
        coverage=coverage,
        candidates=[],
        rejected=[RejectedSignal(sector="cybersecurity", source="reddit", title="x", reason="source_not_candidate_eligible")],
        theme_signals=theme_signals,
        source_errors={},
        grounded_available=False,
    )

    item = result[0]
    assert item.market_sector == "Cybersecurity"
    assert item.status == "Pain signal, no company yet"
    assert "grounded company discovery" in item.why_no_more_companies.lower()
    assert "AI agent security startups" in item.next_hunt


def test_sector_intelligence_marks_oss_project_candidates():
    from radar_models import Candidate, SectorCoverage
    from radar_sector_intelligence import build_sector_intelligence

    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="Cybersecurity",
        market_sector="Cybersecurity",
        source_lane="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
    )

    result = build_sector_intelligence(
        sectors=("cybersecurity",),
        coverage={"cybersecurity": SectorCoverage(sector="cybersecurity", raw_signals=4, candidates=1, rejected=3)},
        candidates=[candidate],
        rejected=[],
        theme_signals=[],
        source_errors={},
        grounded_available=True,
    )

    assert result[0].status == "OSS/project candidates found"
    assert "OSS" in result[0].best_evidence


def test_sector_intelligence_excludes_oss_requested_sector():
    from radar_sector_intelligence import build_sector_intelligence

    result = build_sector_intelligence(
        sectors=("cybersecurity", "oss"),
        coverage={},
        candidates=[],
        rejected=[],
        theme_signals=[],
        source_errors={},
        grounded_available=True,
    )

    assert [item.market_sector for item in result] == ["Cybersecurity"]
