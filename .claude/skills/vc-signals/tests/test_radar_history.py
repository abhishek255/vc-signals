from pathlib import Path


def test_stable_candidate_key_prefers_domain():
    from radar_history import stable_candidate_key
    from radar_models import Candidate

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://news.ycombinator.com/item?id=1",
        candidate_type="launch",
        domain="www.beesafe.ai",
    )

    assert stable_candidate_key(candidate) == "company:beesafe.ai"


def test_stable_candidate_key_uses_repo_for_oss():
    from radar_history import stable_candidate_key
    from radar_models import Candidate

    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="OSS",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
    )

    assert stable_candidate_key(candidate) == "repo:github.com/affaan-m/agentshield"


def test_stable_candidate_key_falls_back_to_name_and_sector():
    from radar_history import stable_candidate_key
    from radar_models import Candidate

    candidate = Candidate(
        name="LineageWatch",
        sector="Data Infra",
        theme="Data lineage",
        source="",
        candidate_type="theme_probe",
    )

    assert stable_candidate_key(candidate) == "candidate:data-infra:lineagewatch"


def test_apply_weekly_tags_marks_new_candidate(tmp_path: Path):
    from radar_history import apply_weekly_tags, load_candidate_history
    from radar_models import Candidate

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        domain="beesafe.ai",
    )

    history = load_candidate_history(tmp_path)
    result = apply_weekly_tags([candidate], history, run_date="2026-05-04")

    assert result.candidates[0].weekly_tag == "NEW"
    assert result.candidates[0].stable_key == "company:beesafe.ai"
    assert result.faded == []


def test_apply_weekly_tags_marks_persistent_on_third_seen_week(tmp_path: Path):
    from radar_history import apply_weekly_tags
    from radar_models import Candidate

    history = {
        "company:beesafe.ai": {
            "display_name": "BeeSafe AI",
            "first_seen": "2026-04-20",
            "last_seen": "2026-04-27",
            "weeks_seen": 2,
            "missed_weeks": 0,
            "sectors": ["Cybersecurity"],
            "themes": ["AI fraud defense"],
            "last_source": "https://beesafe.ai",
        }
    }
    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        domain="beesafe.ai",
    )

    result = apply_weekly_tags([candidate], history, run_date="2026-05-04")

    assert result.candidates[0].weekly_tag == "PERSISTENT"
    assert history["company:beesafe.ai"]["weeks_seen"] == 3


def test_apply_weekly_tags_marks_returning_after_two_missed_weeks(tmp_path: Path):
    from radar_history import apply_weekly_tags
    from radar_models import Candidate

    history = {
        "company:beesafe.ai": {
            "display_name": "BeeSafe AI",
            "first_seen": "2026-04-06",
            "last_seen": "2026-04-13",
            "weeks_seen": 1,
            "missed_weeks": 0,
            "sectors": ["Cybersecurity"],
            "themes": ["AI fraud defense"],
            "last_source": "https://beesafe.ai",
        }
    }
    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        domain="beesafe.ai",
    )

    result = apply_weekly_tags([candidate], history, run_date="2026-05-04")

    assert result.candidates[0].weekly_tag == "RETURNING"


def test_apply_weekly_tags_emits_faded_for_missing_prior_candidate(tmp_path: Path):
    from radar_history import apply_weekly_tags

    history = {
        "company:oldco.ai": {
            "display_name": "OldCo",
            "first_seen": "2026-04-20",
            "last_seen": "2026-04-27",
            "weeks_seen": 1,
            "missed_weeks": 0,
            "sectors": ["AI Infra"],
            "themes": ["Agent runtime"],
            "last_source": "https://oldco.ai",
        }
    }

    result = apply_weekly_tags([], history, run_date="2026-05-04")

    assert result.faded == [{
        "stable_key": "company:oldco.ai",
        "name": "OldCo",
        "sector": "AI Infra",
        "theme": "Agent runtime",
        "last_seen": "2026-04-27",
        "source": "https://oldco.ai",
        "weekly_tag": "FADED",
    }]


def test_apply_weekly_tags_is_idempotent_for_same_run_date(tmp_path: Path):
    from radar_history import apply_weekly_tags
    from radar_models import Candidate

    candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        domain="beesafe.ai",
    )
    first = apply_weekly_tags([candidate], {}, run_date="2026-05-04")
    second_candidate = Candidate(
        name="BeeSafe AI",
        sector="Cybersecurity",
        theme="AI fraud defense",
        source="https://beesafe.ai",
        candidate_type="company_web",
        domain="beesafe.ai",
    )

    second = apply_weekly_tags([second_candidate], first.history, run_date="2026-05-04")

    assert second.candidates[0].weekly_tag == "NEW"
    assert second.history["company:beesafe.ai"]["weeks_seen"] == 1
