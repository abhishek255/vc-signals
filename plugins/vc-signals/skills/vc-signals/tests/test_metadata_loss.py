import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from radar_models import Candidate, IdentityResolution, Signal


def test_metadata_loss_report_identifies_adapter_dropped():
    from metadata_loss import build_metadata_loss_report

    evidence = {
        "last30days": {
            "cybersecurity": {
                "items": [
                    {
                        "source": "hackernews",
                        "title": "Show HN: Burrow",
                        "url": "https://news.ycombinator.com/item?id=1",
                        "_raw_fields_present": ["title", "url", "outbound_url", "domain"],
                    }
                ]
            }
        },
        "github": [],
    }
    signal = Signal(
        source="hackernews",
        role="launch",
        title="Show HN: Burrow",
        url="https://news.ycombinator.com/item?id=1",
        can_create_candidate=True,
        metadata=evidence["last30days"]["cybersecurity"]["items"][0],
    )
    candidate = Candidate(
        name="Burrow",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://news.ycombinator.com/item?id=1",
        candidate_type="launch",
        evidence_metadata=[{"source_url": "https://news.ycombinator.com/item?id=1", "source": "hackernews", "title": "Show HN: Burrow"}],
    )
    resolution = IdentityResolution(
        candidate_key="burrow",
        original_name="Burrow",
        evidence_urls=["https://news.ycombinator.com/item?id=1"],
    )

    report = build_metadata_loss_report(
        evidence=evidence,
        signals=[signal],
        candidates=[candidate],
        identity_resolutions=[resolution],
    )

    assert report[0].loss_point == "adapter_dropped"
    assert "outbound_url" in report[0].identity_useful_fields_missing


def test_metadata_loss_report_identifies_upstream_missing():
    from metadata_loss import build_metadata_loss_report

    evidence = {
        "last30days": {
            "cybersecurity": {
                "items": [
                    {
                        "source": "hackernews",
                        "title": "Show HN: Burrow",
                        "url": "https://news.ycombinator.com/item?id=1",
                        "_raw_fields_present": ["title", "url", "author"],
                    }
                ]
            }
        },
        "github": [],
    }

    report = build_metadata_loss_report(
        evidence=evidence,
        signals=[],
        candidates=[],
        identity_resolutions=[],
    )

    assert report[0].loss_point == "upstream_missing"
    assert report[0].recommended_fix.startswith("Source output lacks")
