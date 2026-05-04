import json
from pathlib import Path


def test_reddit_sources_include_curated_pain_subreddits():
    path = Path(".claude/skills/vc-signals/config/reddit_sources.json")
    config = json.loads(path.read_text())

    assert "devtools" in config
    assert "platformengineering" in config["devtools"]["primary"]
    assert "cybersecurity" in config
    assert "blueteamsec" in config["cybersecurity"]["primary"]
    assert "data-infra" in config
    assert "dataengineering" in config["data-infra"]["primary"]
