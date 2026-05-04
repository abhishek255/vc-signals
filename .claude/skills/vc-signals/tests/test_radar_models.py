def test_signal_roundtrip_dict():
    from radar_models import Signal

    signal = Signal(
        source="reddit",
        role="pain",
        title="Teams hate debugging flaky AI agents",
        url="https://reddit.com/r/devops/example",
        sector="devtools",
        theme="Agent reliability",
        text="Repeated complaints about flaky agent runs.",
        can_create_candidate=False,
        evidence_strength=35,
        reason="Reddit pain evidence should support themes, not directly create rows.",
    )

    assert Signal.from_dict(signal.to_dict()) == signal


def test_candidate_serializes_profile_fields():
    from radar_models import Candidate

    candidate = Candidate(
        name="AgentShield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        company_linkedin="",
        company_x="",
        founder_profiles=[{"name": "affaan-m", "github": "https://github.com/affaan-m"}],
    )

    payload = candidate.to_dict()
    assert payload["name"] == "AgentShield"
    assert payload["founder_profiles"][0]["github"] == "https://github.com/affaan-m"
